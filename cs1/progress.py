"""Progress scoring — turns your Again/Hard/Good/Easy clicks into visible marks.

Every grade earns **recall points**:  Again = 0, Hard = 1, Good = 2, Easy = 3.
So a day with lots of practice, or lots of Good/Easy, scores highly — that's the
reward signal. Aggregated per topic into a 0–100 **strength** score that blends:

  * coverage  — how many of the topic's cards you've actually seen,
  * quality   — share of your grades that were Good or Easy,
  * depth     — how much practice (reps), targeting ~2 reviews per card.

Strength → label: Strong (≥70), Developing (≥40), Weak (>0), Not started (0).
A topic that is Strong is, by definition, *not* a weak area. All derived from the
`reviews` table — no schema change, no extra storage.
"""
from __future__ import annotations

from datetime import date, timedelta
from . import plan  # reuse _as_date / today_utc

RATING_POINTS = {1: 0, 2: 1, 3: 2, 4: 3}
RATING_NAME = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
TARGET_REPS_PER_CARD = 2  # what counts as "enough practice" per card


def points_for(rating) -> int:
    return RATING_POINTS.get(int(rating or 0), 0)


def _streak(days_set: set, today: date) -> int:
    d, n = today, 0
    if d not in days_set and (d - timedelta(days=1)) in days_set:
        d -= timedelta(days=1)  # don't punish today before you've studied
    while d in days_set:
        n += 1
        d -= timedelta(days=1)
    return n


def strength_label(strength: int, reps: int, seen: int) -> str:
    if reps == 0 and seen == 0:
        return "Not started"
    if strength >= 70:
        return "Strong"
    if strength >= 40:
        return "Developing"
    return "Weak"


def compute(cards: list[dict], states: dict, reviews: list[dict],
            today: date | None = None) -> dict:
    today = today or plan.today_utc()
    active = [c for c in cards if c.get("is_active", True)]
    total = len(active)
    seen_ids = set(states.keys())
    week_ago = today - timedelta(days=6)

    # ---- per-topic accumulators (seed from the card bank so 0-rep topics show)
    topics: dict[str, dict] = {}
    for c in active:
        t = c.get("topic") or "—"
        b = topics.setdefault(t, {"topic": t, "module": c.get("module") or 99,
                                  "total": 0, "seen": 0, "reps": 0, "good": 0, "points": 0})
        b["total"] += 1
        if c["id"] in seen_ids:
            b["seen"] += 1

    # ---- walk the review log: points (total / today / 7-day), per-day, per-topic
    total_points = points_today = points_7d = 0
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    per_day: dict[date, dict] = {}
    for r in reviews:
        rating = int(r.get("rating") or 0)
        pts = points_for(rating)
        total_points += pts
        if rating in rating_counts:
            rating_counts[rating] += 1
        d = plan._as_date(r.get("reviewed_at"))
        if d:
            day = per_day.setdefault(d, {"reviews": 0, "points": 0})
            day["reviews"] += 1
            day["points"] += pts
            if d == today:
                points_today += pts
            if d >= week_ago:
                points_7d += pts
        t = r.get("topic")
        if t in topics:
            topics[t]["reps"] += 1
            topics[t]["points"] += pts
            if rating >= 3:
                topics[t]["good"] += 1

    # ---- per-topic strength score
    rows = []
    for info in topics.values():
        reps, tot, seen = info["reps"], info["total"], info["seen"]
        good_rate = info["good"] / reps if reps else 0.0
        coverage = seen / tot if tot else 0.0
        depth = min(1.0, reps / (TARGET_REPS_PER_CARD * tot)) if tot else 0.0
        # quality-dominated: you must have seen the cards (coverage) AND recall them
        # well (good_rate); more practice (depth) lifts it toward the cap. So a topic
        # graded mostly 'Again' reads as Weak even at full coverage.
        quality = 0.25 + 0.75 * good_rate
        strength = round(100 * coverage * quality * (0.7 + 0.3 * depth))
        rows.append({**info, "good_rate": round(100 * good_rate),
                     "coverage": round(100 * coverage), "depth": round(100 * depth),
                     "strength": strength, "label": strength_label(strength, reps, seen)})
    rows.sort(key=lambda r: (r["module"], r["topic"]))

    tally = {k: sum(1 for r in rows if r["label"] == k)
             for k in ["Strong", "Developing", "Weak", "Not started"]}
    needs = sorted([r for r in rows if r["label"] in ("Weak", "Not started")],
                   key=lambda r: (r["strength"], -r["total"]))

    return {
        "today": today,
        "total_points": total_points, "points_today": points_today, "points_7d": points_7d,
        "rating_counts": rating_counts, "streak": _streak(set(per_day), today),
        "topic_rows": rows, "tally": tally, "needs": needs, "per_day": per_day,
        "total": total, "seen": len(seen_ids & {c["id"] for c in active}),
    }
