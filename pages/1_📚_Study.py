"""Study page — the daily loop.

Two modes:
  - Fast (self-grade): reveal the answer and rate yourself. No API, free. (M1)
  - Deep (AI marking): type your answer; Claude scores it, shows what you
    missed, then you confirm the spaced-repetition grade. (M2)
"""
import time
from datetime import datetime, timezone
import streamlit as st

from cs1 import db, scheduler, auth, ai, plan, coach, progress, config, schedule

st.set_page_config(page_title="Study - CS1", page_icon="📚", layout="centered")
uid = auth.require_login()
auth.logout_button()

st.title("Study")

DECKS = {
    "Exam-style questions": lambda c: c.get("source") == "exam",
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
TODAY_EXAM = "📝 Exam Qs — today's topics"  # dynamic deck (handled in build_queue)

# Anki-style in-session learning steps: a card you fail comes back THIS session,
# soon — Again very soon, Hard a bit later. Good/Easy graduate (leave the session;
# FSRS schedules their next day). This is what makes active recall actually bite.
REQUEUE_GAP = {1: 3, 2: 8}  # rating -> how many cards later it reappears

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


def build_queue(deck_name):
    cards = db.get_cards(uid)
    states = db.get_card_states(uid)
    reviews = db.get_reviews(uid)
    answers = db.get_answers(uid)
    profile = db.ensure_profile(uid)
    scoped = config.scope_cards(cards)                       # exam questions by default
    P = plan.compute(profile, scoped, states, reviews)
    PR0 = progress.compute(scoped, states, reviews, answers)  # today's points baseline
    cards_by_id = {c["id"]: c for c in cards}

    now = datetime.now(timezone.utc)

    def due_or_new(c):
        s = states.get(c["id"])
        return s is None or datetime.fromisoformat(s["due"]) <= now

    sched = schedule.for_date(plan.today_utc())   # the dated schedule drives today's focus
    note = None
    if deck_name == TODAY_EXAM:
        df = sched["deck_filter"]
        if df["kind"] == "r":
            def base(c):
                return c.get("source") == "exam" and c.get("type") == "r"
        elif df["kind"] == "module" and df["modules"]:
            mods = set(df["modules"])
            def base(c):
                return c.get("source") == "exam" and c.get("module") in mods
        else:
            def base(c):
                return c.get("source") == "exam"
        if any(due_or_new(c) for c in cards if base(c)):
            deck_fn = base
        else:  # nothing scheduled-topic available → fall back to all exam questions
            def deck_fn(c):
                return c.get("source") == "exam"
            note = (f"No exam questions for today's scheduled focus ({sched['focus']}) "
                    "— showing all your exam questions instead.")
        new_limit = 999
    else:
        deck_fn = DECKS[deck_name]
        # per-DAY new-card budget; AI-remediation & exam decks are exempt for free drilling
        if deck_name in ("Targeted follow-ups (AI)", "Exam-style questions"):
            new_limit = 999
        else:
            new_limit = P["new_remaining_cap"]

    due, new = [], []
    for c in cards:
        if not deck_fn(c):
            continue
        if states.get(c["id"]) is None:
            new.append(c)
        elif datetime.fromisoformat(states[c["id"]]["due"]) <= now:
            due.append(c)
    new.sort(key=lambda c: (c.get("module") or 99, str(c.get("id"))))
    queue_cards = due + new[:new_limit]
    extras = {"today_topics": [sched["focus"]], "pts_today_base": PR0["points_today"],
              "goal": PR0["goal"], "note": note,
              "sched_label": f"Day {sched['day']} · {sched['phase']}"}
    return queue_cards, states, P, extras


# ---------------------------------------------------------------- init / deck change
deck_name = st.selectbox("Deck", list(DECKS.keys()) + [TODAY_EXAM])
RESET_KEYS = ["queue", "cards_by_id", "states", "session_id", "session_start",
              "done", "revealed", "shown_at", "grade_result", "answer_text",
              "session_points", "session_good", "pts_today_base", "goal",
              "focus_topics", "goal_celebrated", "deck_note", "sched_label",
              "followup_chat"]
if st.session_state.get("deck_name") != deck_name:
    for k in RESET_KEYS:
        st.session_state.pop(k, None)
    st.session_state["deck_name"] = deck_name

if "queue" not in st.session_state:
    queue, states, P, extras = build_queue(deck_name)
    st.session_state["plan_snapshot"] = {
        "new_today_done": P["new_today_done"], "daily_new_cap": P["daily_new_cap"],
        "new_remaining_cap": P["new_remaining_cap"], "unseen": P["unseen"],
    }
    st.session_state["queue"] = [c["id"] for c in queue]
    st.session_state["cards_by_id"] = {c["id"]: c for c in queue}
    st.session_state["states"] = states
    st.session_state["session_id"] = db.start_session(uid, deck_name)
    st.session_state["session_start"] = time.time()
    st.session_state["done"] = 0
    st.session_state["session_points"] = 0
    st.session_state["session_good"] = 0
    st.session_state["pts_today_base"] = extras["pts_today_base"]
    st.session_state["goal"] = extras["goal"]
    st.session_state["focus_topics"] = extras["today_topics"]
    st.session_state["deck_note"] = extras.get("note")
    st.session_state["sched_label"] = extras.get("sched_label")
    st.session_state.pop("goal_celebrated", None)
    st.session_state["revealed"] = False
    st.session_state["shown_at"] = time.time()
    st.session_state["grade_result"] = None
    st.session_state["answer_text"] = ""
    st.session_state["followup_chat"] = []

queue = st.session_state["queue"]

# ---------------------------------------------------------------- finished?
if not queue:
    mins = (time.time() - st.session_state.get("session_start", time.time())) / 60
    db.end_session(st.session_state.get("session_id"),
                   int(mins * 60_000), st.session_state.get("done", 0))
    if st.session_state.get("deck_note"):
        st.info(st.session_state["deck_note"])
    if st.session_state.get("done", 0) == 0:
        # the deck was empty to begin with — not a completed session
        st.warning("No cards to study in this deck right now. "
                   "If you want exam questions, make sure you've imported them on the "
                   "**Home** page (click *Import / update exam questions* — there are new "
                   "ones available), or pick another deck above.")
        if st.button("🔄 Rebuild queue"):
            for k in RESET_KEYS:
                st.session_state.pop(k, None)
            st.rerun()
        st.stop()
    st.success(f"Done! {st.session_state.get('done', 0)} answers · "
               f"{st.session_state.get('session_good', 0)} Good/Easy · "
               f"+{st.session_state.get('session_points', 0)} points · {mins:.0f} min.")
    st.balloons()
    # auto-refresh weak areas once per session (only if new Deep-mode answers exist)
    sid = st.session_state.get("session_id")
    if ai.available() and st.session_state.get("autorun_for") != sid:
        st.session_state["autorun_for"] = sid
        with st.spinner("Updating your weak areas from this session…"):
            out = coach.maybe_autorun(uid)
        if out:
            st.success(f"🎯 Weak areas refreshed — {len(out['result'].get('patterns', []))} "
                       f"pattern(s), {out['followups']} new targeted card(s).")
    snap = st.session_state.get("plan_snapshot", {})
    if (deck_name != "Targeted follow-ups (AI)" and snap.get("new_remaining_cap") == 0
            and snap.get("unseen", 0) > 0):
        st.info(f"You've hit today's new-card limit ({snap.get('daily_new_cap')}). "
                f"{snap.get('unseen')} card(s) still to introduce overall — they'll unlock "
                "tomorrow. Want more now? Raise the daily maximum on the Plan page.")
    st.page_link("pages/4_📅_Plan.py", label="📅 See your plan & what's next", icon="📅")
    if ai.available():
        st.page_link("pages/2_🎯_Weak_Areas.py",
                     label="Analyse my answers & generate targeted practice", icon="🎯")
    if st.button("Study more / rebuild queue"):
        for k in RESET_KEYS:
            st.session_state.pop(k, None)
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- progress HUD (game)
def render_status():
    if st.session_state.get("deck_note"):
        st.caption("ℹ️ " + st.session_state["deck_note"])
    focus = st.session_state.get("focus_topics", [])
    if focus:
        lbl = st.session_state.get("sched_label", "")
        prefix = f"🗺️ {lbl} — " if lbl else ""
        st.markdown(f"🎯 **Today's focus:** {prefix}" + "  ·  ".join(focus[:4]))
    pts_today = st.session_state["pts_today_base"] + st.session_state["session_points"]
    goal = st.session_state.get("goal") or progress.DAILY_POINTS_GOAL
    elapsed = time.time() - st.session_state["session_start"]
    a, b, c, d = st.columns(4)
    a.metric("Answered", st.session_state["done"])
    b.metric("Good/Easy ✅", st.session_state["session_good"])
    c.metric("Points today", pts_today)
    d.metric("Time", f"{int(elapsed // 60)}m {int(elapsed % 60):02d}s")
    reached = pts_today >= goal
    st.progress(min(1.0, pts_today / goal) if goal else 0.0,
                text=(f"🎯 Daily goal {pts_today}/{goal} pts" + ("  ✅ reached!" if reached else "")))
    if reached and not st.session_state.get("goal_celebrated"):
        st.session_state["goal_celebrated"] = True
        st.balloons()
        st.toast("🎉 Daily goal reached — nice work!")


render_status()
st.divider()

# ---------------------------------------------------------------- current card
card = st.session_state["cards_by_id"][queue[0]]
is_new = card["id"] not in st.session_state["states"]

max_marks = card.get("max_marks")
marks_txt = f" - {max_marks} marks" if (card.get("source") == "exam" and max_marks) else ""
st.caption(f"{len(queue)} left - {card['topic']} - "
           f"{'new' if is_new else 'review'} - {card['type']}{marks_txt} - {mode}")
with st.container(border=True):
    st.markdown(card["front"], unsafe_allow_html=True)
if card.get("hint") and not st.session_state["revealed"]:
    st.caption("Hint: " + card["hint"])


def render_mark_scheme(card):
    """Show the per-point mark scheme on reveal (exam cards carry one)."""
    ms = card.get("mark_scheme")
    if not ms:
        return
    with st.expander("📋 Mark scheme — where the marks are", expanded=True):
        for item in ms:
            if isinstance(item, dict):
                st.markdown(f"- **[{item.get('marks', '')}]** {item.get('point', '')}")
            else:
                st.markdown(f"- {item}")


def render_followup(card):
    """Let the user ask Claude follow-up questions about this card (Deep mode)."""
    if not ai.available():
        return
    st.divider()
    st.markdown("**💬 Ask Claude a follow-up** (about this question, your answer, or the concept)")
    chat = st.session_state.get("followup_chat", [])
    for qa in chat:
        st.markdown(f"🧑 **You:** {qa['q']}")
        st.markdown(f"🤖 **Claude:** {qa['a']}")
    q = st.text_input("Your follow-up question:", key=f"fu_{card['id']}_{len(chat)}",
                      placeholder="e.g. Why do we use n−1, not n? / Show the R for this.")
    if st.button("Ask", key=f"ask_{card['id']}_{len(chat)}"):
        if q.strip():
            with st.spinner("Claude is answering…"):
                try:
                    a = ai.followup_answer(card, st.session_state.get("answer_text", ""),
                                           st.session_state.get("grade_result") or {}, q, chat)
                    chat.append({"q": q, "a": a})
                    st.session_state["followup_chat"] = chat
                    st.rerun()
                except Exception as e:
                    st.error(f"Follow-up failed: {e}")


def advance(requeue_id=None, gap=0):
    """Drop the current card; if requeue_id is given, re-insert it `gap` cards
    later so a failed card comes back THIS session (Anki-style learning steps)."""
    q = st.session_state["queue"][1:]
    if requeue_id is not None and requeue_id not in q:
        q.insert(min(len(q), gap), requeue_id)
    st.session_state["queue"] = q
    st.session_state["done"] += 1
    st.session_state["revealed"] = False
    st.session_state["shown_at"] = time.time()
    st.session_state["grade_result"] = None
    st.session_state["answer_text"] = ""
    st.session_state["followup_chat"] = []
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
    # gamification: rack up points; Good/Easy count as "passes"
    st.session_state["session_points"] += progress.points_for(rating)
    if rating >= 3:
        st.session_state["session_good"] += 1
    # Anki-style re-queue: Again/Hard come back this session; Good/Easy graduate
    advance(requeue_id=card["id"], gap=REQUEUE_GAP[rating]) if rating in REQUEUE_GAP else advance()


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
        render_mark_scheme(card)
        render_followup(card)
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
        st.markdown("**Model answer**")
        st.markdown(card["model_answer"], unsafe_allow_html=True)
        render_mark_scheme(card)
        render_followup(card)
        st.divider()
        grade_buttons()
