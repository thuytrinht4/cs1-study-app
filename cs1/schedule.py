"""The dated study schedule — a fixed day-by-day topic spine to the exams.

This is the *map* (what to focus on each calendar day); the adaptive Plan/FSRS
layer handles the spacing of recall within it. Design:

  • Learn phase (15 Jun – 9 Aug): cover all 15 CS1 topics, with the high-yield
    ones (MLE, Hypothesis testing, Regression, GLMs, Bayesian, Credibility ⭐)
    getting extra days up front and recurring. Every topic is seen early, leaving
    room to spare.
  • From Week 6 (20 Jul): timed past-paper sections and R/CS1B work start alongside.
  • Past-papers phase (10 Aug – 13 Sep): timed papers, mocks, weak-area drilling, R.
  • CS1A taper (14–17 Sep) → CS1A exam Fri 18 Sep.
  • CS1B (R) focus (19–21 Sep) → CS1B exam Tue 22 Sep.

All dates are fixed (the schedule is the same map whenever you open it).
"""
from datetime import date, timedelta

PLAN_START = date(2026, 6, 15)
WEEK6 = date(2026, 7, 20)             # past-paper sections begin alongside learning
PAST_PAPERS_START = date(2026, 8, 10)
TAPER_START = date(2026, 9, 14)
EXAM_A = date(2026, 9, 18)            # CS1A theory (Fri)
CS1B_FOCUS_START = date(2026, 9, 19)
EXAM_B = date(2026, 9, 22)            # CS1B R (Tue)

# the 15 CS1 topics in teaching order; star = high-yield (extra days, recur)
TOPICS = [
    {"code": "1.1", "module": 1, "name": "Descriptive statistics", "star": False},
    {"code": "1.2", "module": 1, "name": "Data analysis & correlation", "star": False},
    {"code": "2.1", "module": 2, "name": "Random variables & distributions", "star": False},
    {"code": "2.2", "module": 2, "name": "Joint distributions & conditional expectation", "star": False},
    {"code": "2.3", "module": 2, "name": "Central Limit Theorem", "star": False},
    {"code": "2.4", "module": 2, "name": "Generating functions", "star": False},
    {"code": "3.1", "module": 3, "name": "Estimation & MLE", "star": True},
    {"code": "3.2", "module": 3, "name": "Confidence intervals", "star": False},
    {"code": "3.3", "module": 3, "name": "Hypothesis testing", "star": True},
    {"code": "4.1", "module": 4, "name": "Linear regression", "star": True},
    {"code": "4.2", "module": 4, "name": "GLMs", "star": True},
    {"code": "4.3", "module": 4, "name": "Correlation & ANOVA", "star": False},
    {"code": "5.1", "module": 5, "name": "Bayesian statistics", "star": True},
    {"code": "5.2", "module": 5, "name": "Credibility theory", "star": True},
    {"code": "2.5", "module": 2, "name": "Conditional probability & Bayes' theorem", "star": False},
]
HIGH_YIELD = [t for t in TOPICS if t["star"]]


def _learning_sequence():
    """First pass (every topic once, in order) then weighted recurrence
    (high-yield topics appear more), cycled across the learn phase."""
    seq = list(TOPICS)                       # first pass — all 15 covered early
    for t in TOPICS:                         # recurrence, weighted to high-yield
        seq += [t] * (2 if t["star"] else 1)
    return seq


_SEQ = _learning_sequence()


def _label(topic):
    return f"{topic['code']} {topic['name']}" + (" ⭐" if topic["star"] else "")


