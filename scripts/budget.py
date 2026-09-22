#!/usr/bin/env python3
"""Running spend against the user-set budget in goal.json or task.json.

Usage:
  python3 scripts/budget.py check --run <run-dir>

Reads goal.json through goal.load, or task.json (a code-writer-council run) through
task.load, so a hand-edited budget is refused either way, plus journal.jsonl.
Prints the spent line, and a second line whenever the journal holds any entry:
  spent: 12/60 min, 30/200 actions, 2/4 subagents, ~$0.40/$5 (unmetered: 3)
  minutes are wall clock since created_at; longest quiet stretch: 288 min, ending <ts>

The second line is measured from the journal's own timestamps and explains nothing away: the
minutes spent are still wall clock since `created_at`, because that is the cap the user set.
Exit 0 when every number is within its cap, 2 when any cap is exceeded (each exceeded cap
named on stderr), 1 when goal.json is missing, tampered, or lacks a budget number.

Caps come only from that record. This script defines no default and never changes a cap
(CLAUDE.md invariant 4).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal  # noqa: E402
import journal  # noqa: E402
import task  # noqa: E402

CAPS = ("minutes", "max_actions", "max_subagents", "usd_estimate_cap")


def _money(v):
    return f"{v:g}"


def _record(run):
    """(name, record, validation errors): goal.json for a research run, task.json for a code task."""
    run = Path(run)
    if not (run / "goal.json").is_file() and (run / "task.json").is_file():
        t = task.load(run)
        return "task.json", t, task.validate_budget(t.get("budget"), "task.json budget")
    g = goal.load(run)
    return "goal.json", g, goal.validate({key: g.get(key) for key in goal.USER_FIELDS})


def status(run, now=None):
    """Return {spent, caps, unmetered, exceeded}. Raises ValueError."""
    name, g, errors = _record(run)
    budget = g.get("budget", {})
    if not isinstance(budget, dict):
        raise ValueError(f"{name} budget must be an object")
    for k in CAPS:
        if k not in budget:
            raise ValueError(f"{name} budget missing: {k} (no default exists)")
    if errors:
        raise ValueError("; ".join(errors))
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
    if not goal._is_number(spent["usd_estimate_cap"]):
        raise ValueError("non-finite total cost in journal")
    unmetered = sum(1 for e in entries if e["cost_usd"] is None)
    exceeded = [k for k in CAPS if spent[k] > caps[k]]
    return {"spent": spent, "caps": caps, "unmetered": unmetered, "exceeded": exceeded,
            "longest_gap": longest_gap(created, entries)}


def longest_gap(created, entries):
    """(minutes, end timestamp) of the longest quiet stretch, or None when the journal is empty.

    The stretch from `created_at` to the first line counts, so a run left open before its first
    action is reported like any other pause. Nothing here is subtracted from the spent minutes:
    the cap is wall clock because the user set it that way (CLAUDE.md invariant 4), and this only
    says where those minutes went.
    """
    marks = [created] + [datetime.fromisoformat(e["ts"]) for e in entries]
    gaps = [(b - a, b) for a, b in zip(marks, marks[1:])]
    if not gaps:
        return None
    widest, end = max(gaps, key=lambda g: g[0])
    return int(widest.total_seconds() // 60), end.isoformat()


def line(st):
    s, c = st["spent"], st["caps"]
    return (f"spent: {s['minutes']}/{c['minutes']} min, "
            f"{s['max_actions']}/{c['max_actions']} actions, "
            f"{s['max_subagents']}/{c['max_subagents']} subagents, "
            f"~${s['usd_estimate_cap']:.2f}/${_money(c['usd_estimate_cap'])} "
            f"(unmetered: {st['unmetered']})")


def pause_line(st):
    """The second output line, or None when the journal is empty."""
    if st["longest_gap"] is None:
        return None
    minutes, end = st["longest_gap"]
    return (f"minutes are wall clock since created_at; longest quiet stretch: "
            f"{minutes} min, ending {end}")


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
    pause = pause_line(st)
    if pause:
        print(pause)
    if st["exceeded"]:
        for k in st["exceeded"]:
            print(f"exceeded: {k} ({st['spent'][k]}/{st['caps'][k]})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
