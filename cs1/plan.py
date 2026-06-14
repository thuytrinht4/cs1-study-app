"""Deadline-aware study plan, layered on top of FSRS.

WHY THIS EXISTS
FSRS decides *when to repeat* a card you have already seen, adapting to how
well you recall it. It does NOT plan *when to first introduce* the cards you
haven't seen yet, and it can't tell you whether you're on pace to have covered
the whole syllabus before the exam. This module adds that:

  * a daily "introduce this many new cards" TARGET that guarantees every card
    is seen at least once by `coverage_target` (default: 3 weeks before CS1A),
    leaving the run-up to the exam for pure revision;
  * TODAY's workload (reviews due + new to introduce), so nothing is missed;
  * a "BEHIND BY" measure = overdue repetitions + coverage shortfall, so if you
    skip a day or two you can see exactly how far behind you are;
  * a short forward FORECAST of daily load.

The target is ADAPTIVE: it is recomputed from (cards still unseen) / (days left
until the coverage date). Skip a day and the divisor shrinks, so the target
rises automatically to keep your finish date on track — but it is capped by the
per-day maximum (`daily_new_limit`) so it can never explode.

All instants are handled in UTC to match how `due` / `reviewed_at` are stored.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

# Leave this many days of pure revision before the exam: first-pass coverage
# (every card seen at least once) must finish this many days before CS1A.
# 21 = the "3 weeks before" plan. Change here if you want a different buffer.
COVERAGE_BUFFER_DAYS = 21
DEFAULT_DAILY_NEW_CAP = 18  # max new cards/day (anti-burnout); overridable per profile

MODULE_NAMES = {
    1: "Data analysis",
    2: "Probability & distributions",
    3: "Inference & hypothesis testing",
    4: "Regression & GLMs",
    5: "Bayesian statistics",
}


# ---------------------------------------------------------------- date helpers
def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _as_date(value) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


def first_seen_dates(reviews: list[dict]) -> dict[str, date]:
    """card_id -> date (UTC) of its first-ever review. Defines 'introduced'."""
    out: dict[str, date] = {}
    for r in reviews:
        cid = r.get("card_id")
        d = _as_date(r.get("reviewed_at"))
        if cid is None or d is None:
            continue
        if cid not in out or d < out[cid]:
            out[cid] = d
    return out


# ---------------------------------------------------------------- the plan
def compute(profile: dict, cards: list[dict], states: dict,
            reviews: list[dict], today: date | None = None) -> dict:
    """Return everything the Plan page / Home banner needs. Pure & testable."""
    today = today or today_utc()
    now = datetime.now(timezone.utc)

    # --- key dates
    exam_a = _as_date(profile.get("exam_date_a")) or date(2026, 9, 18)
    exam_b = _as_date(profile.get("exam_date_b")) or date(2026, 9, 22)
    coverage_target = exam_a - timedelta(days=COVERAGE_BUFFER_DAYS)
    days_to_exam = (exam_a - today).days
    days_to_cov = max(1, (coverage_target - today).days)

    # when the coverage clock started (so idle days count as "behind")
    plan_start = _as_date(profile.get("created_at")) or today
    if plan_start > today:
        plan_start = today

    # --- card universe
    active = [c for c in cards if c.get("is_active", True)]
    total = len(active)
    seen_ids = set(states.keys())
    seen = sum(1 for c in active if c["id"] in seen_ids)

    def _order_key(c):
        return (c.get("module") or 99, str(c.get("id")))

    unseen_cards = sorted((c for c in active if c["id"] not in seen_ids), key=_order_key)
    unseen_ids = [c["id"] for c in unseen_cards]
    unseen = len(unseen_ids)

    # --- due / overdue (reps FSRS wants now or earlier)
    due_ids, overdue_ids, overdue_ages = [], [], []
    for c in active:
        s = states.get(c["id"])
        if not s:
            continue
        d = _parse_dt(s.get("due"))
        if d is None:
            continue
        if d <= now:
            due_ids.append(c["id"])
            dd = d.date()
            if dd < today:
                overdue_ids.append(c["id"])
                overdue_ages.append((today - dd).days)
    due_today = len(due_ids)
    overdue = len(overdue_ids)
    oldest_overdue = max(overdue_ages) if overdue_ages else 0

    # --- adaptive new-card target (rises if you fall behind; capped)
    daily_new_cap = int(profile.get("daily_new_limit") or DEFAULT_DAILY_NEW_CAP)
    raw_target = math.ceil(unseen / days_to_cov) if unseen else 0
    daily_new_target = min(raw_target, daily_new_cap)
    # genuinely at risk: even at your daily maximum you can't finish the first
    # pass by the coverage date (raise the cap or accept a later finish).
    at_risk = bool(unseen) and raw_target > daily_new_cap

    # --- new cards already introduced today (exact, per calendar day)
    fseen = first_seen_dates(reviews)
    new_today_done = sum(1 for d in fseen.values() if d == today)
    new_remaining_target = max(0, daily_new_target - new_today_done)
    new_remaining_cap = max(0, daily_new_cap - new_today_done)

    # --- coverage pace & "behind by"
    span = max(1, (coverage_target - plan_start).days)
    elapsed_frac = min(1.0, max(0.0, (today - plan_start).days / span))
    expected_seen = round(total * elapsed_frac)
    coverage_gap = max(0, expected_seen - seen)
    if total > 0:
        on_line_date = plan_start + timedelta(days=round((seen / total) * span))
        coverage_days_behind = max(0, (today - on_line_date).days)
    else:
        coverage_days_behind = 0

    behind_cards = overdue + coverage_gap
    on_track = behind_cards == 0 and unseen == 0 if days_to_cov == 1 else behind_cards == 0

    # --- per-module coverage
    modules: dict[int, dict] = {}
    for c in active:
        m = c.get("module") or 0
        b = modules.setdefault(m, {"module": m, "name": MODULE_NAMES.get(m, f"Module {m}"),
                                   "total": 0, "seen": 0, "due": 0, "new": 0})
        b["total"] += 1
        if c["id"] in seen_ids:
            b["seen"] += 1
            if c["id"] in set(due_ids):
                b["due"] += 1
        else:
            b["new"] += 1
    module_rows = [modules[k] for k in sorted(modules)]

    # --- per-topic coverage (for the full checklist)
    topics: dict[str, dict] = {}
    for c in active:
        t = c.get("topic") or "—"
        b = topics.setdefault(t, {"topic": t, "module": c.get("module") or 99,
                                  "total": 0, "seen": 0, "due": 0, "new": 0})
        b["total"] += 1
        if c["id"] in seen_ids:
            b["seen"] += 1
            if c["id"] in set(due_ids):
                b["due"] += 1
        else:
            b["new"] += 1
    topic_rows = sorted(topics.values(), key=lambda r: (r["module"], r["topic"]))

    # --- 14-day forecast (today = real workload; future = projection)
    scheduled: dict[date, int] = {}
    for cid in seen_ids:
        s = states.get(cid)
        d = _as_date(s.get("due")) if s else None
        if d and d > today:
            scheduled[d] = scheduled.get(d, 0) + 1
    forecast = []
    remaining_unseen = unseen
    for i in range(14):
        day = today + timedelta(days=i)
        if i == 0:
            new_n = min(new_remaining_target, remaining_unseen)
            rev_n = due_today  # includes overdue
        else:
            new_n = min(daily_new_target, remaining_unseen) if day <= coverage_target else 0
            rev_n = scheduled.get(day, 0)
        remaining_unseen -= new_n
        forecast.append({"date": day, "new": new_n, "reviews": rev_n, "total": new_n + rev_n})

    # --- a friendly catch-up line
    if behind_cards > 0:
        # daily_new_target is already raised to absorb the coverage gap; the
        # overdue reviews you clear first in the Study queue.
        catch_up = (f"Do **{daily_new_target} new/day** (already bumped to absorb missed days) "
                    f"and clear the **{overdue} overdue** review(s) — that puts you back on the "
                    f"line for {coverage_target:%d %b}.")
    else:
        catch_up = ""

    return {
        # dates
        "today": today, "exam_a": exam_a, "exam_b": exam_b,
        "coverage_target": coverage_target, "plan_start": plan_start,
        "days_to_exam": days_to_exam, "days_to_coverage": days_to_cov,
        # universe
        "total": total, "seen": seen, "unseen": unseen,
        "due_ids": due_ids, "overdue_ids": overdue_ids, "unseen_ids": unseen_ids,
        # today's workload
        "due_today": due_today, "overdue": overdue, "oldest_overdue": oldest_overdue,
        "daily_new_target": daily_new_target, "daily_new_cap": daily_new_cap,
        "raw_target": raw_target, "at_risk": at_risk,
        "new_today_done": new_today_done,
        "new_remaining_target": new_remaining_target, "new_remaining_cap": new_remaining_cap,
        # behind-ness
        "expected_seen": expected_seen, "coverage_gap": coverage_gap,
        "coverage_days_behind": coverage_days_behind,
        "behind_cards": behind_cards, "on_track": on_track, "catch_up": catch_up,
        # breakdowns
        "modules": module_rows, "topics": topic_rows, "forecast": forecast,
    }
