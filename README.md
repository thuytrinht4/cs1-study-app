# CS1 Study Trainer — M0–M4

A working app from the spec in `../CS1 Study App - Build Spec.md`.
It now does **M0** (login + cloud connection + Claude ping), **M1** (import your
73-card deck, FSRS-scheduled daily study loop with self-grading and time logging),
**M2** (Deep mode: type an answer, Claude marks it — score, what you missed,
misconceptions — then you confirm the grade), **M3** (Weak Areas: Claude reviews
your marked answers, finds recurring weaknesses per topic, and auto-generates
targeted follow-up cards) and **M4** (Reports: time, accuracy trend, mastery by
module, and a due-card forecast to the exam). Only deployment (M5) remains.

**The improvement loop:** study in Deep mode → answers get marked & stored →
open **Weak Areas** and "Run analysis" → Claude logs your weak patterns and
generates targeted cards → study the **"Targeted follow-ups (AI)"** deck.

**Two study modes** (toggle in the Study sidebar):
- *Fast (self-grade)* — reveal & rate yourself. No API, free.
- *Deep (AI marking)* — type your answer; Claude grades it. Needs an
  `ANTHROPIC_API_KEY` in secrets (only this mode costs anything; ~cents).

## Run it in ~15 minutes

```bash
# 1. from this folder, create an environment and install
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# 2. set up Supabase
#    - create a free project at supabase.com
#    - SQL Editor -> paste schema.sql -> Run
#    - Settings -> API -> copy Project URL + anon public key

# 3. add secrets
mkdir .streamlit
copy secrets.toml.example .streamlit\secrets.toml   # Windows (use cp on mac/linux)
#    then edit .streamlit/secrets.toml and paste your SUPABASE_URL + SUPABASE_ANON_KEY
#    (leave ANTHROPIC_API_KEY blank for now — not needed until M2)

# 4. launch
streamlit run app.py
```

In the browser: create an account → log in → "Import starter deck" → **Start studying**.

> Tip: in Supabase, Authentication → Providers → Email, you can turn **off**
> "Confirm email" while developing so sign-up logs you straight in.

## What each file does
- `app.py` — Home: secrets check, login, first-run seed import, dashboard (due/new/countdown), M0 Claude ping.
- `pages/1_📚_Study.py` — the daily study loop (queue, reveal, grade, schedule, log time).
- `cs1/config.py` — reads secrets/env.
- `cs1/db.py` — all Supabase queries + auth.
- `cs1/scheduler.py` — FSRS wrapper (verified vs fsrs 6.3.1).
- `cs1/seed.py` — imports `data/seed_cards.json`.
- `cs1/auth.py` — Streamlit login helpers.
- `cs1/ai.py` — Claude calls: `grade_answer()` (Haiku, M2) + `find_weak_patterns()` (Sonnet, M3), both via tool-use structured output.
- `pages/2_🎯_Weak_Areas.py` — run analysis, view weaknesses + coaching note, jump to targeted practice. **(M3)**
- `pages/3_📊_Reports.py` — minutes/day vs goal, accuracy trend, time by topic, mastery by module, due-card forecast. **(M4)**
- `pages/4_📅_Plan.py` — deadline-aware study plan: today's task list by topic, coverage to the exam, a "behind by" meter, and a 14-day forecast.
- `pages/5_🧭_Method.py` — exam method & answer-planning guide: the 5-step method, time budget, and per-topic answer skeletons/mnemonics.
- `cs1/plan.py` — pure planning logic on top of FSRS: adaptive new-card target, coverage tracking, behind-ness, forecast.
- `data/exam_cards.json` — 13 past-paper-style, multi-part exam questions with full model answers + mark schemes (import from Home; study via the "Exam-style questions" deck). Mark schemes also sharpen the AI marking.
- `schema.sql` — database tables + row-level security.

## Next milestone
- **M5** polish + deploy to Streamlit Community Cloud (push to GitHub, paste secrets into the Cloud secrets box). See the build spec §9.

See the build spec for prompts, schemas and detail.

## Known simplifications (intentional for the skeleton)
- One cached Supabase client (fine for personal use; namespace per session for true multi-user).
- "New cards per day" is capped per session rather than per calendar day — tighten in M4.
- Card LaTeX renders via Streamlit markdown; a few mixed HTML+math cards may need a small render helper later.
