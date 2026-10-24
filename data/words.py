from pathlib import Path


def load_as_list(filename: Path) -> list[str]:
    with open(filename) as file:
        return eval(file.read())


DATA_DIR = Path(__file__).resolve().parent

words = load_as_list(DATA_DIR / "words.txt")
guesses = load_as_list(DATA_DIR / "guesses.txt")


WORD_LENGTH = 5
WRONG, POS, CORRECT = 0, 1, 2


def match(word: str, guess: str) -> tuple[int, ...]:
    remaining = list(word)
    board = [WRONG] * WORD_LENGTH

    # Exact matches
    for i in range(WORD_LENGTH):
        if remaining[i] == guess[i]:
            board[i] = CORRECT
            remaining[i] = ""

    # Misplaced matches
    for i, c in enumerate(guess):
        if board[i] == WRONG and c in remaining:
            board[i] = POS
            remaining[remaining.index(c)] = ""

    return tuple(board)
