from pathlib import Path


def load_as_list(filename: Path) -> list[str]:
    with open(filename) as file:
        return eval(file.read())


DATA_DIR = Path(__file__).resolve().parent

words = load_as_list(DATA_DIR / "words.txt")
guesses = load_as_list(DATA_DIR / "guesses.txt")
