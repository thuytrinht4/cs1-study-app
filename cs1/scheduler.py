"""Thin wrapper around the FSRS spaced-repetition scheduler.

Verified against fsrs 6.3.1. The whole FSRS Card is stored as a dict
(Card.to_dict()) so we don't depend on internal field names.

Ratings (match the UI buttons and the DB):
    1 = Again, 2 = Hard, 3 = Good, 4 = Easy
"""
from datetime import datetime, timezone
from fsrs import Scheduler, Card, Rating

# desired_retention 0.9 = aim to recall ~90% of cards when they come due.
# Raise toward 0.95 for harder targets (more frequent reviews), lower to study less.
_scheduler = Scheduler(desired_retention=0.90)


def new_card() -> dict:
    """A brand-new FSRS card (due now)."""
    return Card().to_dict()


def review(fsrs_dict: dict, rating: int, elapsed_ms: int | None = None) -> dict:
    """Apply a grade and return the updated FSRS card dict.
    The returned dict's 'due' (ISO string) is the next review time.
    """
    card = Card.from_dict(fsrs_dict)
    card, _log = _scheduler.review_card(
        card, Rating(rating), datetime.now(timezone.utc),
        review_duration=int(elapsed_ms) if elapsed_ms else None,
    )
    return card.to_dict()


def retrievability(fsrs_dict: dict) -> float:
    """Estimated probability you'd recall this card right now (0..1).
    Useful for mastery reports."""
    return _scheduler.get_card_retrievability(
        Card.from_dict(fsrs_dict), datetime.now(timezone.utc)
    )


def due_at(fsrs_dict: dict) -> datetime:
    return datetime.fromisoformat(fsrs_dict["due"])
