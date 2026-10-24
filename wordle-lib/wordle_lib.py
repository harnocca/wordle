"""Wordle analysis utilities powered by a C extension."""

from _wordle_lib import (
    calc_entropy as _calc_entropy,
)
from _wordle_lib import (
    calc_points as _calc_points,
)
from _wordle_lib import (
    match as _match,
)


def match(
    guess: str,
    word: str,
    /,
) -> tuple[int, int, int, int, int]:
    """Compare a guess against a possible answer.

    Args:
        guess: A five-letter guess.
        word: A five-letter possible answer.

    Returns:
        Five feedback values: 0 for wrong, 1 for misplaced,
        and 2 for correct.
    """
    return _match(guess, word)


def calc_entropy(
    guesses: list[str],
    words: list[str],
    /,
) -> dict[str, float]:
    """Calculate Shannon entropy for each guess.

    Args:
        guesses: Words to evaluate as guesses.
        words: Possible secret answers.

    Returns:
        A mapping of each guess to its entropy in bits.
    """
    return _calc_entropy(guesses, words)


def calc_points(
    guesses: list[str],
    words: list[str],
    /,
) -> dict[str, float]:
    """Calculate total positional scores for each guess.

    Args:
        guesses: Words to evaluate as guesses.
        words: Possible secret answers.

    Returns:
        A mapping of each guess to its total score across answers.
    """
    return _calc_points(guesses, words)
