#!/usr/bin/env python3
"""Judge one recorded claim against its own excerpts, before Reflection ever sees it.

Usage:
  python3 scripts/judge.py run       --run <run-dir> --battery claim --id C-7 \
      [--adapter jev|fake] [--fake-answers <json>] [--mode shadow|gate]
  python3 scripts/judge.py questions --battery claim

`run` prints exactly one line and nothing else:

  judge: claim C-7 yes | no | unsure          a decision, recorded in judge.jsonl
  judge: claim C-7 no (rule: number ...)      a decision made in code, with no call
  judge: claim C-7 skipped: <reason>          nothing was sent and nothing was written

A decision is data (CLAUDE.md invariant 3). Nothing here edits a claim, an evidence record,
the goal or the budget, and a `yes` verifies nothing: only an evidence record does. Shadow is
the only mode this script has, so the exit code is 0 whatever the decision and the run
proceeds exactly as it does today.

Before anything leaves the machine, in this order, each stop printing `skipped: <reason>`,
exiting 0 and writing nothing: the run folder is not <root>/AGI_Research/runs/<id>; the
workspace has no .research-council/judge.json carrying enabled_by, date and terms_read true;
budget.py reports a cap already exceeded, a zero dollar cap, or one more action than the
action cap allows; a cited evidence record's access_scope is not public; the assembled state
carries an address, a run of digits long enough to be a phone number, a key-shaped token or a
home directory path; the state is longer than 60000 characters; TYPESAFE_API_KEY is not in the
environment; the adapter raised.

Every number in the statement must appear in one of the cited excerpts. A missing one is a
`no` decided in code with no call, which is the rule agents/reflection.md already gives the
Reflection role.

When a decision is recorded the journal line is written first and the judge record second,
inside one try, so a call that happened is never unlogged (CLAUDE.md invariant 4). No
threshold is defined here: `fitted` stays None until a calibration on labelled cases fills it
in, and until then every answered decision is `unsure`.

Exit 0 in shadow mode whatever the decision, 1 on bad input: an unknown battery or claim id, a
run with no goal.json, `--mode gate` (not wired until thresholds exist), or `--adapter fake`
without `--fake-answers`.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import claims  # noqa: E402
import evidence  # noqa: E402
import journal  # noqa: E402

FILENAME = "judge.jsonl"
OPT_IN = Path(".research-council") / "judge.json"
BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
MODEL = "jev-1.13.0"
USD_PER_M_INPUT = 0.042  # docs.typesafe.ai/models, checked 2026-09-21 by run 65a47056; output free
TIMEOUT = 30.0
STATE_MAX = 60000
NUMBER = re.compile(r"\d[\d,.]*")
EGRESS = (
    ("address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    # RESEARCH R-9 (confidence: medium): a version list or a benchmark table looks like this too;
    # S-53's exporter counts how often it stops an ordinary excerpt.
    ("phone", re.compile(r"\+?\d[\d\s().-]{8,}\d")),
    ("key", re.compile(r"apikey_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}"
                       r"|AKIA[0-9A-Z]{16}|Bearer\s+\S{16,}")),
    ("home path", re.compile(r"/Users/[^/\s]+")),
)
CLAIM_STATE_FIELDS = ("statement", "scope", "claim_type")
BATTERIES = {
    "claim": {
        "record": "goal.json",
        "questions": {
            "supported": {
                "type": "noul",
                "instructions": "The `evidence` excerpts state what the `claim.statement` says.",
                "criteria": {
                    "true": "At least one excerpt contains the same fact as the statement, in the "
                            "same words or a paraphrase with the same meaning.",
                    "false": "No excerpt contains the fact: the excerpts are about something else, "
                             "or say less than the statement.",
                },
            },
            "contradicted": {
                "type": "noul",
                "instructions": "An `evidence` excerpt says the opposite of the `claim.statement`.",
                "criteria": {
                    "true": "An excerpt asserts a fact that cannot be true at the same time as the "
                            "statement.",
                    "false": "No excerpt disagrees with the statement, including excerpts that are "
                             "silent about it.",
                },
            },
            "wider": {
                "type": "noul",
                "instructions": "The `claim.statement` or `claim.scope` claims more than the "
                                "excerpts show.",
                "criteria": {
                    "true": "The statement generalises to more systems, people, time periods, "
                            "conditions or products than the excerpts describe.",
                    "false": "The statement stays within what the excerpts describe, or is "
                             "narrower.",
                },
            },
            "inferred": {
                "type": "noul",
                "instructions": "The `claim.statement` is a conclusion drawn from the excerpts "
                                "rather than something an excerpt says.",
                "criteria": {
                    "true": "Reaching the statement needs a reasoning step, a comparison, or "
                            "combining two excerpts.",
                    "false": "An excerpt says the statement directly.",
                },
            },
        },
        "thresholds": None,
        "fitted": None,
    },
}


class AdapterError(RuntimeError):
    """The call produced no usable answers. In shadow mode this is a skipped line, not a crash."""


def battery(name):
    """One battery definition. Raises ValueError for an unknown name."""
    if name not in BATTERIES:
        raise ValueError(f"unknown battery: {name} (one of {', '.join(sorted(BATTERIES))})")
    return BATTERIES[name]


def workspace(run):
    """The workspace above <root>/AGI_Research/runs/<id>, or None when the folder is elsewhere."""
    parents = list(Path(run).resolve().parents)
    if len(parents) < 3 or parents[0].name != "runs" or parents[1].name != "AGI_Research":
        return None
    return parents[2]


def enabled(root):
    """True when the workspace carries a complete opt-in file. A missing or partial file is False."""
    if root is None:
        return False
    try:
        body = json.loads((root / OPT_IN).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(body, dict) or body.get("terms_read") is not True:
        return False
    return all(isinstance(body.get(f), str) and body[f].strip() for f in ("enabled_by", "date"))


def budget_reason(run):
    """'budget' when a cap already stops this call, else None. Raises ValueError on a bad record."""
    st = budget.status(run)
    if st["exceeded"] or st["caps"]["usd_estimate_cap"] == 0:
        return "budget"
    if st["spent"]["max_actions"] + 1 > st["caps"]["max_actions"]:
        return "budget"
    return None


def _numbers(text):
    """Number tokens as they are compared: thousands commas dropped, trailing dots dropped."""
    out = []
    for raw in NUMBER.findall(text):
        token = raw.replace(",", "").rstrip(".")
        if token:
            out.append(token)
    return out


def numbers_missing(statement, excerpts):
    """Number tokens in the statement that no excerpt carries. Reflection's own rule, in code."""
    seen = set()
    for excerpt in excerpts:
        seen.update(_numbers(excerpt))
    return [token for token in _numbers(statement) if token not in seen]


