#!/usr/bin/env python3
"""Render FINDINGS.md and HANDOFF.md for a run, from its records only.

Usage:
  python3 scripts/report.py --run <run-dir>

Reads goal.json (through goal.load, so a tampered goal is refused), claims.jsonl,
evidence.jsonl, hypotheses.json (through rank.load, optional), spark.json (optional),
objections.json (optional, saved from the Reflection role), journal.jsonl (disconfirm lines)
and the spend line from budget.py. Every sentence in the output is either a fixed
heading or gloss from this file, or text copied from one of those records. Nothing
is summarised, inferred, or reworded.

FINDINGS.md sections: What you asked; What we found; Unreviewed (objections file unreadable),
only when there is one; Disputed; Unverified; Superseded; How sure;
What we tried that did not work; What is still unknown; What to build now; Spend.
HANDOFF.md sections: Goal; Chosen approach (with the Elo table); Acceptance;
Files likely touched; Must not.

A claim with no evidence ids appears only under "Unverified" (CLAUDE.md invariant 2).
The top-rated open hypothesis is written "Chosen" only once it has been challenged: an
evidence record with stance contradicts names it, or a journal disconfirm line does (S-75).
Until then HANDOFF.md names it "Leading" with a fixed line, FINDINGS.md lists every
unchallenged open hypothesis under "What is still unknown", and the JSON handoff sets
next_investigation.challenged to false.
A claim superseded by a later claim (claims.py supersede) appears only under "Superseded".
A claim named in `claim_ids` of an objection with `blocking: true` appears only under
"Disputed" (S-17, bug 5); a missing objections.json is said in one fixed line. An objections.json
that exists but cannot be read as objections leaves "What we found" empty and lists those claims
under "Unreviewed (objections file unreadable)", which is what the JSON handoff already says
(S-48, bug 23); the line names the first objection that could not be read and why.
Exit 0 ok, 1 when goal.json is missing or tampered.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import claims  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402
import journal  # noqa: E402
import rank  # noqa: E402
import spark  # noqa: E402

FINDINGS = "FINDINGS.md"
OBJECTIONS = "objections.json"
HANDOFF = "HANDOFF.md"
REFUTED = "refuted"
GLOSS = {
    "observed": "seen directly in a record",
    "inferred": "follows from records, not seen directly",
    "predicted": "expected if the finding holds, not yet seen",
}
NONE = "None recorded."
# Every sentence the report may contain that is not copied from a record. Nothing else.
FIXED = {
    "none": NONE,
    "found_intro": "Each finding is one claim with the evidence records that back it; "
                   "[E-n] names the record and where in the source it was seen.",
    "disputed_intro": "Claims with evidence that a blocking objection from Reflection holds out "
                      "of the findings until resolved with new evidence.",
    "disputed_by": "Objection",
    "no_objections_file": f"No {OBJECTIONS} in the run folder: no saved Reflection review.",
    "bad_objections_file": f"{OBJECTIONS} could not be read as objections; nothing is treated as disputed.",
    "unverified_intro": "Claims with no evidence record. Not findings.",
    "superseded_intro": "Claims replaced by a later claim with evidence. The replacement is "
                        "the finding; these are kept so the correction is visible.",
    "superseded_by": "Superseded by",
    "how_sure_intro": "Claim type: " + "; ".join(f"{k} = {v}" for k, v in GLOSS.items()) + ".",
    "no_limitations": "none stated",
    "build_now": f"See {HANDOFF} in this folder.",
    "elo_gloss": "Elo is a rating moved only by head-to-head comparisons; it orders what to "
                 "investigate, it does not verify anything.",
    "beat_none": "Beat: no pair judged against it.",
    "unchallenged": "Not chosen: nothing recorded challenges it. Record evidence with stance "
                    "contradicts, or a journal disconfirm line, naming it first.",
    "never_challenged": "(never challenged)",
    "ears_intro": "One sentence per success criterion, in the form WHEN ... THEN ... SHALL.",
    "table_header": rank.table({"hypotheses": []}),
}


def _sources(run, strict=False):
    run = Path(run)
    if strict:
        for name in ("goal.json", evidence.FILENAME, claims.FILENAME, rank.HYPOTHESES,
                     OBJECTIONS, "spark.json", "journal.jsonl", "meta.md"):
            if (run / name).is_symlink():
                raise ValueError(f"symlink run record is not allowed: {name}")
    g = goal.load(run)
    ev = {r["evidence_id"]: r for r in evidence.read(run)}
    cl = claims.read(run)
    try:
        hyps = rank.load(run)["hypotheses"]
    except ValueError:
        if strict and (run / rank.HYPOTHESES).exists():
            raise
        hyps = []
    sparks = spark.load(run)["sparks"]
    return g, ev, cl, hyps, sparks


def _bad_note(where, exc):
    """The bad-file line, naming the first thing that could not be read and why."""
    reason = f"missing key {exc}" if isinstance(exc, KeyError) else str(exc) or type(exc).__name__
    return f"{FIXED['bad_objections_file']} First problem in {where}: {reason}."


def _review_records(run):
    path = Path(run) / OBJECTIONS
    if not path.exists():
        return [], FIXED["no_objections_file"]
    try:
        items = json.loads(path.read_text(encoding="utf-8"))["objections"]
        if not isinstance(items, list):
            raise ValueError("objections must be a list")
        known_claims = {c["claim_id"] for c in claims.read(run)}
    except (ValueError, KeyError, TypeError) as exc:
        return [], _bad_note("the file", exc)
    for index, obj in enumerate(items):
        try:
            if not isinstance(obj, dict) or type(obj["blocking"]) is not bool:
                raise ValueError("blocking must be JSON true or false")
            if not claims._str_list(obj["claim_ids"]) or set(obj["claim_ids"]) - known_claims:
                raise ValueError("claim_ids must reference known claims")
            for key in ("id", "resolve_with"):
                if not claims._nonempty_str(obj[key]):
                    raise ValueError(f"objection {key} must be a non-empty string")
        except (ValueError, KeyError, TypeError) as exc:
            return [], _bad_note(f"objection {index}", exc)
    return items, None


def _blocking(items):
    blocked = {}
    for obj in items:
        if obj["blocking"]:
            for cid in obj["claim_ids"]:
                blocked.setdefault(cid, []).append((obj["id"], obj["resolve_with"]))
    return blocked


def objections(run):
    """(blocking objections by claim_id, fixed note or None).

    Missing file -> ({}, no_objections_file). Malformed file -> ({}, bad_objections_file plus the
    first objection that could not be read and why).
    Blocking only; a claim under several blocking objections keeps all of them.
    """
    items, note = _review_records(run)
    return _blocking(items), note


def _unreadable(note):
    """True when objections.json exists but could not be read as objections."""
    return note is not None and note != FIXED["no_objections_file"]


def _claim_groups(records, blocked):
    groups = {name: [] for name in ("evidence_backed", "disputed", "unverified", "superseded")}
    for claim in records:
        status = ("superseded" if claim.get("superseded_by") else
                  "unverified" if not claim["evidence_ids"] else
                  "disputed" if claim["claim_id"] in blocked else "evidence_backed")
        groups[status].append(claim)
    return groups


def _ranked(hyps):
    return sorted(hyps, key=lambda h: (-h["elo"], h["id"]))


def beaten(run, chosen, hyps):
    """Highest-rated hypothesis `chosen` has a recorded win over in comparisons.jsonl, or None."""
    losers = set()
    for c in rank._jsonl(Path(run) / rank.COMPARISONS):
        if c["winner_id"] == chosen:
            losers.add(c["b"] if c["a"] == chosen else c["a"])
    ranked = _ranked([h for h in hyps if h["id"] in losers])
    return ranked[0] if ranked else None


def challenged(run, ev):
    """Hypothesis ids named by a contradicts evidence record or a journal disconfirm line."""
    ids = set()
    for r in ev.values():
        if r.get("stance") == "contradicts":
            ids.update(r["hypothesis_ids"])
    for e in journal.read(run):
        if e["kind"] == "disconfirm":
            ids.update(e["hypothesis_ids"])
    return ids


def _evidence_ref(ev, eid):
    r = ev[eid]
    return f"[{eid}] {r['title']}, {r['locator']}"


def _bullets(items, empty=NONE):
    return [f"- {i}" for i in items] if items else [empty]


def findings(run):
    g, ev, cl, hyps, sparks = _sources(run)
    blocked, note = objections(run)
    groups = _claim_groups(cl, blocked)
    superseded, disputed, verified, unverified = (groups[key] for key in
                                                 ("superseded", "disputed", "evidence_backed", "unverified"))
    unreviewed = []
    if _unreadable(note):
        unreviewed, verified = verified, []
    out = [f"# Findings for goal {g['goal_id']} (revision {g['revision']})", ""]
    out += ["## What you asked", "", g["request_text"], "", f"Wanted: {g['desired_outcome']}", ""]
    out += ["## What we found", "", FIXED["found_intro"], ""]
    if verified:
        for c in verified:
            refs = "; ".join(_evidence_ref(ev, e) for e in c["evidence_ids"])
            out += [f"**{c['claim_id']}** {c['statement']} Evidence: {refs}.", ""]
    else:
        out += [NONE, ""]
    if unreviewed:
        out += ["## Unreviewed (objections file unreadable)", "", note, ""]
        out += _bullets([f"{c['claim_id']} {c['statement']}" for c in unreviewed]) + [""]
    out += ["## Disputed", "", FIXED["disputed_intro"], ""]
    if note:
        out += [note, ""]
    out += _bullets([f"{c['claim_id']} {c['statement']} {FIXED['disputed_by']} {oid}: {fix}"
                     for c in disputed for oid, fix in blocked[c["claim_id"]]]) + [""]
    out += ["## Unverified", "", FIXED["unverified_intro"], ""]
    out += _bullets([f"{c['claim_id']} {c['statement']}" for c in unverified]) + [""]
    out += ["## Superseded", "", FIXED["superseded_intro"], ""]
    out += _bullets([f"{c['claim_id']} {c['statement']} {FIXED['superseded_by']} "
                     f"{c['superseded_by']}: {c['reason']}" for c in superseded]) + [""]
    out += ["## How sure", "", FIXED["how_sure_intro"], ""]
    out += _bullets([f"{c['claim_id']}: {c['claim_type']}. Limitations: {c['limitations'] or FIXED['no_limitations']}"
                     for c in verified]) + [""]
    out += ["## What we tried that did not work", ""]
    tried = [f"{h['id']} {h['statement']} (refuted)" for h in hyps if h.get("status") == REFUTED]
    tried += [f"{s['id']} {s['observation']} (did not repeat)" for s in sparks if s["state"] == spark.NOISE]
    out += _bullets(tried) + [""]
    out += ["## What is still unknown", ""]
    unknown = list(g["unknowns"])
    tested = challenged(run, ev)
    unknown += [f"{h['id']} {h['statement']} {FIXED['never_challenged']}" for h in hyps
                if h.get("status") == rank.ELIGIBLE_STATUS and h["id"] not in tested]
    unknown += [f"{s['id']} {s['observation']} (spark in {s['state']})"
                for s in sparks if s["state"] not in (spark.NOISE, spark.STATES[-1])]
    out += _bullets(unknown) + [""]
    out += ["## What to build now", "", FIXED["build_now"], ""]
    out += ["## Spend", "", budget.line(budget.status(run)), ""]
    return "\n".join(out)


def _ears(criterion):
    m, ev, env, pc = (criterion[k].strip().rstrip(".") for k in
                      ("measurement", "evaluator", "environment", "pass_condition"))
    return f"WHEN {m} is measured by {ev} in {env} THEN the result SHALL satisfy: {pc}."


def handoff(run):
    g, ev, cl, hyps, sparks = _sources(run)
    ranked = _ranked([h for h in hyps if h.get("status") == rank.ELIGIBLE_STATUS])
    out = [f"# Handoff for goal {g['goal_id']} (revision {g['revision']})", ""]
    out += ["## Goal", "", g["desired_outcome"], "", f"Scope: {g['scope']}", ""]
    out += ["## Chosen approach", "", FIXED["elo_gloss"], ""]
    if ranked:
        chosen = ranked[0]
        beat = beaten(run, chosen["id"], hyps)
        if chosen["id"] in challenged(run, ev):
            out += [f"Chosen: {chosen['id']} {chosen['statement']}", ""]
        else:
            out += [f"Leading: {chosen['id']} {chosen['statement']}", "", FIXED["unchallenged"], ""]
        out += [f"Beat: {beat['id']} {beat['statement']}" if beat else FIXED["beat_none"], ""]
    else:
        out += [NONE, ""]
    if hyps:
        out += ["```", rank.table({"hypotheses": hyps}), "```", ""]
    out += ["## Acceptance", "", FIXED["ears_intro"], ""]
    for c in g["success_criteria"]:
        out += [_ears(c), ""]
    out += ["## Files likely touched", ""]
    files = sorted({r["source_uri"] for r in ev.values() if r["source_type"] == "file"})
    out += _bullets(files) + [""]
    out += ["## Must not", ""]
    out += _bullets(list(g["prohibited_actions"])) + [""]
    return "\n".join(out)


def structured_handoff(run):
    run = Path(run)
    g, ev, cl, hyps, sparks = _sources(run, strict=True)
    if len(ev) != len(evidence.read(run)):
        raise ValueError("duplicate evidence_id")
    claim_ids = [r["claim_id"] for r in claims._lines(run) if "statement" in r]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("duplicate claim_id")
    for record in ev.values():
        errors = evidence.validate({key: record.get(key) for key in evidence.USER_FIELDS} |
                                   {key: record[key] for key in evidence.OPTIONAL_FIELDS if key in record})
        if errors:
            raise ValueError("; ".join(errors))
        if not claims._nonempty_str(record["evidence_id"]) or not claims._nonempty_str(record.get("retrieved_at")):
            raise ValueError("invalid evidence identity or timestamp")
        if record.get("sha256") != hashlib.sha256(record["excerpt"].encode("utf-8")).hexdigest():
            raise ValueError(f"evidence sha256 mismatch: {record['evidence_id']}")
    by_claim = {c["claim_id"]: c for c in cl}
    for claim in cl:
        errors = claims.validate({key: claim.get(key) for key in claims.USER_FIELDS}, set(ev))
        if errors:
            raise ValueError("; ".join(errors))
        if not claims._nonempty_str(claim["claim_id"]):
            raise ValueError("invalid claim_id")
        if "superseded_by" in claim and (not claims._nonempty_str(claim["superseded_by"])
                                        or claim["superseded_by"] not in by_claim
                                        or not claims._nonempty_str(claim.get("reason"))):
            raise ValueError("invalid superseded claim reference")
    review, note = _review_records(run)
    blocked = _blocking(review)
    groups = _claim_groups(cl, blocked)
    if note:
        groups["unreviewed"] = groups["evidence_backed"]
        groups["evidence_backed"] = []
    statuses = {c["claim_id"]: status for status, entries in groups.items() for c in entries}
    exported_claims = []
    for claim in cl:
        entry = {key: claim[key] for key in ("claim_id", *claims.USER_FIELDS)}
        entry["status"] = statuses[claim["claim_id"]]
        if claim.get("superseded_by"):
            entry.update(superseded_by=claim["superseded_by"], reason=claim["reason"])
        exported_claims.append(entry)
    ranked = _ranked([h for h in hyps if h.get("status") == rank.ELIGIBLE_STATUS])
    next_investigation = None
    if ranked:
        next_investigation = {"hypothesis_id": ranked[0]["id"], "statement": ranked[0]["statement"],
                              "selection_basis": "elo_scheduling_only", "verified_solution": False,
                              "challenged": ranked[0]["id"] in challenged(run, ev)}
    review_status = "recorded" if note is None else "missing" if note == FIXED["no_objections_file"] else "invalid"
    return {
        "schema_version": 1,
        "record_type": "research-handoff",
        "content_policy": "data_only",
        "authorizes_actions": False,
        "goal": g,
        "success_criteria_status": "not_evaluated",
        "review": {"status": review_status, "coverage": "not_attested", "note": note,
                   "objections": review, "blocking_objections": blocked},
        "claims": exported_claims,
        "findings": [c["claim_id"] for c in groups["evidence_backed"]],
        "evidence": [{key: record[key] for key in ("evidence_id", *evidence.USER_FIELDS, *evidence.OPTIONAL_FIELDS,
                                                   "retrieved_at", "sha256") if key in record}
                     for record in ev.values()],
        "next_investigation": next_investigation,
        "unknowns": g["unknowns"],
        "sparks": sparks,
        "meta_review": (run / "meta.md").read_text(encoding="utf-8") if (run / "meta.md").exists() else None,
        "spend": budget.status(run),
    }


def write(run):
    run = Path(run)
    f, h = findings(run), handoff(run)
    (run / FINDINGS).write_text(f, encoding="utf-8")
    (run / HANDOFF).write_text(h, encoding="utf-8")
    return run / FINDINGS, run / HANDOFF


def main(argv):
    p = argparse.ArgumentParser(prog="report.py")
    p.add_argument("--run", required=True)
    p.add_argument("--json", action="store_true", help="print a data-only structured handoff without writing files")
    args = p.parse_args(argv[1:])
    try:
        if args.json:
            print(json.dumps(structured_handoff(args.run), indent=2, ensure_ascii=False, allow_nan=False))
        else:
            for path in write(args.run):
                print(path)
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
