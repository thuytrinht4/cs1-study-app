"""Timed Mock Exam.

Assembles a paper from your exam-style questions, runs a countdown, lets you
write all answers, then marks the whole paper (Claude if available, else
self-mark against the model answers) and reports a total score and breakdown.
AI-marked answers are stored, so the mock also feeds Weak Areas and time reports.
"""
import time
import streamlit as st

from cs1 import db, auth, ai, scheduler

st.set_page_config(page_title="Mock Exam - CS1", page_icon="📝", layout="wide")
uid = auth.require_login()
auth.logout_button()

st.title("📝 Timed Mock Exam")

exam_cards = [c for c in db.get_cards(uid) if c.get("source") == "exam"]
cards_by_id = {c["id"]: c for c in exam_cards}
states = db.get_card_states(uid)
PASS_PCT = 60  # IFoA CS1 pass mark is around 60%

if not exam_cards:
    st.info("No exam-style questions in your bank yet. On the **Home** page, open "
            "*'Add / update past-paper-style questions'* and import them, then come back.")
    st.stop()


def assemble(paper: str):
    theory = sorted([c for c in exam_cards if c["type"] != "r"],
                    key=lambda c: (c.get("module") or 99, str(c["id"])))
    rcards = sorted([c for c in exam_cards if c["type"] == "r"],
                    key=lambda c: (c.get("module") or 99, str(c["id"])))
    if paper == "CS1A theory mock (all theory questions)":
        chosen, rate = theory, 2.0
    elif paper == "CS1B R mock (all R questions)":
        chosen, rate = rcards, 1.1
    else:  # quick mixed, ~30 marks
        chosen, rate, acc = [], 2.0, 0
        for c in theory + rcards:
            chosen.append(c)
            acc += c.get("max_marks", 0)
            if acc >= 30:
                break
    marks = sum(c.get("max_marks", 0) for c in chosen)
    minutes = max(5, round(marks * rate))
    return [c["id"] for c in chosen], marks, minutes


# ================================================================ SETUP
if "mock" not in st.session_state:
    st.caption("Pick a paper, start the clock, and write every answer from a blank page — "
               "closed-book, just like the real thing.")
    papers = ["Quick mock (~30 marks, mixed)",
              "CS1A theory mock (all theory questions)",
              "CS1B R mock (all R questions)"]
    paper = st.radio("Choose a paper", papers)
    ids, marks, minutes = assemble(paper)
    if not ids:
        st.warning("That paper has no questions yet — import more or pick another.")
        st.stop()
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions", len(ids))
    c2.metric("Total marks", marks)
    c3.metric("Time allowed", f"{minutes} min")
    st.caption(f"Marking guide: ~{'2.0' if 'R' not in paper else '1.1'} min/mark "
               f"(CS1A ≈ 2 min/mark; CS1B faster). Pass mark ≈ {PASS_PCT}%.")
    if not ai.available():
        st.info("No Anthropic key configured — the mock will run in **self-mark** mode "
                "(you score yourself against the model answers and mark schemes).")
    if st.button("▶ Start mock", type="primary"):
        st.session_state["mock"] = {
            "ids": ids, "marks": marks, "minutes": minutes,
            "paper": paper, "start": time.time(),
            "answers": {}, "submitted": False, "results": None,
        }
        st.rerun()
    st.stop()

mock = st.session_state["mock"]


def reset_mock():
    for k in list(st.session_state.keys()):
        if k == "mock" or k.startswith("mock_ans_") or k.startswith("selfmark_"):
            st.session_state.pop(k, None)


