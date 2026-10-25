from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .game_logic import CORRECT, MAX_ATTEMPTS, POS, WORD_LENGTH, WRONG, Game

console = Console()

TILE_STYLES = {
    WRONG: "bold white on #3a3a3c",
    POS: "bold white on #b59f3b",
    CORRECT: "bold white on #538d4e",
}
EMPTY_STYLE = "on #242426"


def make_board(game: Game) -> Table:
    """Build the six-row, five-column board."""
    table = Table.grid(padding=(0, 1))

    for _ in range(WORD_LENGTH):
        table.add_column(width=3, justify="center")

    for row_index in range(MAX_ATTEMPTS):
        if row_index < game.attempts:
            guess, pattern = game.history[row_index]
            tiles = [
                Text(
                    f" {letter.upper()} ",
                    style=TILE_STYLES[state],
                )
                for letter, state in zip(guess, pattern)
            ]
        else:
            tiles = [Text("   ", style=EMPTY_STYLE) for _ in range(WORD_LENGTH)]

        table.add_row(*tiles)

    return table


def render(game: Game, message: str = "") -> None:
    """Render the board, remaining candidates, and recommendation."""
    if console.is_terminal:
        console.clear()

    mode = (
        "FREE MODE"
        if game.free
        else "WORDLE" + " (INVESTIGATE)"
        if game.investigate
        else ""
    )

    panel = Panel(
        Align.center(make_board(game)),
        title=f"[bold]{mode}[/bold]",
        subtitle=f"{game.attempts}/{MAX_ATTEMPTS} guesses used",
        border_style="bright_white",
        padding=(1, 2),
    )
    console.print(Align.center(panel))

    legend = Text.assemble(
        (" WRONG ", TILE_STYLES[WRONG]),
        "  ",
        (" PRESENT ", TILE_STYLES[POS]),
        "  ",
        (" CORRECT ", TILE_STYLES[CORRECT]),
    )
    console.print(Align.center(legend))

    if message:
        console.print()
        console.print(Align.center(message))

    if not game.investigate:
        return

    console.print()

    count = len(game.candidates)

    if count <= 20:
        candidate_text = Text(
            "   ".join(word.upper() for word in game.candidates)
            if count
            # This should not happen
            else "No answers remain.",
            style="bold cyan" if count else "bold red",
            justify="center",
        )

        console.print(
            Panel(
                candidate_text,
                title=f"Remaining possible answers ({count})",
                border_style="cyan" if count else "red",
            )
        )
    else:
        console.print(
            Align.center(
                Text(
                    f"{count:,} possible answers remain.",
                    style="dim",
                )
            )
        )

    if not game.finished and count:
        suggestion = game.best_guess()

        if suggestion is not None:
            guess, entropy = suggestion

            suggestion_text = Text.assemble(
                ("Suggested guess: ", "bold"),
                (guess.upper(), "bold green"),
                (f"   Entropy: {entropy:.4f} bits", "dim"),
            )

            console.print(
                Align.center(
                    Panel(
                        suggestion_text,
                        title="Highest-entropy guess",
                        border_style="green",
                        padding=(0, 2),
                    )
                )
            )
