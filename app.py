"""CS1 Study App — Home / Dashboard (Milestone M0 + M1 entry point).

Run:  streamlit run app.py
"""
import streamlit as st

from cs1 import config, db, seed, auth, plan, ai, progress

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
uid = auth.ensure_session()          # auto-login if APP_EMAIL/APP_PASSWORD in secrets
if not uid:
    if config.autologin_ready() and st.session_state.get("autologin_error"):
        st.error("Auto-login failed — check APP_EMAIL / APP_PASSWORD in Secrets. "
                 f"({st.session_state['autologin_error']})")
    auth.login_form()
    st.stop()

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
answers = db.get_answers(uid)
scoped = config.scope_cards(cards)          # plan/progress over exam questions (default)
P = plan.compute(profile, scoped, states, reviews)

cards_by_id = {c["id"]: c for c in cards}
today = plan.today_utc()
days_to_b = (P["exam_b"] - today).days

# ---- days left, front and centre
st.markdown(f"## ⏳ {P['days_to_exam']} days to CS1A · {days_to_b} days to CS1B")
st.caption(f"CS1A (theory) {P['exam_a']:%a %d %b %Y} · CS1B (R) {P['exam_b']:%a %d %b %Y}  ·  "
           f"≈ {P['days_to_exam'] // 7} weeks left  ·  finish first pass by {P['coverage_target']:%d %b}")

# ---- on track / behind banner
if P["on_track"]:
    st.success("✅ **On track** — do today's plan and every topic is covered with three weeks to spare.")
else:
    msg = []
    if P["overdue"]:
        msg.append(f"{P['overdue']} review(s) overdue")
    if P["coverage_gap"]:
        msg.append(f"{P['coverage_gap']} behind on coverage (~{P['coverage_days_behind']}d)")
    st.warning(f"⚠️ **Behind by {P['behind_cards']} card(s):** " + " · ".join(msg)
               + ". Open the Plan for a catch-up.")

st.divider()

# ---- today's snapshot
todays_reviews = [r for r in reviews if plan._as_date(r.get("reviewed_at")) == today]
answered_today = len(todays_reviews)
topics_today = sorted({r.get("topic") for r in todays_reviews if r.get("topic")})
topics_total = len(P["topics"])
topics_started = sum(1 for t in P["topics"] if t["seen"] > 0)
topics_not_started = topics_total - topics_started
focus_ids = list(P["due_ids"]) + P["unseen_ids"][:max(P["new_remaining_target"], 1)]
focus_topics = sorted({cards_by_id[i]["topic"] for i in focus_ids if i in cards_by_id})

st.markdown("### Today")
if focus_topics:
    st.markdown("**Today's focus:** " + "  ·  ".join(focus_topics))
m1, m2, m3, m4 = st.columns(4)
m1.metric("Due now", P["due_today"])
m2.metric("Answered today", answered_today, help="Cards you've reviewed so far today.")
m3.metric("New to add", P["new_remaining_target"], help="Recommended new cards to add today.")
m4.metric("Topics not started", f"{topics_not_started}/{topics_total}",
          help="Syllabus topics with no card seen yet.")
if topics_today:
    st.caption("✅ Topics done today: " + ", ".join(topics_today))
PR = progress.compute(scoped, states, reviews, answers)
marks_txt = ""
if PR["marks_possible"]:
    marks_txt = (f"  ·  📝 exam marks **{PR['marks_earned']}/{PR['marks_possible']}** "
                 f"({PR['ai_accuracy']}%)")
st.markdown(f"**🔥 Recall points** — today **{PR['points_today']}** · 7 days **{PR['points_7d']}** · "
            f"total **{PR['total_points']}** · streak **{PR['streak']}d**{marks_txt}  ·  "
            f"topics 🟢{PR['tally']['Strong']} 🟡{PR['tally']['Developing']} "
            f"🟠{PR['tally']['Weak']} ⚪{PR['tally']['Not started']}")
_goal = PR["goal"]
st.progress(min(1.0, PR["points_today"] / _goal) if _goal else 0.0,
            text=f"🎯 Daily goal: {PR['points_today']} / {_goal} recall points"
                 + ("  ✅ reached!" if PR["points_today"] >= _goal else ""))
if P["due_today"] + P["new_remaining_target"] > 0:
    st.markdown(f"**Plan:** clear **{P['due_today']} due** + add **{P['new_remaining_target']} new**  "
                f"·  {P['seen']}/{P['total']} cards covered, {P['unseen']} unseen.")
else:
    st.success("Nothing required today — you're ahead. Studying more is optional.")
pc1, pc2, pc3 = st.columns(3)
pc1.page_link("pages/1_📚_Study.py", label="▶ Start studying", icon="📚")
pc2.page_link("pages/4_📅_Plan.py", label="📅 Full plan & task list", icon="📅")
pc3.page_link("pages/7_📈_Progress.py", label="📈 Progress & heatmaps", icon="📈")

# ---- weak points
st.divider()
st.markdown("### 🎯 Your weak points")
weak = db.get_weak_patterns(uid, only_open=True)
SEV = {3: "🔴 high", 2: "🟠 medium", 1: "🟡 low"}
if weak:
    for p in weak[:5]:
        st.markdown(f"- **{p.get('label', '')}**  ·  {p.get('topic', '')}  ·  "
                    f"{SEV.get(p.get('severity', 2), '')}")
    st.page_link("pages/2_🎯_Weak_Areas.py", label="See all weak areas & practise them", icon="🎯")
else:
    st.caption("None found yet — do some Deep-mode marking or a mock, then run "
               "Weak Areas → analysis to surface your recurring gaps.")
    st.page_link("pages/2_🎯_Weak_Areas.py", label="Open Weak Areas", icon="🎯")

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
