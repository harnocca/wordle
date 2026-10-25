import argparse
import csv
from collections import Counter
from enum import Enum
from pathlib import Path
from string import ascii_lowercase

from wordle_lib import calc_entropy, calc_points

from data.words import guesses, words

BASE_DIR = Path(__file__).resolve().parent
STATS_DIR = BASE_DIR / "stats"


class Dataset(Enum):
    FREQUENCY = ("Letter frequency", "Letter", "letter_frequency.csv")
    ENTROPY = ("Entropy", "Word", "entropy.csv")
    POINTS = ("Points", "Word", "points.csv")

    def __init__(self, label: str, key: str, file_name: str):
        self.label = label
        self.key = key
        self.file = file_name

    @property
    def path(self) -> Path:
        return STATS_DIR / self.file

    def format_value(self: Dataset, value: float) -> str:
        """Format values according to the dataset."""
        match self:
            case Dataset.FREQUENCY:
                return f"{value:.4%}"
            case Dataset.ENTROPY:
                return f"{value:.5f} bits"
            case Dataset.POINTS:
                return f"{value:,.0f} points"


DEFAULT_LOOKAROUND = 5

# Loading with deduplication and sorting
WORDS = sorted({word.lower() for word in words})
GUESSES = sorted({guess.lower() for guess in guesses})
print(f"Loaded {len(WORDS)} words and {len(GUESSES)} guesses.")


def sorted_dict(data: dict[str, float]) -> list[tuple[str, float]]:
    """Sort by descending value and break ties alphabetically."""
    return sorted(data.items(), key=lambda item: (-item[1], item[0]))


def compute_dataset(dataset: Dataset) -> list[tuple[str, float]]:
    """Calculate one of the three datasets."""
    match dataset:
        case Dataset.FREQUENCY:
            if not WORDS:
                raise ValueError(
                    "Words list is empty. Cannot calculate letter frequency."
                )

            # Counts how many words contain each letter, ignoring duplicates within a word.
            counts = Counter(
                letter
                for word in WORDS
                for letter in set(word)
                if letter in ascii_lowercase
            )

            total = len(WORDS)

            frequencies = {letter: counts[letter] / total for letter in ascii_lowercase}

            return sorted_dict(frequencies)
        case Dataset.ENTROPY:
            return sorted_dict(calc_entropy(GUESSES, WORDS))
        case Dataset.POINTS:
            return sorted_dict(calc_points(GUESSES, WORDS))


def save_dataset(
    dataset: Dataset,
    data: list[tuple[str, float]],
) -> None:
    """Save a ranked dataset as CSV."""
    path = dataset.path
    STATS_DIR.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["rank", "key", "value"])

        for rank, (key, value) in enumerate(data, start=1):
            writer.writerow([rank, key, value])

    print(f"Saved {len(data)} entries to {path.relative_to(BASE_DIR)}")


def load_dataset(dataset: Dataset) -> list[tuple[str, float]]:
    """Load a previously saved dataset."""
    path = dataset.path

    # Recommended pattern for CSV handling
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = [
            (
                int(row["rank"]),
                row["key"],
                float(row["value"]),
            )
            for row in reader
        ]

    rows.sort(key=lambda row: row[0])
    return [(key, value) for _, key, value in rows]


def get_dataset(
    dataset: Dataset,
    update: bool = False,
) -> list[tuple[str, float]]:
    """Load cached data, calculating and saving it if necessary."""
    path = dataset.path

    if update or not path.exists():
        print(f"Calculating data for {dataset.label}...")

        data = compute_dataset(dataset)
        save_dataset(dataset, data)
        return data

    return load_dataset(dataset)


def print_table(
    dataset: Dataset,
    data: list[tuple[str, float]],
    start: int = 0,
    stop: int | None = None,
    selected_rank: int | None = None,
) -> None:
    """Print a slice of a ranking, using one-based rank numbers."""
    if stop is None:
        stop = len(data)

    label = dataset.label
    key_label = dataset.key
    entries = data[start:stop]

    print(f"\n{label} — {len(data)} entries")
    print(f"{'':1} {'Rank':>6}  {key_label:<10} {'Value':>14}")
    print("-" * 40)

    for rank, (key, value) in enumerate(entries, start=start + 1):
        marker = ">" if rank == selected_rank else " "

        print(f"{marker} {rank:>6}  {key:<10} {dataset.format_value(value):>14}")


def window(
    data: list[tuple[str, float]],
    rank: int,
    lookaround: int,
) -> tuple[int, int]:
    """Return a slice with `around` entries on each side of a rank."""
    return max(0, rank - 1 - lookaround), min(len(data), rank + lookaround)


