#!/usr/bin/env python3
"""Running spend against the user-set budget in goal.json.

Usage:
  python3 scripts/budget.py check --run <run-dir>

Reads goal.json through goal.load (so a hand-edited budget is refused) and journal.jsonl.
Prints one line:
  spent: 12/60 min, 30/200 actions, 2/4 subagents, ~$0.40/$5 (unmetered: 3)
Exit 0 when every number is within its cap, 2 when any cap is exceeded (each exceeded cap
named on stderr), 1 when goal.json is missing, tampered, or lacks a budget number.

Caps come only from goal.json. This script defines no default and never changes a cap
(CLAUDE.md invariant 4).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal  # noqa: E402
import journal  # noqa: E402

CAPS = ("minutes", "max_actions", "max_subagents", "usd_estimate_cap")


def _money(v):
    return f"{v:g}"


def status(run, now=None):
    """Return {spent, caps, unmetered, exceeded}. Raises ValueError."""
    g = goal.load(run)
    budget = g.get("budget", {})
    for k in CAPS:
        if k not in budget:
            raise ValueError(f"goal.json budget missing: {k} (no default exists)")
    caps = {k: budget[k] for k in CAPS}
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(g["created_at"])
    entries = journal.read(run)
    spent = {
        "minutes": int((now - created).total_seconds() // 60),
        "max_actions": sum(1 for e in entries if e["kind"] in journal.ACTION_KINDS),
        "max_subagents": sum(1 for e in entries if e["kind"] == "subagent"),
        "usd_estimate_cap": sum(e["cost_usd"] or 0 for e in entries),
    }
    unmetered = sum(1 for e in entries if e["cost_usd"] is None)
    exceeded = [k for k in CAPS if spent[k] > caps[k]]
    return {"spent": spent, "caps": caps, "unmetered": unmetered, "exceeded": exceeded}


def line(st):
    s, c = st["spent"], st["caps"]
    return (f"spent: {s['minutes']}/{c['minutes']} min, "
            f"{s['max_actions']}/{c['max_actions']} actions, "
            f"{s['max_subagents']}/{c['max_subagents']} subagents, "
            f"~${s['usd_estimate_cap']:.2f}/${_money(c['usd_estimate_cap'])} "
            f"(unmetered: {st['unmetered']})")


def main(argv):
    p = argparse.ArgumentParser(prog="budget.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        st = status(args.run)
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(line(st))
    if st["exceeded"]:
        for k in st["exceeded"]:
            print(f"exceeded: {k} ({st['spent'][k]}/{st['caps'][k]})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
