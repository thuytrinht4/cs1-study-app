"""Import the starter deck (data/seed_cards.json) into the user's card bank.

Idempotent: re-running upserts on the card id, so it won't create duplicates.
Cards are owned by the importing user (owner_id), which keeps Row-Level
Security simple for a personal app.
"""
import json
from pathlib import Path
from . import db

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_cards.json"


def load_seed() -> list[dict]:
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def import_seed(user_id: str) -> int:
    """Insert/overwrite the seed cards for this user. Returns count."""
    cards = load_seed()
    rows = [{
        "id": c["id"],
        "topic": c["topic"],
        "module": c.get("module"),
        "type": c["type"],
        "front": c["front"],
        "model_answer": c["model_answer"],
        "hint": c.get("hint"),
        "max_marks": c.get("max_marks", 3),
        "source": "seed",
        "owner_id": user_id,
        "is_active": True,
    } for c in cards]
    db.upsert_cards(rows)
    return len(rows)


def is_seeded(user_id: str) -> bool:
    return len(db.get_cards(user_id)) > 0
