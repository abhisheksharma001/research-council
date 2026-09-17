#!/usr/bin/env python3
"""A frozen task record for the code-writer-council.

Usage:
  python3 scripts/task.py new   --root <workspace> --from <json|->
  python3 scripts/task.py check --run <run-dir>

`new` validates the task body (see skills/code-writer-council/references/task.md), adds
task_id, repo_root, start_commit, budget, created_at and frozen_sha256, and writes
<root>/AGI_Research/code/<task_id>/task.json. Missing or invalid fields are listed one per
line on stderr and the exit code is 1. Nothing is defaulted or invented.

Caps come from <root>/.code-council/config.json when it exists, else from the body's
`budget` block. A missing cap is exit 1 naming it; this script has no default for any cap
(CLAUDE.md invariant 4). When <root> is a git checkout that does not ignore AGI_Research,
the S-16 warning goes to stderr and the exit code stays 0.

`check` recomputes frozen_sha256 and exits 1 if task.json was edited by hand. There is no
revise: the test command and the allowed paths are frozen at task start, and a change to
them is a new task, not an edit (rule 2 of the skill).

Exit 0 ok, 1 invalid input or tampered task.
"""
import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal  # noqa: E402

STRING_FIELDS = ("request_text", "test_command")
BOOL_FIELDS = ("expected_small", "explain")
OPTIONAL_BOOL_FIELDS = ("allow_verifier_edits",)
CAPS = goal.BUDGET_NUMBERS
USER_FIELDS = STRING_FIELDS + ("allowed_paths", "max_diff_lines") + BOOL_FIELDS + OPTIONAL_BOOL_FIELDS + ("budget",)
SCRIPT_FIELDS = ("task_id", "repo_root", "start_commit", "created_at", "frozen_sha256")
CONFIG = Path(".code-council") / "config.json"


def _is_bool(v):
    return isinstance(v, bool)


def validate_budget(budget, where="budget"):
    """Errors for one budget block; `where` names it in each line. Empty when valid."""
    if not isinstance(budget, dict):
        return [f"invalid field: {where} (must be an object)"]
    errors = []
    for k in CAPS:
        if k not in budget:
            errors.append(f"missing field: {where}.{k}")
        elif not goal._is_number(budget[k]) or budget[k] < 0 or (budget[k] == 0 and k != "usd_estimate_cap"):
            floor = "0 or above" if k == "usd_estimate_cap" else "above 0"
            errors.append(f"invalid field: {where}.{k} (must be a number {floor})")
    if budget.get("set_by") != "user":
        errors.append(f'invalid field: {where}.set_by (must be "user")')
    for k in budget:
        if k not in CAPS + ("set_by",):
            errors.append(f"unknown field: {where}.{k}")
    return errors


def validate(body, config_budget=None):
    """Return a list of error strings, empty when the task body is valid.

    config_budget is the budget block read from .code-council/config.json, or None when
    that file does not exist. When it exists the body must not carry its own budget.
    """
    errors = []
    if not isinstance(body, dict):
        return ["task must be a JSON object"]
    for key in body:
        if key not in USER_FIELDS:
            errors.append(f"unknown field: {key}")
    for f in USER_FIELDS:
        if f not in body and f not in OPTIONAL_BOOL_FIELDS + ("budget",):
            errors.append(f"missing field: {f}")
    if config_budget is None and "budget" not in body:
        errors.append(f"missing field: budget (no {CONFIG} in the workspace; "
                      "ask the user for the four caps once per repository)")
    if config_budget is not None and "budget" in body:
        errors.append(f"invalid field: budget (given in the body but {CONFIG} exists; caps come from the config)")
    if errors:
        return errors

    for f in STRING_FIELDS:
        if not goal._nonempty_str(body[f]):
            errors.append(f"invalid field: {f} (must be a non-empty string)")
    paths = body["allowed_paths"]
    if not isinstance(paths, list) or not paths or not all(goal._nonempty_str(x) for x in paths):
        errors.append("invalid field: allowed_paths (must be a list of at least one non-empty string)")
    lines = body["max_diff_lines"]
    if _is_bool(lines) or not isinstance(lines, int) or lines <= 0:
        errors.append("invalid field: max_diff_lines (must be a whole number above 0)")
    for f in BOOL_FIELDS + OPTIONAL_BOOL_FIELDS:
        if f in body and not _is_bool(body[f]):
            errors.append(f"invalid field: {f} (must be true or false)")
    if config_budget is not None:
        errors += validate_budget(config_budget, f"{CONFIG} budget")
    else:
        errors += validate_budget(body["budget"])
    return errors


def read_config(root):
    """The budget block of <root>/.code-council/config.json, or None when the file is absent."""
    path = Path(root) / CONFIG
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "budget" not in data:
        raise ValueError(f"invalid {CONFIG} (must be an object with a budget block)")
    return data["budget"]


def start_commit(root):
    """git HEAD of <root>, or "none" outside a git checkout or before the first commit."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    except OSError:
        return "none"
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "none"


def new(root, body):
    """Validate body, write task.json. Returns the run directory. Raises ValueError."""
    root = Path(root).expanduser()
    if not root.is_dir():
        raise ValueError(f"root must be an existing directory: {root}")
    root = root.resolve()
    config_budget = read_config(root)
    errors = validate(body, config_budget)
    if errors:
        raise ValueError("\n".join(errors))
    task = dict(body)
    task.setdefault("allow_verifier_edits", False)
    task["budget"] = dict(config_budget if config_budget is not None else body["budget"])
    task["task_id"] = str(uuid.uuid4())
    task["repo_root"] = str(root)
    task["start_commit"] = start_commit(root)
    task["created_at"] = goal._now()
    task["frozen_sha256"] = goal.freeze(task)
    run = root / "AGI_Research" / "code" / task["task_id"]
    run.mkdir(parents=True, exist_ok=False)
    goal._write(run / "task.json", task)
    return run


def load(run):
    """Read task.json and verify its hash. Raises ValueError when tampered."""
    task = json.loads((Path(run) / "task.json").read_text(encoding="utf-8"))
    if task.get("frozen_sha256") != goal.freeze(task):
        raise ValueError("task.json was edited outside task.py new (frozen_sha256 mismatch)")
    return task


def main(argv):
    p = argparse.ArgumentParser(prog="task.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("new")
    a.add_argument("--root", required=True)
    a.add_argument("--from", dest="src", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "new":
            run = new(args.root, goal._read_json(args.src))
            warning = goal.ignore_warning(args.root)
            if warning:
                print(warning, file=sys.stderr)
            print(str(run / "task.json"))
        else:
            task = load(args.run)
            print(f"ok: task {task['task_id'][:8]} frozen_sha256 {task['frozen_sha256'][:12]}")
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