def build_claim_state(run, claim_id):
    """(state, cited records) for one claim. Raises ValueError when the id is unknown."""
    by_id = {c["claim_id"]: c for c in claims.read(run)}
    if claim_id not in by_id:
        raise ValueError(f"unknown claim_id: {claim_id}")
    claim = by_id[claim_id]
    records = {r["evidence_id"]: r for r in evidence.read(run)}
    cited = [records[eid] for eid in claim["evidence_ids"] if eid in records]
    state = {
        "claim": {f: claim[f] for f in CLAIM_STATE_FIELDS},
        "evidence": [{"id": r["evidence_id"], "uri": r["source_uri"],
                      "locator": r["locator"], "excerpt": r["excerpt"]} for r in cited],
    }
    return state, cited


def egress_check(payload, records):
    """The first reason this state may not leave the machine, or None. Private records come first."""
    for record in records:
        if record.get("access_scope") != "public":
            return f"egress private {record['evidence_id']}"
    for name, pattern in EGRESS:
        if pattern.search(payload):
            return f"egress {name}"
    return None


def probability(answer):
    """The probability in one noul answer.

    RESEARCH R-8 (confidence: low): the jev skill's own scripts read two different shapes for
    the same field, a bare number and {"noul": <p>}. Both are accepted here and anything else
    raises, so an unexpected body is a skipped line rather than a wrong decision.
    """
    if isinstance(answer, dict) and "noul" in answer:
        answer = answer["noul"]
    if isinstance(answer, bool) or not isinstance(answer, (int, float)):
        raise AdapterError(f"answer is not a probability: {answer!r}")
    return float(answer)


def adapter_jev(state, questions, opener=None, model=MODEL, timeout=TIMEOUT):
    """POST /v1/systemone. Returns {answers, model, input_tokens, cost_usd}. Raises AdapterError."""
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + "/v1/systemone", data=body, method="POST",
        headers={"Authorization": f"Bearer {os.environ.get('TYPESAFE_API_KEY', '').strip()}",
                 "Content-Type": "application/json"})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise AdapterError(str(error)) from None
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise AdapterError("no answers in the response")
    tokens = payload.get("usage", {}).get("input_tokens") or 0
    return {"answers": payload["answers"], "model": payload.get("model", model),
            "input_tokens": tokens, "cost_usd": tokens * USD_PER_M_INPUT / 1_000_000}