# ================================================================ ACTIVE (writing)
if not mock["submitted"]:
    def render_timer():
        m = st.session_state.get("mock")
        if not m or m["submitted"]:
            return
        remaining = m["minutes"] * 60 - (time.time() - m["start"])
        mm, ss = divmod(int(abs(remaining)), 60)
        if remaining >= 0:
            st.metric("⏱️ Time remaining", f"{mm:02d}:{ss:02d}")
        else:
            st.metric("⏱️ Time over by", f"{mm:02d}:{ss:02d}")
            st.warning("Time's up — finish your current point and submit.")

    top = st.columns([1, 2])
    with top[0]:
        if hasattr(st, "fragment"):
            st.fragment(run_every=15)(render_timer)()
        else:
            render_timer()
            st.caption("Timer updates when you interact with the page.")
    with top[1]:
        st.caption(f"**{mock['paper']}** · {len(mock['ids'])} questions · {mock['marks']} marks. "
                   "Answer in the boxes, then **Submit paper** at the bottom.")
        if st.button("✖ Abandon mock"):
            reset_mock()
            st.rerun()

    st.divider()
    with st.form("mock_form"):
        for idx, cid in enumerate(mock["ids"], 1):
            card = cards_by_id[cid]
            st.markdown(f"#### Q{idx}. {card['topic']} — {card.get('max_marks')} marks")
            with st.container(border=True):
                st.markdown(card["front"], unsafe_allow_html=True)
            st.text_area(f"Your answer to Q{idx}", key=f"mock_ans_{cid}", height=150,
                         label_visibility="collapsed", placeholder="Type your full answer here…")
            st.divider()
        submitted = st.form_submit_button("✅ Submit paper", type="primary")

    if submitted:
        mock["answers"] = {cid: st.session_state.get(f"mock_ans_{cid}", "") for cid in mock["ids"]}
        if ai.available():
            results, total, total_max = [], 0.0, 0.0
            prog = st.progress(0.0, text="Claude is marking your paper…")
            session_id = db.start_session(uid, "mock")
            for i, cid in enumerate(mock["ids"]):
                card = cards_by_id[cid]
                ans = mock["answers"].get(cid, "")
                try:
                    gr = ai.grade_answer(card, ans)
                except Exception as e:
                    gr = {"score": 0, "max": card.get("max_marks"), "feedback": f"(marking error: {e})",
                          "missed_points": [], "misconceptions": [], "suggested_rating": 1}
                mx = float(card.get("max_marks") or gr.get("max") or 0)
                sc = min(float(gr.get("score") or 0), mx)
                total += sc
                total_max += mx
                # store so the mock feeds Weak Areas + time reports, and schedules the card
                try:
                    rating = int(gr.get("suggested_rating") or 1)
                    state = states.get(cid)
                    fsrs_dict = state["fsrs"] if state else scheduler.new_card()
                    reps = (state.get("reps", 0) + 1) if state else 1
                    updated = scheduler.review(fsrs_dict, rating)
                    db.save_card_state(uid, cid, updated, reps)
                    rid = db.log_review(uid, cid, session_id, rating, None)
                    db.save_answer(uid, cid, rid, ans, gr)
                except Exception:
                    pass
                results.append({"cid": cid, "answer": ans, "grade": gr, "score": sc, "max": mx})
                prog.progress((i + 1) / len(mock["ids"]), text=f"Marked {i + 1}/{len(mock['ids'])}")
            db.end_session(session_id, int((time.time() - mock["start"]) * 1000), len(mock["ids"]))
            mock["results"] = {"mode": "ai", "items": results, "total": total, "total_max": total_max}
        else:
            mock["results"] = {"mode": "self"}
        mock["submitted"] = True
        st.rerun()
    st.stop()

# ================================================================ RESULTS
res = mock["results"]
elapsed_min = (time.time() - mock["start"]) / 60

if res and res.get("mode") == "ai":
    total, total_max = res["total"], res["total_max"]
    pct = round(100 * total / total_max) if total_max else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Score", f"{total:.0f} / {total_max:.0f}")
    k2.metric("Percentage", f"{pct}%")
    k3.metric("Result", "PASS ✅" if pct >= PASS_PCT else "Below pass")
    k4.metric("Time taken", f"{elapsed_min:.0f} / {mock['minutes']} min")
    if pct >= PASS_PCT:
        st.success(f"Above the ~{PASS_PCT}% pass mark. Now mine the lost marks below.")
    else:
        st.warning(f"Below the ~{PASS_PCT}% pass mark — the per-question breakdown shows exactly "
                   "where the marks went.")
    st.divider()
    st.subheader("Question-by-question")
    for idx, item in enumerate(res["items"], 1):
        card = cards_by_id[item["cid"]]
        gr = item["grade"]
        with st.expander(f"Q{idx}. {card['topic']} — {item['score']:.0f}/{item['max']:.0f}",
                         expanded=False):
            if gr.get("feedback"):
                st.info(gr["feedback"])
            if gr.get("missed_points"):
                st.markdown("**Missed:**")
                for p in gr["missed_points"]:
                    st.markdown(f"- {p}")
            st.markdown("**Your answer:**")
            st.markdown(f"> {item['answer'] or '(blank)'}")
            st.markdown("**Model answer:**")
            st.markdown(card["model_answer"], unsafe_allow_html=True)
    st.divider()
    if ai.available():
        st.page_link("pages/2_🎯_Weak_Areas.py",
                     label="🎯 Turn these mistakes into targeted practice (Run analysis)", icon="🎯")

else:
    # ---- self-mark mode: reveal answers, you award your own marks ----
    st.subheader("Self-mark against the model answers")
    st.caption("Award yourself marks for each question using its mark scheme, then read the total.")
    running = 0
    running_max = 0
    for idx, cid in enumerate(mock["ids"], 1):
        card = cards_by_id[cid]
        mx = int(card.get("max_marks", 0))
        running_max += mx
        with st.container(border=True):
            st.markdown(f"#### Q{idx}. {card['topic']} — {mx} marks")
            st.markdown("**Question:**")
            st.markdown(card["front"], unsafe_allow_html=True)
            st.markdown("**Your answer:**")
            st.markdown(f"> {st.session_state.get('mock_ans_' + cid, '') or '(blank)'}")
            st.markdown("**Model answer:**")
            st.markdown(card["model_answer"], unsafe_allow_html=True)
            ms = card.get("mark_scheme")
            if ms:
                st.markdown("**Mark scheme:**")
                for it in ms:
                    if isinstance(it, dict):
                        st.markdown(f"- **[{it.get('marks','')}]** {it.get('point','')}")
            running += st.number_input(f"Marks you earned on Q{idx}", min_value=0, max_value=mx,
                                       value=0, step=1, key=f"selfmark_{cid}")
    pct = round(100 * running / running_max) if running_max else 0
    st.divider()
    s1, s2, s3 = st.columns(3)
    s1.metric("Self-marked score", f"{running} / {running_max}")
    s2.metric("Percentage", f"{pct}%")
    s3.metric("Result", "PASS ✅" if pct >= PASS_PCT else "Below pass")

st.divider()
if st.button("🔄 New mock"):
    reset_mock()
    st.rerun()
