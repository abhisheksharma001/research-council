#!/usr/bin/env python3
"""Render FINDINGS.md and HANDOFF.md for a run, from its records only.

Usage:
  python3 scripts/report.py --run <run-dir>

Reads goal.json (through goal.load, so a tampered goal is refused), claims.jsonl,
evidence.jsonl, hypotheses.json (through rank.load, optional), spark.json (optional)
and the spend line from budget.py. Every sentence in the output is either a fixed
heading or gloss from this file, or text copied from one of those records. Nothing
is summarised, inferred, or reworded.

FINDINGS.md sections: What you asked; What we found; Unverified; Superseded; How sure;
What we tried that did not work; What is still unknown; What to build now; Spend.
HANDOFF.md sections: Goal; Chosen approach (with the Elo table); Acceptance;
Files likely touched; Must not.

A claim with no evidence ids appears only under "Unverified" (CLAUDE.md invariant 2).
A claim superseded by a later claim (claims.py supersede) appears only under "Superseded".
Exit 0 ok, 1 when goal.json is missing or tampered.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import claims  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402
import rank  # noqa: E402
import spark  # noqa: E402

FINDINGS = "FINDINGS.md"
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
    "unverified_intro": "Claims with no evidence record. Not findings.",
    "superseded_intro": "Claims replaced by a later claim with evidence. The replacement is "
                        "the finding; these are kept so the correction is visible.",
    "superseded_by": "Superseded by",
    "how_sure_intro": "Claim type: " + "; ".join(f"{k} = {v}" for k, v in GLOSS.items()) + ".",
    "no_limitations": "none stated",
    "build_now": f"See {HANDOFF} in this folder.",
    "elo_gloss": "Elo is a rating moved only by head-to-head comparisons; it orders what to "
                 "investigate, it does not verify anything.",
    "beat_none": "Beat: nothing; only one hypothesis stands.",
    "ears_intro": "One sentence per success criterion, in the form WHEN ... THEN ... SHALL.",
    "table_header": rank.table({"hypotheses": []}),
}


def _sources(run):
    g = goal.load(run)
    ev = {r["evidence_id"]: r for r in evidence.read(run)}
    cl = claims.read(run)
    try:
        hyps = rank.load(run)["hypotheses"]
    except ValueError:
        hyps = []
    sparks = spark.load(run)["sparks"]
    return g, ev, cl, hyps, sparks


def _ranked(hyps):
    return sorted(hyps, key=lambda h: (-h["elo"], h["id"]))


def _evidence_ref(ev, eid):
    r = ev[eid]
    return f"[{eid}] {r['title']}, {r['locator']}"


def _bullets(items, empty=NONE):
    return [f"- {i}" for i in items] if items else [empty]


def findings(run):
    g, ev, cl, hyps, sparks = _sources(run)
    superseded = [c for c in cl if c.get("superseded_by")]
    live = [c for c in cl if not c.get("superseded_by")]
    verified = [c for c in live if c["evidence_ids"]]
    unverified = claims.unverified(live)
    out = [f"# Findings for goal {g['goal_id']} (revision {g['revision']})", ""]
    out += ["## What you asked", "", g["request_text"], "", f"Wanted: {g['desired_outcome']}", ""]
    out += ["## What we found", "", FIXED["found_intro"], ""]
    if verified:
        for c in verified:
            refs = "; ".join(_evidence_ref(ev, e) for e in c["evidence_ids"])
            out += [f"**{c['claim_id']}** {c['statement']} Evidence: {refs}.", ""]
    else:
        out += [NONE, ""]
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
    ranked = _ranked([h for h in hyps if h.get("status") != REFUTED])
    out = [f"# Handoff for goal {g['goal_id']} (revision {g['revision']})", ""]
    out += ["## Goal", "", g["desired_outcome"], "", f"Scope: {g['scope']}", ""]
    out += ["## Chosen approach", "", FIXED["elo_gloss"], ""]
    if len(ranked) >= 2:
        out += [f"Chosen: {ranked[0]['id']} {ranked[0]['statement']}", "",
                f"Beat: {ranked[1]['id']} {ranked[1]['statement']}", ""]
    elif ranked:
        out += [f"Chosen: {ranked[0]['id']} {ranked[0]['statement']}", "", FIXED["beat_none"], ""]
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


def write(run):
    run = Path(run)
    f, h = findings(run), handoff(run)
    (run / FINDINGS).write_text(f, encoding="utf-8")
    (run / HANDOFF).write_text(h, encoding="utf-8")
    return run / FINDINGS, run / HANDOFF


def main(argv):
    p = argparse.ArgumentParser(prog="report.py")
    p.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        for path in write(args.run):
            print(path)
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
