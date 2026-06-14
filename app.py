"""CS1 Study App — Home / Dashboard (Milestone M0 + M1 entry point).

Run:  streamlit run app.py
"""
import streamlit as st

from cs1 import config, db, seed, auth, plan, ai

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

# ---------------------------------------------------------------- exam practice
st.divider()
st.markdown("### Exam practice")
xc1, xc2 = st.columns(2)
xc1.page_link("pages/6_📝_Mock.py", label="📝 Take a timed mock exam", icon="📝")
xc2.page_link("pages/5_🧭_Method.py", label="🧭 Exam method & answer planning", icon="🧭")

n_bank = sum(1 for c in cards if c.get("source") == "exam")
try:
    n_avail = len(seed.load_exam())
except Exception:
    n_avail = 0
with st.expander(f"➕ Add / update past-paper-style questions  ·  {n_bank} in your bank",
                 expanded=(n_bank == 0)):
    if n_bank < n_avail:
        st.write(f"**{n_avail - n_bank} new** built-in exam question(s) available ({n_avail} total) — "
                 "multi-part, worked model answers, mark schemes, weighted to GLMs, regression, "
                 "hypothesis testing and Bayesian.")
    else:
        st.write(f"All {n_avail} built-in exam questions are imported. Re-importing is harmless.")
    if st.button(f"Import / update exam questions ({n_avail})", type="primary"):
        with st.spinner("Importing…"):
            n = seed.import_exam(uid)
        st.success(f"Imported/updated {n} exam questions. Study them via the "
                   "'Exam-style questions' deck, or take a mock.")
        st.rerun()

    st.divider()
    if config.anthropic_ready():
        st.markdown("**🤖 Generate a brand-new question with AI**")
        topics = ["4.2 GLMs", "4.1 Linear regression", "3.3 Hypothesis testing",
                  "3.1 Estimation & MLE", "5.1 Bayesian statistics", "5.2 Credibility theory",
                  "2.1 Distributions", "3.2 Confidence intervals", "CS1B R — modelling"]
        gtopic = st.selectbox("Topic", topics, key="gen_topic")
        custom = st.text_input("…or type your own topic", key="gen_custom",
                               placeholder="e.g. Poisson GLM with an offset")
        if st.button("Generate exam question (AI)"):
            chosen = custom.strip() or gtopic
            with st.spinner(f"Claude is writing a '{chosen}' question…"):
                try:
                    q = ai.generate_exam_question(chosen)
                    db.insert_generated_card(uid, q)
                    st.success(f"Added a new {q.get('max_marks', '?')}-mark question on "
                               f"{q.get('topic', chosen)}. It's in the 'Exam-style questions' deck.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Generation failed: {e}")
    else:
        st.caption("Add an ANTHROPIC_API_KEY in Secrets to also generate brand-new questions on demand.")

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
