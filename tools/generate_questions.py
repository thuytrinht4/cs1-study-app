#!/usr/bin/env python3
"""Generate new CS1 exam-style questions and append them to data/exam_cards_3.json.

TWO WAYS TO GENERATE (pick one):

  • FREE, on your Max plan (recommended): don't run this script. Open the project
    in VS Code, give Claude Code the prompt in tools/generate_questions_prompt.md
    (it writes questions straight into data/exam_cards_3.json), then run
        python tools/validate_exam_cards.py
    Generation is the priciest API call, and Claude Code uses your subscription.

  • API (this script): one command, but bills your Anthropic API key
    (~2 cents per question on Sonnet). Reuses your app's tested generator.

Usage (API):
    # set the key first (or have it in .streamlit/secrets.toml)
    set ANTHROPIC_API_KEY=sk-ant-...        (Windows)   /   export ... (mac/linux)
    python tools/generate_questions.py --n 10
    python tools/generate_questions.py --n 6 --topics "4.2 GLMs,3.3 Hypothesis testing"
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT_DEFAULT = ROOT / "data" / "exam_cards_3.json"

# default spread, weighted to the high-yield topics
HIGH_YIELD = [
    "4.2 GLMs", "4.2 GLMs", "3.3 Hypothesis testing", "4.1 Linear regression",
    "3.1 Estimation & MLE", "5.1 Bayesian statistics", "5.2 Credibility theory",
    "2.4 Generating functions",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="how many questions to generate")
    ap.add_argument("--topics", default="", help="comma-separated topics (else high-yield mix)")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()

    try:
        from cs1 import ai, config
    except Exception as e:
        print(f"Could not import the app modules: {e}")
        return 1
    if not config.anthropic_ready():
        print("No ANTHROPIC_API_KEY found (env or .streamlit/secrets.toml).\n"
              "Tip: use the FREE route instead — see tools/generate_questions_prompt.md.")
        return 1

    topics = [t.strip() for t in args.topics.split(",") if t.strip()] or HIGH_YIELD
    out = Path(args.out)
    existing = json.load(open(out, encoding="utf-8")) if out.exists() else []
    ids = {c.get("id") for c in existing}

    made = 0
    for i in range(args.n):
        topic = topics[i % len(topics)]
        try:
            q = ai.generate_exam_question(topic)
        except Exception as e:
            print(f"  ! generation failed for {topic}: {e}")
            continue
        new_id = "gen_" + uuid.uuid4().hex[:8]
        while new_id in ids:
            new_id = "gen_" + uuid.uuid4().hex[:8]
        q["id"] = new_id
        ids.add(new_id)
        existing.append(q)
        made += 1
        print(f"  + {new_id}  {q.get('topic')}  [{q.get('max_marks')} marks]")

    json.dump(existing, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote {made} new question(s) to {out}  ({len(existing)} total).")

    # auto-validate what we just wrote
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("v", ROOT / "tools" / "validate_exam_cards.py")
        v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v)
        print("\nValidating…")
        v.main(["validate", str(out)])
    except Exception as e:
        print(f"(validator could not run automatically: {e} — run it manually)")
    print("\nNext: open the app → Home → 'Import / update exam questions'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
