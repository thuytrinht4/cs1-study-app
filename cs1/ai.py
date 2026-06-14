"""Claude-powered marking (Milestone M2).

Uses Anthropic tool-use to force reliable, structured JSON output instead of
free-form prose. Model defaults to Haiku (cheap, fast) from config.

Cost: a graded answer is ~1-2k tokens in + <0.5k out — a fraction of a cent.
The AnthropicAPI key is only needed for this module; M0/M1 run without it.
"""
import anthropic
from . import config

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.anthropic_ready():
            raise RuntimeError("ANTHROPIC_API_KEY not set — add it to .streamlit/secrets.toml")
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def available() -> bool:
    return config.anthropic_ready()


RATING_LABEL = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

GRADE_TOOL = {
    "name": "report_mark",
    "description": "Mark a student's CS1 answer against the model answer and (if given) mark scheme.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "description": "marks awarded (0..max)"},
            "max": {"type": "number", "description": "maximum marks for this card"},
            "awarded_points": {"type": "array", "items": {"type": "string"},
                               "description": "points the student got right"},
            "missed_points": {"type": "array", "items": {"type": "string"},
                              "description": "marking points the student missed or got wrong"},
            "misconceptions": {"type": "array", "items": {"type": "string"},
                               "description": "specific wrong ideas, e.g. 'uses variance where sd is required'"},
            "feedback": {"type": "string",
                         "description": "one or two specific, encouraging sentences"},
            "suggested_rating": {"type": "integer",
                                 "description": "spaced-repetition grade: 1 Again, 2 Hard, 3 Good, 4 Easy"},
        },
        "required": ["score", "max", "missed_points", "misconceptions",
                     "feedback", "suggested_rating"],
    },
}

SYSTEM = (
    "You are a strict but fair examiner for the IFoA CS1 (Actuarial Statistics) exam. "
    "Mark the student's answer against the model answer and mark scheme. Rules: "
    "award marks only for points actually present in the student's answer; reward correct "
    "method even when there is an arithmetic slip; be specific and concrete about what was "
    "missed. Apply the style examiners reward: stating H0/H1, concluding in context, and "
    "commenting on/interpreting R output. If no explicit mark scheme is provided, infer the "
    "key marking points from the model answer. Set suggested_rating from how complete and "
    "correct the answer is: 1=little/none correct, 2=partial with gaps, 3=mostly correct, "
    "4=fully correct and fluent."
)


def _user_prompt(card: dict, answer_text: str) -> str:
    scheme = card.get("mark_scheme")
    scheme_txt = ""
    if scheme:
        scheme_txt = "MARK SCHEME (each item worth the marks shown):\n" + str(scheme) + "\n\n"
    return (
        f"QUESTION:\n{card['front']}\n\n"
        f"MODEL ANSWER:\n{card['model_answer']}\n\n"
        f"{scheme_txt}"
        f"MAX MARKS: {card.get('max_marks', 3)}\n\n"
        f"STUDENT ANSWER:\n{answer_text.strip() or '(blank)'}"
    )


def grade_answer(card: dict, answer_text: str) -> dict:
    """Return a dict matching GRADE_TOOL's schema. Raises on API/parse failure."""
    msg = _get_client().messages.create(
        model=config.MODEL_MARKER,
        max_tokens=800,
        tools=[GRADE_TOOL],
        tool_choice={"type": "tool", "name": "report_mark"},
        system=SYSTEM,
        messages=[{"role": "user", "content": _user_prompt(card, answer_text)}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return a structured mark.")


# ====================================================================
#  M3 — weak-pattern detection & targeted follow-up generation (Sonnet)
# ====================================================================
import json as _json

ANALYZE_TOOL = {
    "name": "report_patterns",
    "description": ("Identify recurring weaknesses from a CS1 student's recent marked "
                    "answers and propose targeted follow-up cards."),
    "input_schema": {
        "type": "object",
        "properties": {
            "patterns": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string", "description": "existing pattern id if updating one; omit if new"},
                "topic": {"type": "string"},
                "label": {"type": "string", "description": "short name of the weakness"},
                "description": {"type": "string", "description": "what is repeatedly wrong and why"},
                "severity": {"type": "integer", "description": "1 low, 2 medium, 3 high"},
                "status": {"type": "string", "enum": ["open", "improving", "resolved"]},
            }, "required": ["topic", "label", "description", "severity", "status"]}},
            "followup_cards": {"type": "array", "items": {"type": "object", "properties": {
                "topic": {"type": "string", "description": "must match one of the provided topic names"},
                "type": {"type": "string", "enum": ["concept", "formula", "r"]},
                "front": {"type": "string"},
                "model_answer": {"type": "string"},
                "targets_label": {"type": "string", "description": "which weakness label this addresses"},
            }, "required": ["topic", "type", "front", "model_answer"]}},
            "coaching_note": {"type": "string", "description": "2-4 specific, encouraging sentences"},
        },
        "required": ["patterns", "followup_cards", "coaching_note"],
    },
}

ANALYZE_SYSTEM = (
    "You are an expert IFoA CS1 study coach. From a student's recent marked answers, identify the "
    "few highest-impact recurring weaknesses, grouped by topic/section. Update any existing open "
    "patterns (reuse their id; mark 'improving' or 'resolved' when recent evidence shows progress) "
    "and add new ones only when justified. Then generate at most 5 targeted follow-up flashcards "
    "that, if mastered, would recover the most marks — prefer the highest-yield topics (GLMs, "
    "hypothesis testing, regression, MLE, Bayesian). Each card's topic MUST be one of the provided "
    "topic names. Be concrete and specific; avoid generic advice."
)


def find_weak_patterns(answers: list[dict], open_patterns: list[dict], topic_names: list[str]) -> dict:
    """Analyse recent answers -> {patterns, followup_cards, coaching_note}."""
    digest = [{
        "topic": a.get("topic"),
        "score": a.get("ai_score"), "max": a.get("ai_max"),
        "missed": a.get("missed_points"), "misconceptions": a.get("misconceptions"),
    } for a in answers]
    existing = [{"id": p.get("id"), "topic": p.get("topic"),
                 "label": p.get("label"), "status": p.get("status")} for p in open_patterns]
    content = (
        "RECENT MARKED ANSWERS (most recent first):\n" + _json.dumps(digest, default=str) +
        "\n\nEXISTING OPEN PATTERNS:\n" + _json.dumps(existing, default=str) +
        "\n\nVALID TOPIC NAMES for follow-up cards:\n" + _json.dumps(topic_names)
    )
    msg = _get_client().messages.create(
        model=config.MODEL_ANALYST,
        max_tokens=1600,
        tools=[ANALYZE_TOOL],
        tool_choice={"type": "tool", "name": "report_patterns"},
        system=ANALYZE_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return structured patterns.")
