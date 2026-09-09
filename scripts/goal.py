#!/usr/bin/env python3
"""Goal capture with a frozen revision.

Usage:
  python3 scripts/goal.py new    --root <workspace> --from <json>
  python3 scripts/goal.py revise --run <run-dir> --from <json> --reason <text>
  python3 scripts/goal.py check  --run <run-dir>

`new` validates the goal body (see skills/research-council/references/goal.md), adds
goal_id, revision 1, created_at and frozen_sha256, and writes
<root>/AGI_Research/runs/<goal_id>/goal.json. Missing or invalid fields are listed one per
line on stderr and the exit code is 1. Nothing is defaulted or invented. When <root> has a
.git directory and its .gitignore has no line mentioning AGI_Research, a warning goes to stderr
and the exit code stays 0; this script never edits .gitignore.

`revise` is the only way a goal changes. It verifies the current goal.json is untouched,
appends it (with the reason) to goal.history.jsonl, and writes revision n+1. A budget cap
can never go up in a revision (CLAUDE.md invariant 4).

`check` recomputes frozen_sha256 and exits 1 if goal.json was edited by hand.

Exit 0 ok, 1 invalid input or tampered goal.
"""
import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

STRING_FIELDS = ("request_text", "desired_outcome", "scope", "baseline")
LIST_FIELDS = ("observations", "suggested_explanations", "unknowns", "allowed_actions",
               "prohibited_actions")
HYPOTHESIS_KEYS = ("id", "statement", "predicted_result", "strongest_alternative")
CRITERION_KEYS = ("measurement", "evaluator", "environment", "pass_condition")
BUDGET_NUMBERS = ("minutes", "max_actions", "max_subagents", "usd_estimate_cap")
MIN_HYPOTHESES = 2
USER_FIELDS = STRING_FIELDS + LIST_FIELDS + (
    "competing_hypotheses", "success_criteria", "budget", "library_snapshot")
SCRIPT_FIELDS = ("goal_id", "revision", "created_at", "revised_at", "revision_reason",
                 "frozen_sha256")


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate(body):
    """Return a list of error strings, empty when the goal body is valid."""
    errors = []
    if not isinstance(body, dict):
        return ["goal must be a JSON object"]
    for key in body:
        if key not in USER_FIELDS:
            errors.append(f"unknown field: {key}")
    for f in USER_FIELDS:
        if f not in body:
            errors.append(f"missing field: {f}")
    if errors:
        return errors

    for f in STRING_FIELDS:
        if not _nonempty_str(body[f]):
            errors.append(f"invalid field: {f} (must be a non-empty string)")
    for f in LIST_FIELDS:
        if not isinstance(body[f], list) or not all(_nonempty_str(x) for x in body[f]):
            errors.append(f"invalid field: {f} (must be a list of non-empty strings)")

    hyps = body["competing_hypotheses"]
    if not isinstance(hyps, list) or len(hyps) < MIN_HYPOTHESES:
        errors.append(f"invalid field: competing_hypotheses (need at least {MIN_HYPOTHESES})")
    else:
        ids = []
        for i, h in enumerate(hyps):
            if not isinstance(h, dict):
                errors.append(f"invalid field: competing_hypotheses[{i}] (must be an object)")
                continue
            for k in HYPOTHESIS_KEYS:
                if not _nonempty_str(h.get(k)):
                    errors.append(f"missing field: competing_hypotheses[{i}].{k}")
            ids.append(h.get("id"))
        if len(set(ids)) != len(ids):
            errors.append("invalid field: competing_hypotheses (ids must be unique)")

    crit = body["success_criteria"]
    if not isinstance(crit, list) or len(crit) < 1:
        errors.append("invalid field: success_criteria (need at least 1; never invent one)")
    else:
        for i, c in enumerate(crit):
            if not isinstance(c, dict):
                errors.append(f"invalid field: success_criteria[{i}] (must be an object)")
                continue
            for k in CRITERION_KEYS:
                if not _nonempty_str(c.get(k)):
                    errors.append(f"missing field: success_criteria[{i}].{k}")

    budget = body["budget"]
    if not isinstance(budget, dict):
        errors.append("invalid field: budget (must be an object)")
    else:
        for k in BUDGET_NUMBERS:
            if k not in budget:
                errors.append(f"missing field: budget.{k}")
            elif not _is_number(budget[k]) or budget[k] < 0 or (budget[k] == 0 and k != "usd_estimate_cap"):
                floor = "0 or above" if k == "usd_estimate_cap" else "above 0"
                errors.append(f"invalid field: budget.{k} (must be a number {floor})")
        if budget.get("set_by") != "user":
            errors.append('invalid field: budget.set_by (must be "user")')
        for k in budget:
            if k not in BUDGET_NUMBERS + ("set_by",):
                errors.append(f"unknown field: budget.{k}")

    snap = body["library_snapshot"]
    if snap is not None and not _nonempty_str(snap):
        errors.append("invalid field: library_snapshot (must be a string or null)")
    return errors


