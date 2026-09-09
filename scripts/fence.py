#!/usr/bin/env python3
"""After-spawn fence: prove a council role touched only its own file.

Usage:
  python3 scripts/fence.py snapshot --run <run-dir> --role <generation|reflection|ranking|meta-review>
  python3 scripts/fence.py check    --run <run-dir> --role <role>

`snapshot` runs before the spawn. It writes <run>/fence/<role>.json holding every file in
the run folder (recursively) and its sha256. `check` runs after the spawn and compares the
folder with that snapshot. Allowed changes: `hypotheses.json` for generation, `meta.md` for
meta-review, nothing for reflection and ranking. Every other new, changed or removed file is
printed as `violation: <role> wrote <file>` (or `removed`), one `note` naming them is appended
to journal.jsonl, and the exit code is 2. Exit 0 when clean.

`journal.jsonl` and the `fence/` folder are the Supervisor's and are never compared. The
script deletes nothing: the Supervisor decides what to do with a violating file.

Exit 0 clean, 1 bad input or missing snapshot, 2 violation.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal  # noqa: E402

ALLOWED = {
    "generation": {"hypotheses.json"},
    "reflection": set(),
    "ranking": set(),
    "meta-review": {"meta.md"},
}
SKIP = {journal.FILENAME}
FENCE_DIR = "fence"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def listing(run):
    """{relative posix path: sha256} for every file in the run folder except the Supervisor's."""
    run = Path(run)
    out = {}
    for path in sorted(run.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run)
        if rel.parts[0] == FENCE_DIR or rel.as_posix() in SKIP:
            continue
        out[rel.as_posix()] = _sha256(path)
    return out


def _check_inputs(run, role):
    run = Path(run)
    if role not in ALLOWED:
        raise ValueError(f"invalid role: {role!r} (one of {', '.join(ALLOWED)})")
    if not (run / "goal.json").is_file():
        raise ValueError(f"no goal.json in {run}; run goal.py new first")
    return run


def snapshot(run, role):
    """Write <run>/fence/<role>.json. Returns the snapshot dict. Raises ValueError."""
    run = _check_inputs(run, role)
    snap = {"role": role, "taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": listing(run)}
    (run / FENCE_DIR).mkdir(exist_ok=True)
    (run / FENCE_DIR / f"{role}.json").write_text(json.dumps(snap, indent=2) + "\n",
                                                  encoding="utf-8")
    return snap


def violations(run, role):
    """Return [(verb, file)] for every change outside the role's allowed files. Raises ValueError."""
    run = _check_inputs(run, role)
    snap_path = run / FENCE_DIR / f"{role}.json"
    if not snap_path.is_file():
        raise ValueError(f"no snapshot for {role}: run fence.py snapshot before the spawn")
    before = json.loads(snap_path.read_text(encoding="utf-8"))["files"]
    after = listing(run)
    found = []
    for name in sorted(set(before) | set(after)):
        if name in ALLOWED[role]:
            continue
        if name not in before:
            found.append(("wrote", name))
        elif name not in after:
            found.append(("removed", name))
        elif before[name] != after[name]:
            found.append(("wrote", name))
    return found


def check(run, role):
    """Print violations, append one journal note, return the exit code."""
    found = violations(run, role)
    if not found:
        print(f"ok: {role} changed nothing outside {', '.join(sorted(ALLOWED[role])) or 'its reply'}")
        return 0
    for verb, name in found:
        print(f"violation: {role} {verb} {name}")
    journal.add(run, "note", None,
                "fence violation: " + ", ".join(f"{role} {verb} {name}" for verb, name in found))
    return 2


def main(argv):
    p = argparse.ArgumentParser(prog="fence.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("snapshot", "check"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--role", required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "snapshot":
            snap = snapshot(args.run, args.role)
            print(f"snapshot: {args.role} {len(snap['files'])} files")
            return 0
        return check(args.run, args.role)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
