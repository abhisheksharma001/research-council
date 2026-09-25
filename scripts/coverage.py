#!/usr/bin/env python3
"""Coverage gate: count the sources recorded for each of the goal's unknowns before the report.

Usage:
  python3 scripts/coverage.py check --run <run-dir> --min <n>

An evidence record names the unknowns it bears on with its optional `unknowns` field (numbers
from 1, in goal.json order). A source is one distinct `source_uri`: three excerpts from one page
are one source. For every unknown, one line:

  U1 3/2 ok   Whether the assistant configuration was changed ...
  U2 0/2 gap  Whether the upstream API has its own error log ...

then `coverage: all <k> unknowns have <n> sources` or `coverage: <g> of <k> unknowns short`.

Workers stop early: told to research for fifteen minutes, they come back in five, because a
duration reads as enough, not as a floor (docs/research-upgrade-2026-09-25.md section 9). A
count in code is the floor. Exit 2 means re-dispatch a worker into each gap before synthesis,
unless budget.py check already exits 2. The script only reads; it writes nothing.

Exit 0 every unknown met, 2 at least one gap, 1 bad input.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import goal  # noqa: E402


def check(run, minimum):
    """[(number, sources, unknown text)] for every goal unknown. Raises ValueError."""
    if type(minimum) is not int or minimum < 1:
        raise ValueError("--min must be a whole number of at least 1")
    unknowns = goal.load(run)["unknowns"]
    sources = {n: set() for n in range(1, len(unknowns) + 1)}
    for record in evidence.read(run):
        for n in record.get("unknowns", []):
            if n in sources:
                sources[n].add(record["source_uri"])
    return [(n, len(sources[n]), text) for n, text in enumerate(unknowns, 1)]


def main(argv):
    p = argparse.ArgumentParser(prog="coverage.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    c.add_argument("--min", dest="minimum", type=int, required=True)
    args = p.parse_args(argv[1:])
    try:
        rows = check(args.run, args.minimum)
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    short = [n for n, count, _ in rows if count < args.minimum]
    for n, count, text in rows:
        mark = "gap" if n in short else "ok "
        print(f"U{n} {count}/{args.minimum} {mark} {text[:70]}")
    if short:
        print(f"coverage: {len(short)} of {len(rows)} unknowns short")
        return 2
    print(f"coverage: all {len(rows)} unknowns have {args.minimum} sources")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