def freeze(goal):
    """sha256 over every field except frozen_sha256, canonical JSON."""
    payload = {k: v for k, v in goal.items() if k != "frozen_sha256"}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(path, goal):
    path.write_text(json.dumps(goal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def new(root, body):
    """Validate body, write revision 1. Returns the run directory. Raises ValueError."""
    errors = validate(body)
    if errors:
        raise ValueError("\n".join(errors))
    goal = dict(body)
    goal["goal_id"] = str(uuid.uuid4())
    goal["revision"] = 1
    goal["created_at"] = _now()
    goal["frozen_sha256"] = freeze(goal)
    run = Path(root) / "AGI_Research" / "runs" / goal["goal_id"]
    run.mkdir(parents=True, exist_ok=False)
    _write(run / "goal.json", goal)
    return run


def load(run):
    """Read goal.json and verify its hash. Raises ValueError when tampered."""
    goal = json.loads((Path(run) / "goal.json").read_text(encoding="utf-8"))
    if goal.get("frozen_sha256") != freeze(goal):
        raise ValueError("goal.json was edited outside goal.py revise (frozen_sha256 mismatch)")
    return goal


def revise(run, body, reason):
    """Write revision n+1, keep the old one in goal.history.jsonl. Raises ValueError."""
    if not _nonempty_str(reason):
        raise ValueError("missing field: reason")
    current = load(run)
    errors = validate(body)
    for k in BUDGET_NUMBERS:
        if not errors and body["budget"][k] > current["budget"][k]:
            errors.append(f"budget cap cannot be raised in a revision: {k} "
                          f"{current['budget'][k]} -> {body['budget'][k]}")
    if errors:
        raise ValueError("\n".join(errors))
    goal = dict(body)
    goal["goal_id"] = current["goal_id"]
    goal["revision"] = current["revision"] + 1
    goal["created_at"] = current["created_at"]
    goal["revised_at"] = _now()
    goal["revision_reason"] = reason
    goal["frozen_sha256"] = freeze(goal)
    run = Path(run)
    with (run / "goal.history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"superseded_at": goal["revised_at"], "reason": reason,
                             "goal": current}, ensure_ascii=False) + "\n")
    _write(run / "goal.json", goal)
    return goal


def _read_json(path):
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


IGNORE_WARNING = ("warning: AGI_Research/ is not ignored by {gitignore}; "
                  "the run folder holds client data")


def ignore_warning(root):
    """S-16 warning when <root> is a git checkout that does not ignore AGI_Research; else None."""
    root = Path(root)
    if not (root / ".git").exists():
        return None
    gitignore = root / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if any("AGI_Research" in line for line in lines):
        return None
    return IGNORE_WARNING.format(gitignore=gitignore)


def main(argv):
    p = argparse.ArgumentParser(prog="goal.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("new")
    a.add_argument("--root", required=True)
    a.add_argument("--from", dest="src", required=True)
    b = sub.add_parser("revise")
    b.add_argument("--run", required=True)
    b.add_argument("--from", dest="src", required=True)
    b.add_argument("--reason", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "new":
            run = new(args.root, _read_json(args.src))
            warning = ignore_warning(args.root)
            if warning:
                print(warning, file=sys.stderr)
            print(str(run / "goal.json"))
        elif args.cmd == "revise":
            goal = revise(args.run, _read_json(args.src), args.reason)
            print(f"revision {goal['revision']} written; previous kept in goal.history.jsonl")
        else:
            goal = load(args.run)
            print(f"ok: revision {goal['revision']} frozen_sha256 {goal['frozen_sha256'][:12]}")
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
