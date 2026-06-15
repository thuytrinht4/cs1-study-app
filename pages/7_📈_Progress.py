"""Progress page — your recall points and topic-strength heatmaps.

Answers: how much have I practised, how well (Good/Easy), which topics are now
strong (not weak), and which still need work before the exam.
"""
from datetime import timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cs1 import db, auth, progress

st.set_page_config(page_title="Progress - CS1", page_icon="📈", layout="wide")
uid = auth.require_login()
auth.logout_button()

st.title("📈 Progress & Heatmaps")

cards = db.get_cards(uid)
states = db.get_card_states(uid)
reviews = db.get_reviews(uid)
answers = db.get_answers(uid)

if not cards:
    st.info("Import your deck on the Home page first.")
    st.stop()

P = progress.compute(cards, states, reviews, answers)

# ================================================================ recall points
st.subheader("Recall points")
st.caption("Every grade scores: **Again 0 · Hard 1 · Good 2 · Easy 3** — in both Fast and Deep "
           "mode. Deep mode and mocks *also* earn real **exam marks** (Claude's score), shown "
           "below and folded into topic strength.")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Points today", P["points_today"])
k2.metric("Points (last 7 days)", P["points_7d"])
k3.metric("Total points", P["total_points"])
k4.metric("Day streak", f"{P['streak']} 🔥")
_goal = P["goal"]
st.progress(min(1.0, P["points_today"] / _goal) if _goal else 0.0,
            text=f"🎯 Daily goal: {P['points_today']} / {_goal} recall points"
                 + ("  ✅ reached!" if P["points_today"] >= _goal else ""))
if P["marks_possible"]:
    mk1, mk2 = st.columns(2)
    mk1.metric("Exam marks earned (AI/mock)", f"{P['marks_earned']} / {P['marks_possible']}")
    mk2.metric("AI mark accuracy", f"{P['ai_accuracy']}%",
               help="Average % of marks Claude awarded on your Deep-mode answers and mocks.")
rc = P["rating_counts"]
st.caption(f"Grades so far — Easy {rc[4]} · Good {rc[3]} · Hard {rc[2]} · Again {rc[1]}.  "
           f"Topic status: 🟢 {P['tally']['Strong']} strong · 🟡 {P['tally']['Developing']} developing · "
           f"🟠 {P['tally']['Weak']} weak · ⚪ {P['tally']['Not started']} not started.")

st.divider()

# ================================================================ topic strength heatmap
st.subheader("Topic strength — your heatmap")
st.caption("Strength blends coverage (cards seen) × quality (Good/Easy rate) × depth (practice). "
           "Green = strong (not a weak area); red = weak or untouched.")

rows = P["topic_rows"]
bar_df = pd.DataFrame([{"Topic": f"M{r['module']} · {r['topic']}", "Strength": r["strength"],
                        "Status": r["label"]} for r in rows])
bar_df = bar_df.sort_values("Strength")  # weakest at top
fig = px.bar(bar_df, x="Strength", y="Topic", orientation="h", range_x=[0, 100],
             color="Strength", color_continuous_scale="RdYlGn", range_color=[0, 100],
             text="Strength")
fig.update_layout(height=max(320, 22 * len(bar_df)), margin=dict(t=10, b=0, l=0, r=0),
                  coloraxis_showscale=False, yaxis_title="")
fig.update_traces(textposition="outside")
st.plotly_chart(fig, use_container_width=True)


def heat_css(v):
    """Red→amber→green background for a 0–100 value (no matplotlib needed)."""
    try:
        v = max(0, min(100, float(v))) / 100
    except (TypeError, ValueError):
        return ""
    if v < 0.5:
        t = v / 0.5
        r, g, b = 0.86, 0.30 + 0.55 * t, 0.30
    else:
        t = (v - 0.5) / 0.5
        r, g, b = 0.86 - 0.55 * t, 0.85 - 0.10 * t, 0.30
    return f"background-color: rgba({int(r*255)},{int(g*255)},{int(b*255)},0.85)"


with st.expander("Per-topic detail (coverage · practice · Good% · strength)", expanded=True):
    tdf = pd.DataFrame([{
        "Module": r["module"], "Topic": r["topic"],
        "Coverage %": r["coverage"], "Practice (reps)": r["reps"],
        "Good %": r["good_rate"],
        "AI mark %": (r["ai_pct"] if r["ai_pct"] is not None else "—"),
        "Strength": r["strength"], "Status": r["label"],
    } for r in rows])
    styled = tdf.style.applymap(heat_css, subset=["Coverage %", "Good %", "Strength"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=460)

st.divider()

# ================================================================ daily activity calendar
st.subheader("Daily practice — last 12 weeks")
st.caption("How much you practised each day (recall points). Darker = a heavier study day.")
if P["total_points"] == 0:
    st.info("No graded cards yet — study some cards (any mode) and your activity will fill in here.")
else:
    today = P["today"]
    start = today - timedelta(weeks=11)
    start -= timedelta(days=start.weekday())  # back to a Monday
    days = [start + timedelta(days=i) for i in range((today - start).days + 1)]
    recs = [{"week": (d - start).days // 7, "wd": d.weekday(), "date": d,
             "points": P["per_day"].get(d, {}).get("points", 0)} for d in days]
    cal = pd.DataFrame(recs)
    z = cal.pivot(index="wd", columns="week", values="points")
    txt = cal.pivot(index="wd", columns="week", values="date").astype(str)
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    xlabels = [(start + timedelta(weeks=w)).strftime("%d %b") for w in sorted(cal["week"].unique())]
    fig2 = go.Figure(go.Heatmap(
        z=z.values, x=xlabels, y=weekdays, colorscale="Greens", xgap=3, ygap=3,
        hovertext=txt.values, hovertemplate="%{hovertext}: %{z} pts<extra></extra>",
        colorbar=dict(title="pts")))
    fig2.update_yaxes(autorange="reversed")
    fig2.update_layout(height=260, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ================================================================ needs practice
st.subheader("⚠️ Needs practice before the exam")
needs = P["needs"]
if not needs:
    st.success("Every topic has been started and is at least developing — keep the reps up!")
else:
    st.caption("Weakest / untouched topics first. Drill these to turn red cells green.")
    ndf = pd.DataFrame([{"Module": r["module"], "Topic": r["topic"], "Status": r["label"],
                         "Coverage %": r["coverage"], "Good %": r["good_rate"],
                         "Strength": r["strength"]} for r in needs])
    st.dataframe(ndf, use_container_width=True, hide_index=True, height=min(420, 40 + 36 * len(ndf)))
    st.page_link("pages/1_📚_Study.py", label="▶ Go study (interleave the weak topics)", icon="📚")
