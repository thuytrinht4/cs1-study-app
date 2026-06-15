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
        # cache_control marks the static prefix (system + tools) as cacheable.
        # Note: prompt caching only *bills less* when that cached prefix exceeds
        # Anthropic's minimum (~2048 tokens for Haiku, ~1024 for Sonnet). Our
        # system+tools here are smaller than that, so today the saving is ~nil —
        # this is correct, free, future-proofing for if these prompts grow. The
        # real cost levers are: use Deep only on substantive cards (self-grade
        # the quick ones) and generate questions free on your Max plan.
        tools=[{**GRADE_TOOL, "cache_control": {"type": "ephemeral"}}],
        tool_choice={"type": "tool", "name": "report_mark"},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _user_prompt(card, answer_text)}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return a structured mark.")


TUTOR_SYSTEM = (
    "You are a patient, precise IFoA CS1 tutor. The student has just answered an exam-style "
    "question and seen the mark. Answer their follow-up about the question, their answer, or the "
    "underlying concept. Be concise and correct; treat the model answer and mark scheme as ground "
    "truth. Show working or a short derivation where it helps, and point out the exam technique "
    "examiners reward (state H0/H1, conclude in context, comment on R output). If they ask for an "
    "R snippet, give correct R."
)


def followup_answer(card: dict, answer_text: str, grade: dict,
                    question: str, history: list | None = None) -> str:
    """Tutor-style reply to a follow-up question about a card (Haiku, cheap)."""
    ctx = f"QUESTION:\n{card.get('front', '')}\n\nMODEL ANSWER:\n{card.get('model_answer', '')}\n\n"
    if card.get("mark_scheme"):
        ctx += "MARK SCHEME:\n" + str(card["mark_scheme"]) + "\n\n"
    if (answer_text or "").strip():
        ctx += f"STUDENT'S ANSWER:\n{answer_text.strip()}\n\n"
    if grade and grade.get("feedback"):
        ctx += f"EXAMINER FEEDBACK:\n{grade.get('feedback')}\n\n"
    messages = []
    for qa in (history or []):
        messages.append({"role": "user", "content": qa["q"]})
        messages.append({"role": "assistant", "content": qa["a"]})
    messages.append({"role": "user", "content": question.strip()})
    msg = _get_client().messages.create(
        model=config.MODEL_MARKER,
        max_tokens=700,
        system=TUTOR_SYSTEM + "\n\nCONTEXT FOR THIS QUESTION:\n" + ctx,
        messages=messages,
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


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
        tools=[{**ANALYZE_TOOL, "cache_control": {"type": "ephemeral"}}],
        tool_choice={"type": "tool", "name": "report_patterns"},
        system=[{"type": "text", "text": ANALYZE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return structured patterns.")


# ====================================================================
#  Generate a fresh exam-style question on demand (Sonnet)
# ====================================================================
GENERATE_TOOL = {
    "name": "report_question",
    "description": "Produce one original, exam-style CS1 question with a worked model answer and mark scheme.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "short topic label, e.g. '4.2 GLMs'"},
            "module": {"type": "integer", "description": "1 Data analysis, 2 Probability, 3 Inference, 4 Regression/GLM, 5 Bayesian"},
            "type": {"type": "string", "enum": ["concept", "formula", "r"]},
            "front": {"type": "string", "description": "the question, multi-part with marks shown as **[n]**, past-paper style"},
            "model_answer": {"type": "string", "description": "worked solution; begin with '**Approach:**' (the method) then '**Solution:**'"},
            "mark_scheme": {"type": "array", "items": {"type": "object", "properties": {
                "point": {"type": "string"}, "marks": {"type": "integer"}}, "required": ["point", "marks"]}},
            "max_marks": {"type": "integer", "description": "must equal the sum of the mark-scheme marks"},
        },
        "required": ["topic", "module", "type", "front", "model_answer", "mark_scheme", "max_marks"],
    },
}

GENERATE_SYSTEM = (
    "You are an IFoA CS1 (Actuarial Statistics) examiner writing original practice questions in the "
    "style of past papers. Write ONE multi-part, applied question on the requested topic — a realistic "
    "scenario with parts labelled (i), (ii), … and the marks shown as **[n]**. Provide a fully worked "
    "model answer that starts with the method/approach, then the solution with clear substitution, and "
    "ends with interpretation in context. Provide a point-by-point mark scheme whose marks sum exactly "
    "to max_marks. Use realistic numbers and ensure every calculation is numerically correct. Reward the "
    "exam style: stating H0/H1, concluding in context, commenting on R output. If the topic is R/CS1B, "
    "set type='r' and give correct R code in fenced ```r blocks."
)


def generate_exam_question(topic: str) -> dict:
    """Ask Claude for one new exam-style question dict (matches GENERATE_TOOL)."""
    msg = _get_client().messages.create(
        model=config.MODEL_ANALYST,
        max_tokens=1500,
        tools=[{**GENERATE_TOOL, "cache_control": {"type": "ephemeral"}}],
        tool_choice={"type": "tool", "name": "report_question"},
        system=[{"type": "text", "text": GENERATE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Write one exam-style CS1 question on: {topic}."}],
    )
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return a question.")
