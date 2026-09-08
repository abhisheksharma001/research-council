#!/usr/bin/env python3
"""Record one piece of evidence in a run's evidence.jsonl.

Usage:
  python3 scripts/evidence.py add --run <run-dir> --from <json|->

Input JSON (see skills/research-council/references/evidence.md):
  source_type   web | file | command | user | paper
  source_uri    where the source lives (URL, path, command line, "user", arXiv id)
  title         short human name for the source
  locator       page, section, line range, timestamp or artifact key; required
  excerpt       the exact text seen, at most 2000 characters; required
  access_scope  public | private

The script adds evidence_id (E-<n>), retrieved_at (UTC) and sha256 of the excerpt.
Anything else in the input is an error. Nothing is defaulted.

Exit 0 ok, 1 invalid input.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_TYPES = ("web", "file", "command", "user", "paper")
ACCESS_SCOPES = ("public", "private")
USER_FIELDS = ("source_type", "source_uri", "title", "locator", "excerpt", "access_scope")
EXCERPT_MAX = 2000
FILENAME = "evidence.jsonl"
ID_PREFIX = "E-"


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate(body):
    """Return a list of error strings, empty when the record is valid."""
    if not isinstance(body, dict):
        return ["evidence must be a JSON object"]
    errors = [f"unknown field: {k}" for k in body if k not in USER_FIELDS]
    errors += [f"missing field: {f}" for f in USER_FIELDS if f not in body]
    if errors:
        return errors
    for f in ("source_uri", "title", "locator"):
        if not _nonempty_str(body[f]):
            errors.append(f"invalid field: {f} (must be a non-empty string)")
    if body["source_type"] not in SOURCE_TYPES:
        errors.append(f"invalid field: source_type (one of {', '.join(SOURCE_TYPES)})")
    if body["access_scope"] not in ACCESS_SCOPES:
        errors.append(f"invalid field: access_scope (one of {', '.join(ACCESS_SCOPES)})")
    ex = body["excerpt"]
    if not _nonempty_str(ex):
        errors.append("invalid field: excerpt (must be a non-empty string)")
    elif len(ex) > EXCERPT_MAX:
        errors.append(f"invalid field: excerpt ({len(ex)} chars, max {EXCERPT_MAX})")
    return errors


def read(run):
    """Return all evidence records; an absent file is an empty list."""
    path = Path(run) / FILENAME
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def next_id(ids, prefix):
    """<prefix><n> where n is one above the highest number already used in ids."""
    highest = 0
    for rid in ids:
        if isinstance(rid, str) and rid.startswith(prefix) and rid[len(prefix):].isdigit():
            highest = max(highest, int(rid[len(prefix):]))
    return f"{prefix}{highest + 1}"


def add(run, body):
    """Validate and append one record. Returns it. Raises ValueError."""
    run = Path(run)
    errors = validate(body)
    if errors:
        raise ValueError("\n".join(errors))
    if not (run / "goal.json").is_file():
        raise ValueError(f"no goal.json in {run}; run goal.py new first")
    record = {"evidence_id": next_id([r["evidence_id"] for r in read(run)], ID_PREFIX)}
    record.update({f: body[f] for f in USER_FIELDS})
    record["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["sha256"] = hashlib.sha256(body["excerpt"].encode("utf-8")).hexdigest()
    with (run / FILENAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_json(path):
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def main(argv):
    p = argparse.ArgumentParser(prog="evidence.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--run", required=True)
    a.add_argument("--from", dest="src", required=True)
    args = p.parse_args(argv[1:])
    try:
        record = add(args.run, _read_json(args.src))
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"{record['evidence_id']} recorded ({record['source_type']}: {record['title']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
