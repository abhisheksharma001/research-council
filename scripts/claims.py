#!/usr/bin/env python3
"""Record claims in a run's claims.jsonl and list the unverified ones.

Usage:
  python3 scripts/claims.py add  --run <run-dir> --from <json|->
  python3 scripts/claims.py list --run <run-dir> [--unverified]

Input JSON for add (see skills/research-council/references/evidence.md):
  statement     the claim in one sentence
  claim_type    observed | inferred | predicted
  scope         where the claim holds (system, data range, environment)
  evidence_ids  list of evidence_id values; every one must exist in evidence.jsonl
  test_ids      list of test ids (may be empty; not checked until S-10 exists)
  limitations   what the claim does not cover (string, may be empty)

A claim with an empty evidence_ids list is stored but is unverified (CLAUDE.md
invariant 2). A claim naming an evidence_id that does not exist is refused and
nothing is written. The script adds claim_id (C-<n>).

Exit 0 ok, 1 invalid input.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402

CLAIM_TYPES = ("observed", "inferred", "predicted")
USER_FIELDS = ("statement", "claim_type", "scope", "evidence_ids", "test_ids", "limitations")
FILENAME = "claims.jsonl"
ID_PREFIX = "C-"


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def _str_list(v):
    return isinstance(v, list) and all(_nonempty_str(x) for x in v)


def validate(body, known_evidence):
    """Return a list of error strings, empty when the claim is valid."""
    if not isinstance(body, dict):
        return ["claim must be a JSON object"]
    errors = [f"unknown field: {k}" for k in body if k not in USER_FIELDS]
    errors += [f"missing field: {f}" for f in USER_FIELDS if f not in body]
    if errors:
        return errors
    for f in ("statement", "scope"):
        if not _nonempty_str(body[f]):
            errors.append(f"invalid field: {f} (must be a non-empty string)")
    if body["claim_type"] not in CLAIM_TYPES:
        errors.append(f"invalid field: claim_type (one of {', '.join(CLAIM_TYPES)})")
    if not isinstance(body["limitations"], str):
        errors.append("invalid field: limitations (must be a string)")
    for f in ("evidence_ids", "test_ids"):
        if not _str_list(body[f]):
            errors.append(f"invalid field: {f} (must be a list of non-empty strings)")
    if errors:
        return errors
    ids = body["evidence_ids"]
    if len(set(ids)) != len(ids):
        errors.append("invalid field: evidence_ids (duplicates)")
    for eid in ids:
        if eid not in known_evidence:
            errors.append(f"unknown evidence_id: {eid}")
    return errors


def read(run):
    """Return all claims; an absent file is an empty list."""
    path = Path(run) / FILENAME
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def add(run, body):
    """Validate against evidence.jsonl and append one claim. Returns it. Raises ValueError."""
    run = Path(run)
    if not (run / "goal.json").is_file():
        raise ValueError(f"no goal.json in {run}; run goal.py new first")
    known = {r["evidence_id"] for r in evidence.read(run)}
    errors = validate(body, known)
    if errors:
        raise ValueError("\n".join(errors))
    claim = {"claim_id": evidence.next_id([c["claim_id"] for c in read(run)], ID_PREFIX)}
    claim.update({f: body[f] for f in USER_FIELDS})
    with (run / FILENAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(claim, ensure_ascii=False) + "\n")
    return claim


def unverified(claims):
    return [c for c in claims if not c["evidence_ids"]]


def line(claim):
    ev = ", ".join(claim["evidence_ids"]) if claim["evidence_ids"] else "unverified"
    return f"{claim['claim_id']} {claim['claim_type']} [{ev}] {claim['statement']}"


def _read_json(path):
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def main(argv):
    p = argparse.ArgumentParser(prog="claims.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--run", required=True)
    a.add_argument("--from", dest="src", required=True)
    b = sub.add_parser("list")
    b.add_argument("--run", required=True)
    b.add_argument("--unverified", action="store_true")
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "add":
            claim = add(args.run, _read_json(args.src))
            print(f"{claim['claim_id']} recorded ({len(claim['evidence_ids'])} evidence)")
        else:
            claims = read(args.run)
            for c in unverified(claims) if args.unverified else claims:
                print(line(c))
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
