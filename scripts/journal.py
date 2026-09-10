#!/usr/bin/env python3
"""Append one line to a run's journal.jsonl.

Usage:
  python3 scripts/journal.py add --run <run-dir> --kind <fetch|read|write|subagent|exec|note> \
      --cost_usd <float|null> --detail <text>

Every line is {"ts", "kind", "cost_usd", "detail"}. `cost_usd null` means the cost is
unknown (unmetered); budget.py counts it as 0 and reports how many such lines exist.
`note` is commentary and does not count as an action.

Exit 0 ok, 1 bad input.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("fetch", "read", "write", "subagent", "exec", "note")
ACTION_KINDS = tuple(k for k in KINDS if k != "note")
FILENAME = "journal.jsonl"


def _valid_cost(value):
    if value is None:
        return True
    try:
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0)
    except OverflowError:
        return False


def parse_cost(raw):
    """'null' -> None, otherwise a non-negative float. Raises ValueError."""
    if raw is None or raw.strip().lower() == "null":
        return None
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"invalid cost_usd: {raw!r} (float or null)")
    if not _valid_cost(v):
        raise ValueError("invalid cost_usd (must be finite and >= 0)")
    return v


def add(run, kind, cost_usd, detail):
    """Append one entry. Returns the entry dict. Raises ValueError."""
    run = Path(run)
    if kind not in KINDS:
        raise ValueError(f"invalid kind: {kind!r} (one of {', '.join(KINDS)})")
    if not _valid_cost(cost_usd):
        raise ValueError("invalid cost_usd (must be a finite nonnegative number or null)")
    if not isinstance(detail, str) or detail.strip() == "":
        raise ValueError("missing field: detail")
    if not (run / "goal.json").is_file():
        raise ValueError(f"no goal.json in {run}; run goal.py new first")
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "kind": kind, "cost_usd": cost_usd, "detail": detail}
    with (run / FILENAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read(run):
    """Return all entries; an absent journal is an empty list."""
    path = Path(run) / FILENAME
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    for entry in entries:
        if not isinstance(entry, dict) or "cost_usd" not in entry or not _valid_cost(entry["cost_usd"]):
            raise ValueError("invalid or missing cost_usd in journal")
    return entries


def main(argv):
    p = argparse.ArgumentParser(prog="journal.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--run", required=True)
    a.add_argument("--kind", required=True)
    a.add_argument("--cost_usd", required=True)
    a.add_argument("--detail", required=True)
    args = p.parse_args(argv[1:])
    try:
        entry = add(args.run, args.kind, parse_cost(args.cost_usd), args.detail)
    except (ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"{entry['ts']} {entry['kind']} logged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