def save_all(dataset: Dataset | None) -> None:
    """Recalculate and save one or all datasets."""
    sets = [dataset] if dataset else [s for s in Dataset]

    for s in sets:
        print(f"\nCalculating {s.label}...")
        data = compute_dataset(s)
        save_dataset(s, data)


def positive_int(value: str) -> int:
    """Parse a positive integer for CLI arguments."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")

    return number


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="analysis.py",
        description=("Analyze Wordle letter frequency, entropy, and points."),
        epilog="""examples:
          python analysis.py -e --top 10      top 10 guesses by entropy
          python analysis.py -p --last        bottom 10 guesses by points
          python analysis.py -l --rank 5 3    letter frequency, rank 5 plus 3 on each side
          python analysis.py -e --lookup tarse 5
                                              entropy, "tarse" plus 5 on each side
          python analysis.py -e --save        recalculate and save entropy data
          python analysis.py --save           recalculate and save every dataset
          python analysis.py -e --top -U      ignore saved data and recalculate
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    datasets = parser.add_mutually_exclusive_group()
    datasets.add_argument(
        "-l",
        "--letters",
        dest="dataset",
        action="store_const",
        const="FREQUENCY",
        help="Use letter frequency data.",
    )
    datasets.add_argument(
        "-e",
        "--entropy",
        dest="dataset",
        action="store_const",
        const="ENTROPY",
        help="Use entropy data.",
    )
    datasets.add_argument(
        "-p",
        "--points",
        dest="dataset",
        action="store_const",
        const="POINTS",
        help="Use points data.",
    )

    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--top",
        type=positive_int,
        nargs="?",
        const=DEFAULT_LOOKAROUND * 2,
        metavar="N",
        help=("Show the top N entries (default: 10). This is also the default action."),
    )
    actions.add_argument(
        "--last",
        type=positive_int,
        nargs="?",
        const=DEFAULT_LOOKAROUND * 2,
        metavar="N",
        help="Show the last N entries (default: 10).",
    )
    actions.add_argument(
        "--rank",
        type=positive_int,
        nargs="+",
        metavar="N",
        help=(
            "Show the entry at rank N, or show COUNT entries on each "
            "side of it (default: 5): --rank 5 3."
        ),
    )
    actions.add_argument(
        "--lookup",
        nargs="+",
        metavar="KEY",
        help=(
            "Find a letter or word, or show COUNT entries on each "
            "side of it (default: 5): --lookup tarse 3."
        ),
    )
    actions.add_argument(
        "--save",
        action="store_true",
        help=(
            "Recalculate and save the selected dataset, or every "
            "dataset when none is selected."
        ),
    )

    parser.add_argument(
        "-U",
        "--update",
        action="store_true",
        help=("Ignore saved data, recalculate, and replace the saved data."),
    )

    return parser


def parse_lookup(
    parser: argparse.ArgumentParser,
    values: list[str],
) -> tuple[str, int]:
    """Split --lookup values into a key and an optional lookaround."""
    if len(values) > 2:
        parser.error("--lookup takes a key and, optionally, one number")

    if len(values) == 1:
        return values[0], DEFAULT_LOOKAROUND

    try:
        around = positive_int(values[1])
    except argparse.ArgumentTypeError as exc:
        parser.error(f"--lookup count {exc}")

    return values[0], around


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.rank is not None and len(args.rank) > 2:
        parser.error("--rank takes a rank and, optionally, one number")

    if args.save:
        save_all(args.dataset)
        return

    if args.dataset is None:
        parser.error("choose a dataset with -l, -e, or -p")

    dataset = Dataset[args.dataset]

    if args.rank is not None:
        rank = args.rank[0]
        lookaround = args.rank[1] if len(args.rank) == 2 else DEFAULT_LOOKAROUND
        data = get_dataset(dataset, args.update)

        if not 1 <= rank <= len(data):
            print(f"Rank must be between 1 and {len(data)}.")
            return

        print_table(
            dataset,
            data,
            *window(data, rank, lookaround),
            selected_rank=rank,
        )

    elif args.lookup is not None:
        key, lookaround = parse_lookup(parser, args.lookup)
        data = get_dataset(dataset, args.update)
        key = key.lower()

        index = next(
            (i for i, (item, _) in enumerate(data) if item == key),
            None,
        )

        if index is None:
            print(f"{key!r} was not found in the {dataset.label} dataset.")
            return

        print_table(
            dataset,
            data,
            *window(data, index + 1, lookaround),
            selected_rank=index + 1,
        )

    elif args.last is not None:
        data = get_dataset(dataset, args.update)

        start = max(0, len(data) - args.last)
        print_table(dataset, data, start, len(data))

    else:
        # --top with no value and no action both default to the top 10.
        data = get_dataset(dataset, args.update)
        print_table(dataset, data, 0, min(args.top or DEFAULT_LOOKAROUND * 2, len(data)))


if __name__ == "__main__":
    main()
