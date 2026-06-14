"""Study page — the daily loop.

Two modes:
  - Fast (self-grade): reveal the answer and rate yourself. No API, free. (M1)
  - Deep (AI marking): type your answer; Claude scores it, shows what you
    missed, then you confirm the spaced-repetition grade. (M2)
"""
import time
from datetime import datetime, timezone
import streamlit as st

from cs1 import db, scheduler, auth, ai

st.set_page_config(page_title="Study - CS1", page_icon="📚", layout="centered")
uid = auth.require_login()
auth.logout_button()

st.title("Study")

DECKS = {
    "All cards": lambda c: True,
    "CS1A theory only": lambda c: c["type"] != "r",
    "CS1B R code only": lambda c: c["type"] == "r",
    "Module 1 - Data analysis": lambda c: c["module"] == 1 and c["type"] != "r",
    "Module 2 - Probability": lambda c: c["module"] == 2 and c["type"] != "r",
    "Module 3 - Inference": lambda c: c["module"] == 3 and c["type"] != "r",
    "Module 4 - Regression & GLM": lambda c: c["module"] == 4 and c["type"] != "r",
    "Module 5 - Bayesian": lambda c: c["module"] == 5 and c["type"] != "r",
    "Targeted follow-ups (AI)": lambda c: c.get("source") == "ai_followup",
}
NEW_LIMIT = 18

# ---------------------------------------------------------------- sidebar: mode
ai_on = ai.available()
mode = st.sidebar.radio(
    "Study mode",
    ["Fast (self-grade)", "Deep (AI marking)"],
    help="Deep mode lets you type an answer and have Claude mark it. "
         "Requires an Anthropic API key (Milestone M2).",
)
deep = mode.startswith("Deep")
if deep and not ai_on:
    st.sidebar.warning("Add ANTHROPIC_API_KEY to secrets to use AI marking. "
                       "Falling back to self-grade.")
    deep = False


def build_queue(deck_fn):
    cards = db.get_cards(uid)
    states = db.get_card_states(uid)
    now = datetime.now(timezone.utc)
    due, new = [], []
    for c in cards:
        if not deck_fn(c):
            continue
        s = states.get(c["id"])
        if s is None:
            new.append(c)
        elif datetime.fromisoformat(s["due"]) <= now:
            due.append(c)
    return due + new[:NEW_LIMIT], states


# ---------------------------------------------------------------- init / deck change
deck_name = st.selectbox("Deck", list(DECKS.keys()))
RESET_KEYS = ["queue", "cards_by_id", "states", "session_id", "session_start",
              "done", "revealed", "shown_at", "grade_result", "answer_text"]
if st.session_state.get("deck_name") != deck_name:
    for k in RESET_KEYS:
        st.session_state.pop(k, None)
    st.session_state["deck_name"] = deck_name

if "queue" not in st.session_state:
    queue, states = build_queue(DECKS[deck_name])
    st.session_state["queue"] = [c["id"] for c in queue]
    st.session_state["cards_by_id"] = {c["id"]: c for c in queue}
    st.session_state["states"] = states
    st.session_state["session_id"] = db.start_session(uid, deck_name)
    st.session_state["session_start"] = time.time()
    st.session_state["done"] = 0
    st.session_state["revealed"] = False
    st.session_state["shown_at"] = time.time()
    st.session_state["grade_result"] = None
    st.session_state["answer_text"] = ""

queue = st.session_state["queue"]

# ---------------------------------------------------------------- finished?
if not queue:
    mins = (time.time() - st.session_state.get("session_start", time.time())) / 60
    db.end_session(st.session_state.get("session_id"),
                   int(mins * 60_000), st.session_state.get("done", 0))
    st.success(f"Done! {st.session_state.get('done', 0)} cards in {mins:.0f} min.")
    st.balloons()
    if ai.available():
        st.page_link("pages/2_🎯_Weak_Areas.py",
                     label="Analyse my answers & generate targeted practice", icon="🎯")
    if st.button("Study more / rebuild queue"):
        for k in RESET_KEYS:
            st.session_state.pop(k, None)
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- current card
card = st.session_state["cards_by_id"][queue[0]]
is_new = card["id"] not in st.session_state["states"]