def adapter_fake(path):
    """Answers read from a JSON file. For tests and dry runs; it never opens a socket."""
    try:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AdapterError(str(error)) from None
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        raise AdapterError(f"fake answers file needs an answers object: {path}")
    return {"answers": body["answers"], "model": body.get("model", "fake"),
            "input_tokens": body.get("input_tokens", 0), "cost_usd": body.get("cost_usd", 0.0)}


def decide(answers, thresholds):
    """yes, no or unsure. Without fitted thresholds every answered decision is unsure."""
    if not thresholds:
        return "unsure"
    low = {name: answers[name] <= thresholds[name]["low"] for name in answers}
    high = {name: answers[name] >= thresholds[name]["high"] for name in answers}
    if low["supported"] or high["contradicted"] or high["wider"]:
        return "no"
    if high["supported"] and all(low[name] for name in ("contradicted", "wider", "inferred")):
        return "yes"
    return "unsure"


def _skipped(name, subject, reason):
    return f"judge: {name} {subject} skipped: {reason}", None


def _record(run, name, subject, decision, result, answers, note=None):
    """Journal line first, judge record second, so a call that happened is never unlogged."""
    detail = (f"judge {name} {subject} {decision} model={result['model']} "
              f"tokens={result['input_tokens']}")
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "battery": name, "subject": subject, "adapter": result["adapter"],
              "model": result["model"], "input_tokens": result["input_tokens"],
              "cost_usd": result["cost_usd"], "answers": answers, "decision": decision,
              "mode": "shadow"}
    try:
        journal.add(run, "judge", result["cost_usd"], detail)
        with (Path(run) / FILENAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        raise ValueError(f"the decision could not be recorded: {error}") from None
    return f"judge: {name} {subject} {decision}" + (f" ({note})" if note else ""), record


def run_battery(run, name, subject, adapter="jev", fake_answers=None, opener=None):
    """Decide one subject. Returns (line to print, record or None). Raises ValueError on bad input."""
    spec = battery(name)
    run = Path(run)
    if not (run / spec["record"]).is_file():
        raise ValueError(f"no {spec['record']} in {run}; the {name} battery judges a research run")
    if adapter == "fake" and not fake_answers:
        raise ValueError("--adapter fake needs --fake-answers <path>")
    root = workspace(run)
    if root is None or not enabled(root):
        return _skipped(name, subject, "not enabled")
    reason = budget_reason(run)
    if reason:
        return _skipped(name, subject, reason)
    state, cited = build_claim_state(run, subject)
    payload = json.dumps(state, ensure_ascii=False)
    reason = egress_check(payload, cited)
    if reason:
        return _skipped(name, subject, reason)
    if len(payload) > STATE_MAX:
        return _skipped(name, subject, "size")
    missing = numbers_missing(state["claim"]["statement"],
                              [item["excerpt"] for item in state["evidence"]])
    if missing:
        rule = {"adapter": "rule", "model": "rule", "input_tokens": 0, "cost_usd": 0.0}
        return _record(run, name, subject, "no", rule, {},
                       note=f"rule: number {missing[0]} not in any excerpt")
    if adapter == "jev" and not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return _skipped(name, subject, "no key")
    try:
        result = (adapter_fake(fake_answers) if adapter == "fake"
                  else adapter_jev(state, spec["questions"], opener))
        absent = [q for q in spec["questions"] if q not in result["answers"]]
        if absent:
            raise AdapterError(f"no answer for {', '.join(absent)}")
        answers = {q: probability(result["answers"][q]) for q in spec["questions"]}
    except AdapterError as error:
        return _skipped(name, subject, f"adapter {error}")
    result["adapter"] = adapter
    decision = decide(answers, spec["thresholds"] if spec["fitted"] else None)
    return _record(run, name, subject, decision, result, answers)


def main(argv):
    p = argparse.ArgumentParser(prog="judge.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run", required=True)
    r.add_argument("--battery", required=True)
    r.add_argument("--id", dest="subject", required=True)
    r.add_argument("--adapter", default="jev", choices=("jev", "fake"))
    r.add_argument("--fake-answers")
    r.add_argument("--mode", default="shadow", choices=("shadow", "gate"))
    q = sub.add_parser("questions")
    q.add_argument("--battery", required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "questions":
            print(json.dumps(battery(args.battery)["questions"], indent=2, ensure_ascii=False))
            return 0
        if args.mode == "gate":
            raise ValueError("--mode gate has no fitted thresholds to gate on; shadow mode only")
        line, _ = run_battery(args.run, args.battery, args.subject, args.adapter,
                              args.fake_answers)
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
