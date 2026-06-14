"""All Supabase access in one place.

Note on auth model (fine for a personal app): we keep a single cached
Supabase client. After sign-in, that client carries your JWT, so every
query runs as you and Row-Level Security returns only your rows. If you
ever make this truly multi-user on a shared server, give each browser
session its own client instead of caching one globally.
"""
import uuid
from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client

from . import config


# ---------------------------------------------------------------- client
@st.cache_resource
def client() -> Client:
    if not config.supabase_ready():
        raise RuntimeError("Supabase secrets missing — fill .streamlit/secrets.toml")
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


# ---------------------------------------------------------------- auth
def sign_up(email: str, password: str):
    return client().auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str):
    return client().auth.sign_in_with_password({"email": email, "password": password})


def sign_out():
    try:
        client().auth.sign_out()
    except Exception:
        pass


def current_user():
    try:
        return client().auth.get_user().user
    except Exception:
        return None


# ---------------------------------------------------------------- profile
def ensure_profile(user_id: str, display_name: str = ""):
    c = client()
    existing = c.table("profiles").select("id").eq("id", user_id).execute().data
    if not existing:
        c.table("profiles").insert(
            {"id": user_id, "display_name": display_name}
        ).execute()
    return c.table("profiles").select("*").eq("id", user_id).single().execute().data


def update_profile(user_id: str, fields: dict):
    """Patch profile settings (exam dates, daily limits, goal minutes)."""
    fields = {k: v for k, v in fields.items() if v is not None}
    if fields:
        client().table("profiles").update(fields).eq("id", user_id).execute()


# ---------------------------------------------------------------- cards
def get_cards(user_id: str) -> list[dict]:
    return (
        client().table("cards").select("*")
        .eq("owner_id", user_id).eq("is_active", True)
        .execute().data
    )


def get_card_states(user_id: str) -> dict[str, dict]:
    rows = client().table("card_states").select("*").eq("user_id", user_id).execute().data
    return {r["card_id"]: r for r in rows}


def upsert_cards(rows: list[dict]):
    """Insert/overwrite cards (used by the seed importer)."""
    if rows:
        client().table("cards").upsert(rows).execute()


def save_card_state(user_id: str, card_id: str, fsrs_dict: dict, reps: int):
    client().table("card_states").upsert({
        "user_id": user_id,
        "card_id": card_id,
        "fsrs": fsrs_dict,
        "due": fsrs_dict["due"],
        "last_review": datetime.now(timezone.utc).isoformat(),
        "stability": fsrs_dict.get("stability"),
        "state": fsrs_dict.get("state"),
        "reps": reps,
    }).execute()


# ---------------------------------------------------------------- reviews / sessions
def log_review(user_id, card_id, session_id, rating, elapsed_ms) -> int | None:
    res = client().table("reviews").insert({
        "user_id": user_id, "card_id": card_id, "session_id": session_id,
        "rating": rating, "elapsed_ms": elapsed_ms,
    }).execute()
    return res.data[0]["id"] if res.data else None


def save_answer(user_id, card_id, review_id, answer_text, grade: dict):
    """Persist a free-text answer + Claude's mark (used in Deep/AI mode)."""
    client().table("answers").insert({
        "user_id": user_id,
        "card_id": card_id,
        "review_id": review_id,
        "answer_text": answer_text,
        "ai_score": grade.get("score"),
        "ai_max": grade.get("max"),
        "ai_feedback": grade.get("feedback"),
        "missed_points": grade.get("missed_points"),
        "misconceptions": grade.get("misconceptions"),
        "suggested_rating": grade.get("suggested_rating"),
    }).execute()


def start_session(user_id: str, deck: str = "all") -> str:
    res = client().table("sessions").insert(
        {"user_id": user_id, "deck": deck}
    ).execute()
    return res.data[0]["id"]


def end_session(session_id: str, duration_ms: int, cards_done: int):
    client().table("sessions").update({
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms, "cards_done": cards_done,
    }).eq("id", session_id).execute()


# ---------------------------------------------------------------- M3: weak patterns
def get_recent_answers(user_id: str, limit: int = 50) -> list[dict]:
    """Recent AI-marked answers, each enriched with the card's topic/module."""
    rows = (
        client().table("answers").select("*, cards(topic, module)")
        .eq("user_id", user_id).order("graded_at", desc=True).limit(limit)
        .execute().data
    )
    for r in rows:
        c = r.get("cards") or {}
        r["topic"] = c.get("topic")
        r["module"] = c.get("module")
    return rows


def get_reviews(user_id: str) -> list[dict]:
    """All review events, each enriched with the card's topic/module (for reports)."""
    rows = (
        client().table("reviews").select("*, cards(topic, module)")
        .eq("user_id", user_id).order("reviewed_at").execute().data
    )
    for r in rows:
        c = r.get("cards") or {}
        r["topic"] = c.get("topic")
        r["module"] = c.get("module")
    return rows


def get_weak_patterns(user_id: str, only_open: bool = False) -> list[dict]:
    q = client().table("weak_patterns").select("*").eq("user_id", user_id)
    if only_open:
        q = q.neq("status", "resolved")
    return q.order("severity", desc=True).execute().data


def upsert_weak_pattern(user_id: str, p: dict):
    row = {
        "user_id": user_id, "topic": p.get("topic"), "label": p["label"],
        "description": p.get("description"), "severity": p.get("severity", 2),
        "status": p.get("status", "open"),
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    if p.get("id"):
        client().table("weak_patterns").update(row).eq("id", p["id"]).execute()
    else:
        client().table("weak_patterns").insert(row).execute()


def insert_followup_cards(user_id: str, cards: list[dict], topic_module: dict) -> int:
    """Insert AI-generated follow-up cards. They have no card_state, so they
    surface as 'new' in the queue (and in the 'Targeted follow-ups' deck)."""
    rows = []
    for c in cards:
        topic = c.get("topic") or "Targeted practice"
        rows.append({
            "id": "ai_" + uuid.uuid4().hex[:10],
            "topic": topic,
            "module": topic_module.get(topic),
            "type": c.get("type", "concept"),
            "front": c["front"],
            "model_answer": c["model_answer"],
            "mark_scheme": c.get("mark_scheme"),
            "max_marks": c.get("max_marks", 3),
            "source": "ai_followup",
            "owner_id": user_id,
            "is_active": True,
        })
    if rows:
        client().table("cards").upsert(rows).execute()
    return len(rows)
