import argparse

from rich.panel import Panel

from .game_logic import (
    ANSWERS,
    MAX_ATTEMPTS,
    VALID_GUESSES,
    WORD_LENGTH,
    Game,
)
from .renderer import console, render


def parse_feedback(raw: str) -> tuple[int, ...] | None:
    """Parse five feedback digits: 0=wrong, 1=present, 2=correct."""
    value = "".join(raw.split())

    if len(value) != WORD_LENGTH:
        return None

    if any(char not in "012" for char in value):
        return None

    return tuple(int(char) for char in value)


def get_input(prompt: str) -> str | None:
    """Read input, returning None when the user quits or cancels."""
    try:
        value = console.input(prompt).strip().lower()
    except EOFError, KeyboardInterrupt:
        console.print("\n[dim]Game cancelled.[/dim]")
        return None

    if value in {"q", "quit", "exit"}:
        console.print("[dim]Game ended.[/dim]")
        return None

    return value


def play(
    answer: str | None = None,
    investigate: bool = False,
    free: bool = False,
) -> None:
    game = Game(
        answer=answer,
        investigate=investigate,
        free=free,
    )

    if free:
        message = "[cyan]Enter a guess and its feedback from your existing Wordle game.[/cyan]"
    else:
        message = "[cyan]Guess the five-letter word. Enter q to quit.[/cyan]"

    while not game.finished:
        render(game, message)

        guess = get_input(
            "\n[bold cyan]Your guess[/bold cyan] [dim](q to quit)[/dim] > "
        )

        if guess is None:
            return

        if len(guess) != WORD_LENGTH:
            message = (
                "[bold red]Enter a word containing exactly five letters.[/bold red]"
            )
            continue

        if guess not in VALID_GUESSES:
            message = f"[bold red]{guess.upper()} isn't in the word list. Try again.[/bold red]"
            continue

        feedback = None

        if free:
            # Try until the user provides a valid feedback
            while True:
                raw = get_input(
                    "\n[bold yellow]Feedback[/bold yellow] "
                    "[dim](0=gray, 1=yellow, 2=green)[/dim] > "
                )

                if raw is None:
                    return

                feedback = parse_feedback(raw)

                if feedback is None:
                    message = (
                        "[bold red]Feedback must contain exactly five digits: "
                        "0, 1, or 2. Try again.[/bold red]"
                    )
                    console.print(message)
                    continue

                break

        accepted = game.submit(guess, feedback)

        if not accepted:
            message = (
                "[bold red]That feedback leaves no possible answers. "
                "Please re-examine your feedbacks and answers[/bold red]. "
            )

            continue

        if game.has_won:
            message = "[cyan]You found the word![/cyan]"
        elif game.finished:
            message = "[cyan]No guesses remaining.[/cyan]"
        else:
            remaining = MAX_ATTEMPTS - game.attempts
            message = f"[cyan]{remaining} guesses remaining.[/cyan]"

    render(game, message)

    if game.has_won:
        console.print(
            Panel(
                f"[bold green]Solved in {game.attempts} "
                f"{'guess' if game.attempts == 1 else 'guesses'}![/bold green]",
                border_style="green",
            )
        )
    elif game.free or game.answer is None:
        # Free mode has no answer, so we can't show the answer at the end.
        console.print(
            Panel(
                "[bold red]No guesses remaining.[/bold red]\n"
                "Free mode does not know the answer; "
                "continue in a new session to investigate further.",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]Game over.[/bold red]\n"
                f"The answer was [bold]{game.answer.upper()}[/bold].",
                border_style="red",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play Wordle or investigate an existing board."
    )
    parser.add_argument(
        "-w",
        "--word",
        help="Set the secret answer for a normal game. Does not apply in free mode.",
    )
    parser.add_argument(
        "-i",
        "--investigate",
        action="store_true",
        help="Show entropy recommendations and possible answers.",
    )
    parser.add_argument(
        "-f",
        "--free",
        action="store_true",
        help="Manually enter guesses and feedback from an existing game.",
    )

    args = parser.parse_args()

    if not ANSWERS:
        parser.error("The answer word list is empty.")

    if args.free and args.word:
        parser.error("--word cannot be used with --free.")

    answer = args.word.lower() if args.word else None

    if answer is not None:  # noqa: SIM102
        if len(answer) != WORD_LENGTH or answer not in ANSWERS:
            parser.error("The secret word must be a five-letter possible answer.")

    play(
        answer=answer,
        investigate=args.investigate or args.free,
        free=args.free,
    )
