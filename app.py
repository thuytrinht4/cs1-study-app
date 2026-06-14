"""CS1 Study App — Home / Dashboard (Milestone M0 + M1 entry point).

Run:  streamlit run app.py
"""
from datetime import date, datetime, timezone
import streamlit as st

from cs1 import config, db, seed, auth

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
now = datetime.now(timezone.utc)
due = sum(1 for c in cards if c["id"] in states
          and datetime.fromisoformat(states[c["id"]]["due"]) <= now)
new = sum(1 for c in cards if c["id"] not in states)

exam_a = profile.get("exam_date_a") or "2026-09-18"
days_to_a = (date.fromisoformat(str(exam_a)) - date.today()).days

c1, c2, c3 = st.columns(3)
c1.metric("Due now", due)
c2.metric("New available", new)
c3.metric("Days to CS1A", days_to_a)

st.divider()
st.markdown("### Today")
if due + new > 0:
    st.markdown(f"You have **{due} due** and up to **{min(new, profile.get('daily_new_limit', 18))} new** cards.")
    st.page_link("pages/1_📚_Study.py", label="▶ Start studying", icon="📚")
else:
    st.success("Nothing due right now — great. New cards unlock as you go.")

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
