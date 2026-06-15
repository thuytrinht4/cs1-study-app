"""Weak Areas page (Milestone M3).

Runs Claude (Sonnet) over your recent AI-marked answers to find recurring
weaknesses per topic, then auto-generates targeted follow-up cards that enter
your queue. Study them via the 'Targeted follow-ups (AI)' deck on the Study page.
"""
import streamlit as st
from cs1 import db, auth, ai, coach

st.set_page_config(page_title="Weak Areas - CS1", page_icon="🎯", layout="centered")
uid = auth.require_login()
auth.logout_button()

st.title("Weak Areas")
st.caption("Claude analyses your marked answers, finds what keeps costing you marks, "
           "and builds targeted practice for exactly those gaps.")

SEV = {3: "🔴 high", 2: "🟠 medium", 1: "🟡 low"}

# ---------------------------------------------------------------- run analysis
if not ai.available():
    st.warning("AI analysis needs an ANTHROPIC_API_KEY in .streamlit/secrets.toml "
               "(same key as Deep marking). Add it, then reload.")
else:
    col1, col2 = st.columns([1, 2])
    with col1:
        run = st.button("Run analysis now", type="primary")
    with col2:
        st.caption("Uses your recent answers. Best after you've done some Deep-mode marking.")

    if run:
        with st.spinner("Claude is analysing your answers…"):
            try:
                out = coach.run_analysis(uid)
            except Exception as e:
                out = None
                st.error(f"Analysis failed: {e}")
        if out and not out["ok"]:
            st.info(f"Only {out['count']} marked answers so far. Do a few cards in "
                    "Deep (AI marking) mode first, then run this for useful patterns.")
        elif out and out["ok"]:
            result = out["result"]
            st.session_state["coaching_note"] = result.get("coaching_note", "")
            st.session_state["last_followups"] = out["followups"]
            st.success(f"Analysis done. {len(result.get('patterns', []))} patterns updated, "
                       f"{out['followups']} targeted cards generated.")

# ---------------------------------------------------------------- coaching note
if st.session_state.get("coaching_note"):
    st.info("**Coach:** " + st.session_state["coaching_note"])

# ---------------------------------------------------------------- current patterns
st.divider()
st.subheader("Your open weaknesses")
patterns = db.get_weak_patterns(uid, only_open=True)
if not patterns:
    st.write("None recorded yet — run an analysis after some Deep-mode practice.")
else:
    for p in patterns:
        with st.container(border=True):
            st.markdown(f"**{p.get('label','')}**  ·  {p.get('topic','')}  ·  "
                        f"{SEV.get(p.get('severity', 2), '')}  ·  _{p.get('status','open')}_")
            if p.get("description"):
                st.write(p["description"])

# ---------------------------------------------------------------- study link
st.divider()
n_follow = sum(1 for c in db.get_cards(uid) if c.get("source") == "ai_followup")
st.markdown(f"**{n_follow}** targeted follow-up cards in your bank.")
st.page_link("pages/1_📚_Study.py", label="Study them (pick the 'Targeted follow-ups (AI)' deck)", icon="📚")
