#!/usr/bin/env python3
"""Triage: decide whether a request is big enough for research-council.

Usage:
  python3 scripts/triage.py --answers <json-file-or-'-'>

The agent answers five fixed yes/no questions about the request BEFORE calling this script
(see skills/research-council/references/triage.md). The script is deterministic and never
reads the workspace or calls a model.

Answers JSON: {"q1": true|false, "q2": ..., "q3": ..., "q4": ..., "q5": ...}
Output JSON on stdout: {"verdict": "big"|"small", "reasons": [...]}
Exit 0 for big, 3 for small, 1 for malformed input.
"""
import json
import sys

QUESTIONS = {
    "q1": "more than one credible explanation",
    "q2": "outcome cannot be verified by one command or one test",
    "q3": "affects more than one file, service, or user",
    "q4": "user asked for research explicitly",
    "q5": "a wrong answer costs money, data, or a client",
}
SCORED = ("q1", "q2", "q3", "q5")
MIN_YES = 2


def triage(answers):
    missing = [q for q in QUESTIONS if q not in answers]
    if missing:
        raise ValueError(f"missing answers: {', '.join(missing)}")
    bad = [q for q in QUESTIONS if not isinstance(answers[q], bool)]
    if bad:
        raise ValueError(f"answers must be true/false: {', '.join(bad)}")

    if answers["q4"]:
        return {"verdict": "big", "reasons": ["q4: user asked for research explicitly"]}

    yes = [q for q in SCORED if answers[q]]
    no = [q for q in SCORED if not answers[q]]
    if len(yes) >= MIN_YES:
        return {"verdict": "big", "reasons": [f"{q}: {QUESTIONS[q]}" for q in yes]}
    return {
        "verdict": "small",
        "reasons": [f"only {len(yes)} of {len(SCORED)} size signals present; need {MIN_YES}"]
        + [f"{q}: no ({QUESTIONS[q]})" for q in no],
    }


def main(argv):
    if len(argv) != 3 or argv[1] != "--answers":
        print(__doc__)
        return 1
    try:
        raw = sys.stdin.read() if argv[2] == "-" else open(argv[2], encoding="utf-8").read()
        result = triage(json.loads(raw))
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}))
        return 1
    print(json.dumps(result))
    return 0 if result["verdict"] == "big" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