def for_date(d: date) -> dict:
    """Return the schedule entry for date d."""
    day = (d - PLAN_START).days + 1
    base = {"day": day, "date": d, "topic": None, "deck_filter": {"kind": "all", "modules": set()}}

    if d < PLAN_START:
        return {**base, "phase": "Before start", "focus": "Schedule starts 15 Jun 2026",
                "activities": []}
    if d == EXAM_A:
        return {**base, "phase": "EXAM DAY", "focus": "CS1A (theory) exam — good luck! 🎯",
                "activities": ["Sit CS1A (theory). Read each command word; conclude in context."]}
    if d == EXAM_B:
        return {**base, "phase": "EXAM DAY", "focus": "CS1B (R) exam — good luck! 🎯",
                "activities": ["Sit CS1B (R). Comment every output; sd not variance; set.seed."]}
    if d > EXAM_B:
        return {**base, "phase": "Done", "focus": "Exams complete 🎉", "activities": []}

    # ---- LEARN phase (with past-paper sections from Week 6) ----
    if d < PAST_PAPERS_START:
        topic = _SEQ[(d - PLAN_START).days % len(_SEQ)]
        acts = ["Clear today's due recall cards (Study)",
                f"Drill **{_label(topic)}**: exam-style questions in Deep mode",
                f"Skim the {topic['name']} skeleton on the Method page"]
        phase = "Learn"
        if d >= WEEK6:
            phase = "Learn + past papers"
            acts.append("One timed past-paper section (~30–40 min)")
            if d.weekday() in (2, 5):       # Wed & Sat
                acts.append("R / CS1B practice in RStudio (interpret every output)")
        return {**base, "phase": phase, "topic": topic, "focus": _label(topic),
                "activities": acts, "deck_filter": {"kind": "module", "modules": {topic["module"]}}}

    # ---- PAST-PAPERS / consolidation phase ----
    if d < TAPER_START:
        i = (d - PAST_PAPERS_START).days
        hy = HIGH_YIELD[i % len(HIGH_YIELD)]
        rot = i % 4
        if rot == 0:
            focus = "Full timed CS1A past paper"
            acts = ["Sit a full CS1A section under time", "Daily recall cards",
                    f"Quick drill: {_label(hy)}"]
            df = {"kind": "module", "modules": {hy["module"]}}
        elif rot == 1:
            focus = "Mark & mine weak areas"
            acts = ["Mark yesterday's paper against the examiner report",
                    "Run Weak Areas → analysis, then drill the targeted cards",
                    "Daily recall cards"]
            df = {"kind": "all", "modules": set()}
        elif rot == 2:
            focus = "CS1B (R) full paper"
            acts = ["Full CS1B paper in RStudio on real data",
                    "Comment & interpret every output", "Daily recall cards"]
            df = {"kind": "r", "modules": set()}
        else:
            focus = f"High-yield drill: {_label(hy)}"
            acts = [f"Deep-mode exam questions on {_label(hy)}",
                    "Re-derive its key formulae from a blank page", "Daily recall cards"]
            df = {"kind": "module", "modules": {hy["module"]}}
        return {**base, "phase": "Past papers & mocks", "topic": hy, "focus": focus,
                "activities": acts, "deck_filter": df}

    # ---- CS1A taper (14–17 Sep) ----
    if d < CS1B_FOCUS_START:
        if d == EXAM_A - timedelta(days=1):
            acts = ["Light review only — skim the Method skeletons",
                    "Write the core formula sheet from memory, timed", "Rest well for tomorrow"]
        else:
            acts = ["Light recall of weak cards", "One short timed section",
                    "Write the formula sheet from memory"]
        return {**base, "phase": "CS1A taper", "focus": "Final CS1A review & formula sheet",
                "activities": acts, "deck_filter": {"kind": "all", "modules": set()}}

    # ---- CS1B (R) focus (19–21 Sep) ----
    acts = ["R / CS1B past papers in RStudio", "Drill the ~20 core R code patterns",
            "Interpret every output in one sentence; remember set.seed and sd"]
    return {**base, "phase": "CS1B (R) focus", "focus": "R / CS1B drilling before Tue",
            "activities": acts, "deck_filter": {"kind": "r", "modules": set()}}


def upcoming(d: date, n: int = 7) -> list[dict]:
    return [for_date(d + timedelta(days=i)) for i in range(n)]


def full_schedule() -> list[dict]:
    days = (EXAM_B - PLAN_START).days + 1
    return [for_date(PLAN_START + timedelta(days=i)) for i in range(days)]
