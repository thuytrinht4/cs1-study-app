"""Reports page (Milestone M4).

Turns your review/answer history into the numbers that predict your result:
time on task, accuracy trend, where your hours go, mastery by module, and a
due-card forecast to the exam so you don't get buried near September.
"""
from datetime import date, datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
import streamlit as st

from cs1 import db, auth, scheduler

st.set_page_config(page_title="Reports - CS1", page_icon="📊", layout="wide")
uid = auth.require_login()
auth.logout_button()

st.title("Progress & Reports")

profile = db.ensure_profile(uid)
goal_min = profile.get("daily_goal_min", 20)
exam_a = date.fromisoformat(str(profile.get("exam_date_a") or "2026-09-18"))

reviews = db.get_reviews(uid)
states = db.get_card_states(uid)
cards = db.get_cards(uid)

if not reviews:
    st.info("No study history yet. Do a few cards on the Study page, then come back — "
            "this page fills with your time, accuracy, mastery and a due-card forecast.")
    st.stop()

# ------------------------------------------------------------------ dataframe
df = pd.DataFrame(reviews)
df["reviewed_at"] = pd.to_datetime(df["reviewed_at"], utc=True, errors="coerce")
df["day"] = df["reviewed_at"].dt.date
df["minutes"] = df["elapsed_ms"].fillna(0) / 60000.0
df["good"] = df["rating"] >= 3

# ------------------------------------------------------------------ KPIs
def current_streak(days_set):
    d, n = date.today(), 0
    if d not in days_set and (d - timedelta(1)) in days_set:
        d = d - timedelta(1)            # allow "yesterday" so today isn't punished early
    while d in days_set:
        n += 1
        d -= timedelta(1)
    return n

days_studied = set(df["day"])
total_hours = df["minutes"].sum() / 60.0
mastered = sum(1 for s in states.values()
               if s.get("fsrs") and scheduler.retrievability(s["fsrs"]) >= 0.9
               and s.get("state") == 2)
days_left = (exam_a - date.today()).days

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total reviews", len(df))
k2.metric("Hours studied", f"{total_hours:.1f}")
k3.metric("Day streak", current_streak(days_studied))
k4.metric("Mastered cards", mastered)
k5.metric("Days to CS1A", days_left)

st.divider()

# ------------------------------------------------------------------ minutes/day vs goal
left, right = st.columns(2)
with left:
    st.subheader("Minutes per day")
    per_day = df.groupby("day")["minutes"].sum().reset_index()
    fig = px.bar(per_day, x="day", y="minutes", labels={"minutes": "minutes", "day": ""})
    fig.add_hline(y=goal_min, line_dash="dash", annotation_text=f"goal {goal_min}m")
    fig.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Accuracy trend (% Good or better)")
    acc = df.groupby("day")["good"].mean().reset_index()
    acc["pct"] = acc["good"] * 100
    fig2 = px.line(acc, x="day", y="pct", markers=True, labels={"pct": "% good+", "day": ""})
    fig2.update_yaxes(range=[0, 100])
    fig2.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------------------------------ time by topic + mastery
left2, right2 = st.columns(2)
with left2:
    st.subheader("Where your time goes (minutes by topic)")
    by_topic = (df.dropna(subset=["topic"]).groupby("topic")["minutes"].sum()
                .sort_values(ascending=True).reset_index())
    fig3 = px.bar(by_topic, x="minutes", y="topic", orientation="h",
                  labels={"minutes": "minutes", "topic": ""})
    fig3.update_layout(height=380, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig3, use_container_width=True)

with right2:
    st.subheader("Mastery by module")
    mod_of = {c["id"]: c.get("module") for c in cards}
    MOD = {1: "1 Data analysis", 2: "2 Probability", 3: "3 Inference",
           4: "4 Regression & GLM", 5: "5 Bayesian"}
    rows = []
    for m, name in MOD.items():
        ids = [c["id"] for c in cards if c.get("module") == m]
        if not ids:
            continue
        mast = 0
        for cid in ids:
            s = states.get(cid)
            if s and s.get("fsrs") and scheduler.retrievability(s["fsrs"]) >= 0.9 and s.get("state") == 2:
                mast += 1
        rows.append({"module": name, "mastered %": round(100 * mast / len(ids)),
                     "mastered": mast, "total": len(ids)})
    mdf = pd.DataFrame(rows)
    fig4 = px.bar(mdf, x="mastered %", y="module", orientation="h", range_x=[0, 100],
                  hover_data=["mastered", "total"], labels={"module": ""})
    fig4.update_layout(height=380, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig4, use_container_width=True)

# ------------------------------------------------------------------ due-load forecast
st.subheader(f"Due-card forecast to CS1A ({exam_a:%d %b %Y})")
today = date.today()
buckets = {}
overdue = 0
for s in states.values():
    try:
        d = datetime.fromisoformat(s["due"]).astimezone(timezone.utc).date()
    except Exception:
        continue
    if d < today:
        overdue += 1
    elif d <= exam_a:
        buckets[d] = buckets.get(d, 0) + 1
if overdue:
    st.caption(f"{overdue} cards are overdue right now — clear these first.")
if buckets:
    fdf = pd.DataFrame(sorted(buckets.items()), columns=["day", "cards due"])
    fig5 = px.bar(fdf, x="day", y="cards due", labels={"day": ""})
    fig5.update_layout(height=280, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig5, use_container_width=True)
else:
    st.caption("No future reviews scheduled yet — they appear as you grade cards.")
