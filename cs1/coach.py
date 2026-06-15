"""Weak-area analysis runner — shared by the Weak Areas page and the automatic
post-session refresh, so the dashboard's weak points stay current without a click.
"""
import streamlit as st
from . import db, ai

MIN_ANSWERS = 3  # need at least this many marked answers for a useful analysis


def run_analysis(uid: str) -> dict:
    """Analyse recent marked answers, persist patterns + follow-up cards.
    Returns {"ok": bool, "count": n, "result": {...}, "followups": n}.
    """
    answers = db.get_recent_answers(uid, limit=50)
    if len(answers) < MIN_ANSWERS:
        return {"ok": False, "count": len(answers)}
    cards = db.get_cards(uid)
    topic_names = sorted({c["topic"] for c in cards})
    topic_module = {c["topic"]: c.get("module") for c in cards}
    open_patterns = db.get_weak_patterns(uid, only_open=True)
    result = ai.find_weak_patterns(answers, open_patterns, topic_names)
    for p in result.get("patterns", []):
        db.upsert_weak_pattern(uid, p)
    n = db.insert_followup_cards(uid, result.get("followup_cards", []), topic_module)
    st.session_state["wa_last_count"] = len(answers)
    return {"ok": True, "count": len(answers), "result": result, "followups": n}


def maybe_autorun(uid: str) -> dict | None:
    """Run the analysis automatically only if AI is on and there are *new* marked
    answers since the last run (so Fast-only sessions don't trigger it)."""
    if not ai.available():
        return None
    answers = db.get_recent_answers(uid, limit=50)
    if len(answers) < MIN_ANSWERS or len(answers) <= st.session_state.get("wa_last_count", -1):
        return None
    try:
        out = run_analysis(uid)
    except Exception:
        return None
    return out if out.get("ok") else None