st.caption(f"{len(queue)} left - {card['topic']} - "
           f"{'new' if is_new else 'review'} - {card['type']} - {mode}")
st.markdown("#### " + card["front"], unsafe_allow_html=True)
if card.get("hint") and not st.session_state["revealed"]:
    st.caption("Hint: " + card["hint"])


def advance():
    st.session_state["queue"] = queue[1:]
    st.session_state["done"] += 1
    st.session_state["revealed"] = False
    st.session_state["shown_at"] = time.time()
    st.session_state["grade_result"] = None
    st.session_state["answer_text"] = ""
    st.rerun()


def grade(rating):
    elapsed_ms = int((time.time() - st.session_state["shown_at"]) * 1000)
    state = st.session_state["states"].get(card["id"])
    fsrs_dict = state["fsrs"] if state else scheduler.new_card()
    reps = (state["reps"] + 1) if state else 1
    updated = scheduler.review(fsrs_dict, rating, elapsed_ms)
    db.save_card_state(uid, card["id"], updated, reps)
    review_id = db.log_review(uid, card["id"], st.session_state["session_id"], rating, elapsed_ms)
    gr = st.session_state.get("grade_result")
    if gr:
        try:
            db.save_answer(uid, card["id"], review_id,
                           st.session_state.get("answer_text", ""), gr)
        except Exception as e:
            st.warning(f"Answer not saved (DB write failed: {e})")
    st.session_state["states"][card["id"]] = {
        "fsrs": updated, "due": updated["due"], "reps": reps}
    advance()


def grade_buttons(suggested=None):
    label = "**How well did you recall it?**"
    if suggested:
        label += f"  -  suggested: **{ai.RATING_LABEL.get(suggested, '')}**"
    st.markdown(label)
    cols = st.columns(4)
    for col, (r, lab) in zip(cols, [(1, "Again"), (2, "Hard"), (3, "Good"), (4, "Easy")]):
        star = "* " if r == suggested else ""
        if col.button(star + lab, key=f"grade_{r}"):
            grade(r)


# ---------------------------------------------------------------- DEEP (AI) mode
if deep:
    if not st.session_state["revealed"]:
        st.session_state["answer_text"] = st.text_area(
            "Type your answer (as you would in the exam):",
            value=st.session_state.get("answer_text", ""),
            height=160, key=f"ans_{card['id']}",
        )
        if st.button("Mark my answer", type="primary"):
            with st.spinner("Claude is marking..."):
                try:
                    st.session_state["grade_result"] = ai.grade_answer(
                        card, st.session_state["answer_text"])
                    st.session_state["revealed"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Marking failed: {e}")
        st.caption("Short on time? Switch to Fast mode in the sidebar.")
    else:
        gr = st.session_state["grade_result"] or {}
        st.metric("Score", f"{gr.get('score', 0)} / {gr.get('max', card.get('max_marks', 3))}")
        if gr.get("feedback"):
            st.info(gr["feedback"])
        if gr.get("missed_points"):
            st.markdown("**You missed:**")
            for p in gr["missed_points"]:
                st.markdown(f"- {p}")
        if gr.get("misconceptions"):
            st.markdown("**Watch out:**")
            for p in gr["misconceptions"]:
                st.markdown(f"- {p}")
        st.divider()
        st.markdown("**Model answer**")
        st.markdown(card["model_answer"], unsafe_allow_html=True)
        st.divider()
        grade_buttons(suggested=gr.get("suggested_rating"))

# ---------------------------------------------------------------- FAST mode
else:
    if not st.session_state["revealed"]:
        if st.button("Show answer", type="primary"):
            st.session_state["revealed"] = True
            st.rerun()
    else:
        st.divider()
        st.markdown(card["model_answer"], unsafe_allow_html=True)
        st.divider()
        grade_buttons()
