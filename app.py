"""CS1 Study App — Home / Dashboard (Milestone M0 + M1 entry point).

Run:  streamlit run app.py
"""
import streamlit as st

from cs1 import config, db, seed, auth, plan

st.set_page_config(page_title="CS1 Study Trainer", page_icon="📘", layout="centered")
st.title("📘 CS1 Study Trainer")

# ---------------------------------------------------------------- M0: secrets check
if not config.supabase_ready():
    st.error("Supabase isn't configured yet.")
    st.markdown(
        "Create `.streamlit/secrets.toml` from `secrets.toml.example` and add your "
        "`SUPABASE_URL` and `SUPABASE_ANON_KEY`, then reload. "
        "Run `schema.sql` in your Supabase SQL editor first."
    )
    st.stop()

# ---------------------------------------------------------------- auth gate
if not auth.current_user_id():
    auth.login_form()
    st.stop()

uid = auth.current_user_id()
auth.logout_button()

# ---------------------------------------------------------------- first run: seed
if not seed.is_seeded(uid):
    st.info("Welcome! Let's load your starter deck of 73 cards.")
    if st.button("Import starter deck", type="primary"):
        with st.spinner("Importing…"):
            n = seed.import_seed(uid)
        st.success(f"Imported {n} cards. You're ready to study.")
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- dashboard
profile = db.ensure_profile(uid)
cards = db.get_cards(uid)
states = db.get_card_states(uid)
reviews = db.get_reviews(uid)
P = plan.compute(profile, cards, states, reviews)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Due now", P["due_today"])
c2.metric("New today", P["new_remaining_target"],
          help="Recommended new cards to add today to stay on track for full coverage.")
c3.metric("Covered", f"{P['seen']}/{P['total']}")
c4.metric("Days to CS1A", P["days_to_exam"])

# plan status — the "am I on track / how behind am I" answer
if P["on_track"]:
    st.success("✅ **On track.** Do today's plan and every topic is covered with three weeks "
               "to spare before the exam.")
else:
    msg = []
    if P["overdue"]:
        msg.append(f"{P['overdue']} review(s) overdue")
    if P["coverage_gap"]:
        msg.append(f"{P['coverage_gap']} card(s) behind on coverage (~{P['coverage_days_behind']}d)")
    st.warning("⚠️ **Behind by " + str(P["behind_cards"]) + " card(s):** " + " · ".join(msg)
               + ". Open the Plan for a catch-up.")

st.divider()
st.markdown("### Today")
if P["due_today"] + P["new_remaining_target"] > 0:
    st.markdown(f"Clear **{P['due_today']} due** and add **{P['new_remaining_target']} new** "
                f"(of {P['unseen']} still unseen).")
else:
    st.success("Nothing required today — you're ahead. Studying more is optional.")
pc1, pc2 = st.columns(2)
pc1.page_link("pages/1_📚_Study.py", label="▶ Start studying", icon="📚")
pc2.page_link("pages/4_📅_Plan.py", label="📅 See full plan to the exam", icon="📅")

# ---------------------------------------------------------------- M0 connectivity checks (optional)
with st.expander("Setup checks (M0)"):
    st.write(f"Supabase: connected · {len(cards)} cards in your bank")
    if config.anthropic_ready():
        if st.button("Ping Claude"):
            try:
                import anthropic
                cl = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                msg = cl.messages.create(
                    model=config.MODEL_MARKER, max_tokens=20,
                    messages=[{"role": "user", "content": "Reply with: ok"}],
                )
                st.success(f"Claude replied: {msg.content[0].text}")
            except Exception as e:
                st.error(f"Claude error: {e}")
    else:
        st.caption("Claude (AI marking) not configured — optional until Milestone M2. "
                   "Add ANTHROPIC_API_KEY to secrets when ready.")
