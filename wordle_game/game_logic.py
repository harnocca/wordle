from random import choice

import wordle_lib

from data.words import guesses, words

WORD_LENGTH = 5
MAX_ATTEMPTS = 6

WRONG, POS, CORRECT = 0, 1, 2
WIN_PATTERN = (CORRECT,) * WORD_LENGTH

ANSWERS = tuple(sorted({word.lower() for word in words}))

VALID_GUESSES = tuple(sorted({word.lower() for word in guesses}))


class Game:
    def __init__(
        self,
        answer: str | None = None,
        investigate: bool = False,
        free: bool = False,
    ):
        self.free = free
        self.investigate = investigate or free

        # In free mode, the answer is unknown.
        if free:
            self.answer = None
        else:
            self.answer = answer.lower() if answer is not None else choice(ANSWERS)

        self.history: list[tuple[str, tuple[int, ...]]] = []
        self.candidates: tuple[str, ...] = ANSWERS if self.investigate else ()
        self._suggestion: tuple[str, float] | None = None

    @property
    def attempts(self) -> int:
        return len(self.history)

    @property
    def has_won(self) -> bool:
        return bool(self.history) and self.history[-1][1] == WIN_PATTERN

    @property
    def finished(self) -> bool:
        return self.has_won or self.attempts >= MAX_ATTEMPTS

    def submit(
        self,
        guess: str,
        feedback: tuple[int, ...] | None = None,
    ) -> bool:
        """Submit a guess. Return False if an invalid feedback is provided."""
        if self.free:
            if feedback is None:
                raise ValueError("Free mode requires manual feedback.")

            if len(feedback) != WORD_LENGTH or any(
                value not in (WRONG, POS, CORRECT) for value in feedback
            ):
                raise ValueError("Invalid feedback pattern.")

            result = feedback
        else:
            assert self.answer is not None
            result = tuple(wordle_lib.match(guess, self.answer))

        next_candidates = self.candidates

        if self.investigate:
            next_candidates = tuple(
                candidate
                for candidate in self.candidates
                if tuple(wordle_lib.match(guess, candidate)) == result
            )

            # Reject guesses that eliminate all candidates, because it's likely a typo.
            if not next_candidates:
                return False

        self.history.append((guess, result))

        if self.investigate:
            self.candidates = next_candidates
            self._suggestion = None

        return True

    def best_guess(self) -> tuple[str, float] | None:
        """Return the highest-entropy guess for remaining candidates."""
        if not self.investigate or not self.candidates:
            return None

        if self._suggestion is None:
            scores = wordle_lib.calc_entropy(
                list(VALID_GUESSES),
                list(self.candidates),
            )

            candidate_set = frozenset(self.candidates)

            # Prefer higher entropy, then possible answers, then uses an alphabetical tiebreaker.
            self._suggestion = min(
                scores.items(),
                key=lambda item: (
                    -item[1],
                    item[0] not in candidate_set,
                    item[0],
                ),
            )

        return self._suggestion
