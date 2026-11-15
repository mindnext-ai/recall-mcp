"""SM-2 spaced repetition algorithm.

A pure-function implementation of the SM-2 algorithm (Wozniak, 1990),
the same scheduling core used by SuperMemo and (in spirit) Anki.

Given a card's current state and a review grade (0-5), it returns the
next state: ease factor, interval in days, and repetition count.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_EASE = 1.3
DEFAULT_EASE = 2.5


@dataclass
class CardState:
    ease_factor: float = DEFAULT_EASE
    interval_days: int = 0
    repetitions: int = 0


def review(state: CardState, grade: int) -> CardState:
    """Apply one review.

    grade: 0-5 recall quality (5 = perfect, 3 = barely recalled,
    below 3 = forgotten and the card restarts).
    """
    if not 0 <= grade <= 5:
        raise ValueError(f"grade must be 0..5, got {grade}")

    if grade < 3:
        # Forgotten: restart the learning steps, keep the ease factor
        # adjustment below so hard cards still drift down.
        repetitions = 0
        interval = 1
    else:
        if state.repetitions == 0:
            interval = 1
        elif state.repetitions == 1:
            interval = 6
        else:
            interval = round(state.interval_days * state.ease_factor)
        repetitions = state.repetitions + 1

    ease = state.ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ease = max(MIN_EASE, ease)

    return CardState(ease_factor=round(ease, 4), interval_days=interval,
                     repetitions=repetitions)
