"""Study Plan page.

Answers three questions every time you open it:
  1. Am I on track to cover everything before the exam?  (status + behind-by)
  2. What should I do TODAY?                              (due + new, by topic)
  3. What's the schedule from here to the exam?           (forecast + coverage)
"""
from datetime import date
import pandas as pd
import streamlit as st

from cs1 import db, auth, plan, config

st.set_page_config(page_title="Plan - CS1", page_icon="📅", layout="wide")
uid = auth.require_login()
auth.logout_button()

st.title("📅 Study Plan")

profile = db.ensure_profile(uid)
cards = config.scope_cards(db.get_cards(uid))   # exam questions by default
states = db.get_card_states(uid)
reviews = db.get_reviews(uid)

if not cards:
    st.info("No exam questions yet. On the Home page, import them "
            "(*Add / update past-paper-style questions*), then come back here.")
    st.stop()

P = plan.compute(profile, cards, states, reviews)
cards_by_id = {c["id"]: c for c in cards}

# ================================================================ headline KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Days to CS1A", P["days_to_exam"], help=f"Exam: {P['exam_a']:%d %b %Y}")
k2.metric("Cards covered", f"{P['seen']} / {P['total']}",
          help="Cards you've seen at least once (first pass).")
k3.metric("Finish first pass by", f"{P['coverage_target']:%d %b}",
          help="Every card seen once by this date — then it's pure revision to the exam.")
if P["on_track"]:
    k4.metric("Status", "On track ✅")
else:
    k4.metric("Status", f"Behind {P['behind_cards']}", delta=f"-{P['behind_cards']} cards",
              delta_color="inverse")

# ================================================================ status banner
if P["on_track"]:
    st.success("**You're on track.** Keep doing today's plan below and every topic will be "
               f"covered with three weeks to spare before CS1A.")
else:
    bits = []
    if P["overdue"]:
        bits.append(f"**{P['overdue']} review(s) overdue** (oldest {P['oldest_overdue']}d) — "
                    "these are cards FSRS wanted you to revise earlier.")
    if P["coverage_gap"]:
        bits.append(f"**{P['coverage_gap']} card(s) behind on coverage** "
                    f"(~{P['coverage_days_behind']} day(s) of slippage) — you've seen "
                    f"{P['seen']} of {P['total']}, the pace wants ~{P['expected_seen']} by now.")
    st.warning("**A bit behind:** " + "  \n".join(bits))
    if P["catch_up"]:
        st.markdown("**Catch-up plan:** " + P["catch_up"])
    if P["at_risk"]:
        st.error(f"⏰ **At risk:** even at your daily maximum of {P['daily_new_cap']} new/day you "
                 f"can't see all {P['unseen']} remaining cards by {P['coverage_target']:%d %b} "
                 f"(you'd need {P['raw_target']}/day). Raise the daily maximum below, or accept "
                 "first-pass finishing a little closer to the exam.")

st.divider()

# ================================================================ TODAY
left, right = st.columns([1, 1])

with left:
    st.subheader("Do today")
    t1, t2, t3 = st.columns(3)
    t1.metric("Reviews due", P["due_today"])
    t2.metric("New to add", P["new_remaining_target"],
              help="Recommended new cards to introduce today to stay on track.")
    t3.metric("New done today", P["new_today_done"])
    if P["due_today"] + P["new_remaining_target"] == 0:
        st.success("Nothing required today — you're ahead. Studying more is optional.")
    else:
        st.markdown(f"**Target:** clear **{P['due_today']}** due + add **{P['new_remaining_target']}** new.")
    st.page_link("pages/1_📚_Study.py", label="▶ Start today's session", icon="📚")
    st.caption(f"Daily new-card maximum: {P['daily_new_cap']} "
               f"(raise it below if you want to push faster).")

with right:
    st.subheader("Today's cards, by topic")
    # due cards + the next N new cards the plan introduces today
    due_cards = [cards_by_id[c] for c in P["due_ids"] if c in cards_by_id]
    new_cards = [cards_by_id[c] for c in P["unseen_ids"][:P["new_remaining_target"]] if c in cards_by_id]
    todays = [("review", c) for c in due_cards] + [("new", c) for c in new_cards]
    if not todays:
        st.caption("No cards queued for today.")
    else:
        by_topic: dict[str, list] = {}
        for kind, c in todays:
            by_topic.setdefault(c.get("topic", "—"), []).append((kind, c))
        for topic in sorted(by_topic):
            items = by_topic[topic]
            with st.expander(f"{topic}  ·  {len(items)} card(s)", expanded=len(by_topic) <= 3):
                for kind, c in items:
                    tag = "🆕" if kind == "new" else "🔁"
                    st.markdown(f"{tag} {c['front']}", unsafe_allow_html=True)

st.divider()

# ================================================================ COVERAGE
st.subheader("Coverage by module")
st.caption("Are all the important areas getting covered? Progress = cards seen at least once.")
mcols = st.columns(len(P["modules"]) or 1)
for col, m in zip(mcols, P["modules"]):
    pct = round(100 * m["seen"] / m["total"]) if m["total"] else 0
    col.markdown(f"**M{m['module']} · {m['name']}**")
    col.progress(pct / 100, text=f"{m['seen']}/{m['total']} seen · {m['due']} due · {m['new']} new")

with st.expander("Full coverage checklist (every topic & its status)"):
    tdf = pd.DataFrame([{
        "Module": r["module"], "Topic": r["topic"],
        "Seen": f"{r['seen']}/{r['total']}",
        "Due now": r["due"], "Not yet seen": r["new"],
        "Covered %": round(100 * r["seen"] / r["total"]) if r["total"] else 0,
    } for r in P["topics"]])
    st.dataframe(tdf, use_container_width=True, hide_index=True)

st.divider()

# ================================================================ FORECAST
st.subheader("The next two weeks")
fdf = pd.DataFrame([{
    "Date": f["date"].strftime("%a %d %b"),
    "New cards": f["new"], "Reviews due": f["reviews"], "Total": f["total"],
} for f in P["forecast"]])
fc1, fc2 = st.columns([2, 1])
with fc1:
    st.dataframe(fdf, use_container_width=True, hide_index=True, height=320)
with fc2:
    st.metric("Recommended new / day", P["daily_new_target"],
              help="Introduce at least this many new cards a day to finish the first pass on time.")
    st.caption("Today's row shows your *real* remaining workload. Future 'Reviews due' counts are "
               "a **lower bound** — each card you grade schedules more repetitions, so later days "
               "will fill in as you study. See **Reports** for the full due-load chart to the exam.")
    st.page_link("pages/3_📊_Reports.py", label="Open Reports", icon="📊")

st.divider()

# ================================================================ SETTINGS
with st.expander("⚙️ Plan settings"):
    st.caption("These drive the whole plan. Changes save to your profile and recompute instantly.")
    s1, s2 = st.columns(2)
    with s1:
        new_exam = st.date_input("CS1A exam date", value=P["exam_a"])
    with s2:
        new_cap = st.number_input("Daily new-card maximum", min_value=1, max_value=100,
                                  value=int(P["daily_new_cap"]), step=1)
    st.caption(f"First-pass coverage deadline is automatically {plan.COVERAGE_BUFFER_DAYS} days "
               f"before the exam (currently {P['coverage_target']:%d %b %Y}).")
    if st.button("Save plan settings", type="primary"):
        db.update_profile(uid, {
            "exam_date_a": new_exam.isoformat(),
            "daily_new_limit": int(new_cap),
        })
        st.success("Saved. Recomputing…")
        st.rerun()
