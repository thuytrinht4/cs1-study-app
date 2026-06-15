#!/usr/bin/env python3
"""Validate AI-generated CS1 exam-style question JSON before importing.

Run this after Claude Code (or the generator script) writes new questions, so
only correct, well-formed questions reach your app.

Checks each question: required fields present; type/module valid; mark_scheme is
a non-empty list of {point, marks}; max_marks equals the sum of scheme marks;
ids unique across all exam files; R questions contain an R code block.

Usage:
    python tools/validate_exam_cards.py                # checks data/exam_cards*.json
    python tools/validate_exam_cards.py data/exam_cards_3.json
Exit code 0 = all valid (no errors); 1 = errors found.
"""
import json
import sys
import glob
from pathlib import Path

try:  # make emoji / unicode output safe on the Windows console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ["id", "topic", "module", "type", "front", "model_answer", "mark_scheme", "max_marks"]
TYPES = {"concept", "formula", "r"}


def validate_file(path: str, seen_ids: set) -> tuple[list, list]:
    errs, warns = [], []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return [f"{path}: invalid JSON — {e}"], []
    if not isinstance(data, list):
        return [f"{path}: top level must be a JSON array"], []
    for i, c in enumerate(data):
        loc = f"{Path(path).name}[{i}] id={c.get('id', '?')}"
        for k in REQUIRED:
            if k not in c or c[k] in (None, ""):
                errs.append(f"{loc}: missing/empty '{k}'")
        if c.get("id"):
            if c["id"] in seen_ids:
                errs.append(f"{loc}: duplicate id '{c['id']}'")
            seen_ids.add(c["id"])
        if c.get("type") not in TYPES:
            errs.append(f"{loc}: type must be one of {sorted(TYPES)}")
        m = c.get("module")
        if not isinstance(m, int) or not (1 <= m <= 5):
            errs.append(f"{loc}: module must be an int 1..5")
        ms = c.get("mark_scheme")
        if isinstance(ms, list) and ms:
            total, ok = 0, True
            for item in ms:
                if not isinstance(item, dict) or "marks" not in item or "point" not in item:
                    errs.append(f"{loc}: each mark_scheme item needs 'point' and 'marks'")
                    ok = False
                    break
                total += item.get("marks", 0)
            if ok and c.get("max_marks") != total:
                errs.append(f"{loc}: max_marks ({c.get('max_marks')}) != sum of scheme ({total})")
        else:
            errs.append(f"{loc}: mark_scheme must be a non-empty list")
        if c.get("type") == "r" and "```r" not in (c.get("model_answer") or ""):
            warns.append(f"{loc}: type 'r' but no ```r code block in model_answer")
        if len(str(c.get("front") or "")) < 40:
            warns.append(f"{loc}: very short 'front' — check it's a full question")
    return errs, warns


def main(argv: list) -> int:
    files = argv[1:] or sorted(glob.glob(str(ROOT / "data" / "exam_cards*.json")))
    if not files:
        print("No exam_cards*.json files found.")
        return 1
    seen, all_err, all_warn, total = set(), [], [], 0
    for f in files:
        if not Path(f).exists():
            print(f"skip (not found): {f}")
            continue
        try:
            total += len(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
        e, w = validate_file(f, seen)
        all_err += e
        all_warn += w
    for w in all_warn:
        print("WARN: ", w)
    for e in all_err:
        print("ERROR:", e)
    print(f"\nChecked {total} questions across {len(files)} file(s): "
          f"{len(all_err)} error(s), {len(all_warn)} warning(s).")
    if not all_err:
        print("All valid - safe to import in the app.")
    return 1 if all_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
