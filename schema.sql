-- =====================================================================
--  CS1 Study App — Supabase / Postgres schema  (M0/M1 version)
--  Run once: Supabase -> SQL Editor -> New query -> paste -> Run.
--  Simplified for the starter skeleton: cards carry their topic as text
--  (no separate topics table needed yet) and the FSRS state is stored as
--  a JSON blob so it survives library version changes.
-- =====================================================================

-- ---------- PROFILE (extends Supabase auth.users) ----------
create table if not exists profiles (
  id              uuid primary key references auth.users(id) on delete cascade,
  display_name    text,
  exam_date_a     date default '2026-09-18',
  exam_date_b     date default '2026-09-22',
  daily_new_limit int  default 18,
  daily_goal_min  int  default 20,
  created_at      timestamptz default now()
);

-- ---------- CARDS (question bank; owned by the user who imports them) ----------
create table if not exists cards (
  id              text primary key,        -- e.g. '4.2a'  (namespace per user if you go multi-user)
  topic           text not null,           -- e.g. '4.2 GLMs'
  module          int,                     -- 1..5
  type            text not null,           -- 'concept' | 'formula' | 'r'
  front           text not null,
  model_answer    text not null,
  mark_scheme     jsonb,                   -- [{point:'...', marks:1}] (added in Phase 5)
  max_marks       int  default 3,
  hint            text,
  source          text default 'seed',     -- 'seed' | 'user' | 'ai_followup'
  weak_pattern_id uuid,
  owner_id        uuid references auth.users(id),
  is_active       boolean default true,
  created_at      timestamptz default now()
);

-- ---------- CARD STATES (per user; drives the FSRS queue) ----------
create table if not exists card_states (
  user_id     uuid references auth.users(id) on delete cascade,
  card_id     text references cards(id) on delete cascade,
  fsrs        jsonb not null,              -- full fsrs Card.to_dict()
  due         timestamptz not null,        -- mirror of fsrs.due, for fast "what's due" queries
  last_review timestamptz,
  stability   double precision,            -- mirror, for mastery reports
  state       int,                         -- fsrs State int (1 Learning,2 Review,3 Relearning)
  reps        int default 0,
  primary key (user_id, card_id)
);
create index if not exists idx_card_states_due on card_states(user_id, due);

-- ---------- REVIEWS (one row per grade; time + accuracy log) ----------
create table if not exists reviews (
  id          bigserial primary key,
  user_id     uuid references auth.users(id) on delete cascade,
  card_id     text references cards(id),
  session_id  uuid,
  rating      int not null,                -- 1 Again | 2 Hard | 3 Good | 4 Easy
  elapsed_ms  int,
  reviewed_at timestamptz default now()
);
create index if not exists idx_reviews_user_time on reviews(user_id, reviewed_at);

-- ---------- ANSWERS (free-text, AI-graded — used from M2) ----------
create table if not exists answers (
  id             bigserial primary key,
  user_id        uuid references auth.users(id) on delete cascade,
  card_id        text references cards(id),
  review_id      bigint references reviews(id),
  answer_text    text,
  ai_score       numeric,
  ai_max         numeric,
  ai_feedback    text,
  missed_points  jsonb,
  misconceptions jsonb,
  suggested_rating int,
  graded_at      timestamptz default now()
);

-- ---------- SESSIONS (time tracking) ----------
create table if not exists sessions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  started_at  timestamptz default now(),
  ended_at    timestamptz,
  duration_ms bigint,
  cards_done  int default 0,
  deck        text
);

-- ---------- WEAK PATTERNS (AI-detected — used from M3) ----------
create table if not exists weak_patterns (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  topic       text,
  label       text not null,
  description text,
  severity    int default 2,
  evidence    jsonb,
  status      text default 'open',
  created_at  timestamptz default now(),
  last_seen   timestamptz default now()
);

-- =====================================================================
--  ROW-LEVEL SECURITY — each user only ever sees their own rows
-- =====================================================================
alter table profiles      enable row level security;
alter table cards         enable row level security;
alter table card_states   enable row level security;
alter table reviews       enable row level security;
alter table answers       enable row level security;
alter table sessions      enable row level security;
alter table weak_patterns enable row level security;

create policy "own profile"       on profiles      for all using (auth.uid() = id)      with check (auth.uid() = id);
create policy "own cards"         on cards         for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "own card_states"   on card_states   for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own reviews"       on reviews       for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own answers"       on answers       for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own sessions"      on sessions      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own weak_patterns" on weak_patterns for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
