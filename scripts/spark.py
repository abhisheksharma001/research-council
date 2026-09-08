#!/usr/bin/env python3
"""Fire protocol state machine: track one unexpected observation from spark to skill candidate.

Usage:
  python3 scripts/spark.py new     --run <run-dir> --observation "..." --prediction_before "..." --hypotheses H1[,H2]
  python3 scripts/spark.py trial   --run <run-dir> --spark SP-1 --kind repeat|vary|combine (--ok | --failed)
                                   --detail "..." [--condition "..."] [--evidence E-3]
  python3 scripts/spark.py advance --run <run-dir> --spark SP-1 --to <STATE> [--prediction_after "..."]
  python3 scripts/spark.py status  --run <run-dir> [--spark SP-1]

States, in order (strategies/fire.md): SPARK, REPEAT, VARY, BOUNDARY, COMBINE, NAME.
NOISE is a terminal side exit from REPEAT. A spark only moves forward, and every
target state has requirements that are checked before anything is written:
  REPEAT    nothing
  VARY      at least 2 successful repeat trials
  NOISE     at least 1 failed repeat trial (from REPEAT only)
  BOUNDARY  at least 2 successful repeat trials and 1 failed vary trial
  COMBINE   prediction_after written (given with --prediction_after when advancing to BOUNDARY)
  NAME      at least 1 combine trial

The reward field `progress` is set once, when prediction_after is written, and only
when prediction_after narrows prediction_before: it still contains the old prediction
and adds a scope word (when, only, if, unless, ...). Longer text, different text, or
confident text earns nothing (CLAUDE.md invariant 7).

All sparks of a run live in spark.json. Exit 0 ok, 1 on any refusal.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402

FILENAME = "spark.json"
HYPOTHESES = "hypotheses.json"
ID_PREFIX = "SP-"
STATES = ("SPARK", "REPEAT", "VARY", "BOUNDARY", "COMBINE", "NAME")
NOISE = "NOISE"
TRIAL_KINDS = ("repeat", "vary", "combine")
STATE_OF_KIND = {"repeat": "REPEAT", "vary": "VARY", "combine": "COMBINE"}
MIN_REPEATS = 2
MIN_FAILED_VARIATIONS = 1
SCOPE_WORDS = ("when", "only", "if", "unless", "under", "between", "above", "below", "after",
               "before", "within", "except", "while", "during", "until", "provided")
SCOPE_RE = re.compile(r"\b(" + "|".join(SCOPE_WORDS) + r")\b", re.IGNORECASE)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nonempty(v):
    return isinstance(v, str) and v.strip() != ""


def load(run):
    path = Path(run) / FILENAME
    if not path.is_file():
        return {"sparks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(run, doc):
    (Path(run) / FILENAME).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")


def _find(doc, spark_id):
    for s in doc["sparks"]:
        if s["id"] == spark_id:
            return s
    raise ValueError(f"unknown spark: {spark_id}")


def _known_hypotheses(run):
    path = Path(run) / HYPOTHESES
    if not path.is_file():
        raise ValueError(f"no {HYPOTHESES} in {run}; a spark must name the hypotheses it touches")
    return {h["id"] for h in json.loads(path.read_text(encoding="utf-8"))["hypotheses"]}


def new(run, observation, prediction_before, hypothesis_ids):
    """Open a spark in state SPARK. Raises ValueError; writes nothing on refusal."""
    run = Path(run)
    if not (run / "goal.json").is_file():
        raise ValueError(f"no goal.json in {run}; run goal.py new first")
    if not _nonempty(observation):
        raise ValueError("observation must be a non-empty string")
    if not _nonempty(prediction_before):
        raise ValueError("prediction_before must be a non-empty string")
    if not hypothesis_ids:
        raise ValueError("at least one hypothesis id is required")
    known = _known_hypotheses(run)
    unknown = [h for h in hypothesis_ids if h not in known]
    if unknown:
        raise ValueError(f"unknown hypothesis id: {', '.join(unknown)}")
    doc = load(run)
    spark = {"id": evidence.next_id([s["id"] for s in doc["sparks"]], ID_PREFIX),
             "state": STATES[0], "observation": observation.strip(),
             "hypothesis_ids": list(hypothesis_ids),
             "prediction_before": prediction_before.strip(), "prediction_after": None,
             "progress": False, "trials": [], "opened_at": _now(), "updated_at": _now()}
    doc["sparks"].append(spark)
    save(run, doc)
    return spark


def trial(run, spark_id, kind, ok, detail, condition=None, evidence_id=None):
    """Append one trial. The kind must match the spark's current state. Raises ValueError."""
    if kind not in TRIAL_KINDS:
        raise ValueError(f"kind must be one of {', '.join(TRIAL_KINDS)}")
    if not _nonempty(detail):
        raise ValueError("detail must be a non-empty string")
    if kind == "vary" and not _nonempty(condition):
        raise ValueError("a vary trial must say which one condition changed (--condition)")
    doc = load(run)
    spark = _find(doc, spark_id)
    if spark["state"] != STATE_OF_KIND[kind]:
        raise ValueError(f"{spark_id} is in {spark['state']}; a {kind} trial needs {STATE_OF_KIND[kind]}")
    if evidence_id is not None:
        if evidence_id not in {r["evidence_id"] for r in evidence.read(run)}:
            raise ValueError(f"unknown evidence_id: {evidence_id}")
    record = {"kind": kind, "ok": bool(ok), "detail": detail.strip(),
              "condition": condition.strip() if condition else None,
              "evidence_id": evidence_id, "ts": _now()}
    spark["trials"].append(record)
    spark["updated_at"] = _now()
    save(run, doc)
    return record


def counts(spark):
    c = {"repeat_ok": 0, "repeat_failed": 0, "vary_ok": 0, "vary_failed": 0, "combine": 0}
    for t in spark["trials"]:
        if t["kind"] == "combine":
            c["combine"] += 1
        else:
            c[f"{t['kind']}_{'ok' if t['ok'] else 'failed'}"] += 1
    return c


def narrowed(before, after):
    """v1 string test: `after` keeps `before` and adds a scope word. Nothing else counts."""
    b = before.strip().rstrip(".").lower()
    a = after.strip().rstrip(".").lower()
    if not b or b not in a or a == b:
        return False
    added = a.replace(b, " ", 1)
    return SCOPE_RE.search(added) is not None


def _missing(spark, target):
    """Return the first unmet requirement for `target`, or None."""
    c = counts(spark)
    if target in ("VARY", "BOUNDARY") and c["repeat_ok"] < MIN_REPEATS:
        return f"need {MIN_REPEATS} repeats (have {c['repeat_ok']})"
    if target == "BOUNDARY" and c["vary_failed"] < MIN_FAILED_VARIATIONS:
        return f"need {MIN_FAILED_VARIATIONS} failed variation (have {c['vary_failed']})"
    if target == NOISE and c["repeat_failed"] < 1:
        return "need a failed repeat to call it noise"
    if target == "COMBINE" and spark["prediction_after"] is None:
        return "need prediction_after (write the boundary first)"
    if target == "NAME" and c["combine"] < 1:
        return "need a combine trial"
    return None


def advance(run, spark_id, target, prediction_after=None):
    """Move a spark forward. Raises ValueError; writes nothing on refusal."""
    if target not in STATES and target != NOISE:
        raise ValueError(f"unknown state: {target}")
    doc = load(run)
    spark = _find(doc, spark_id)
    current = spark["state"]
    if current == NOISE:
        raise ValueError(f"{spark_id} is noise; it cannot move")
    if target == NOISE:
        if current != "REPEAT":
            raise ValueError(f"only a spark in REPEAT can be marked noise ({spark_id} is in {current})")
    elif STATES.index(target) <= STATES.index(current):
        raise ValueError(f"{spark_id} is already in {current}; sparks only move forward")
    if prediction_after is not None:
        if target != "BOUNDARY":
            raise ValueError("prediction_after is written only when advancing to BOUNDARY")
        if not _nonempty(prediction_after):
            raise ValueError("prediction_after must be a non-empty string")
    missing = _missing(spark, target)
    if missing:
        raise ValueError(f"cannot advance {spark_id} to {target}: {missing}")
    if prediction_after is not None:
        spark["prediction_after"] = prediction_after.strip()
        spark["progress"] = narrowed(spark["prediction_before"], spark["prediction_after"])
    spark["state"] = target
    spark["updated_at"] = _now()
    save(run, doc)
    return spark


def line(spark):
    c = counts(spark)
    return (f"{spark['id']} {spark['state']} repeat {c['repeat_ok']} ok/{c['repeat_failed']} failed, "
            f"vary {c['vary_ok']} ok/{c['vary_failed']} failed, combine {c['combine']}, "
            f"progress {'yes' if spark['progress'] else 'no'}")


def main(argv):
    p = argparse.ArgumentParser(prog="spark.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--run", required=True)
    n.add_argument("--observation", required=True)
    n.add_argument("--prediction_before", required=True)
    n.add_argument("--hypotheses", required=True, help="comma-separated ids from hypotheses.json")
    t = sub.add_parser("trial")
    t.add_argument("--run", required=True)
    t.add_argument("--spark", required=True)
    t.add_argument("--kind", required=True, choices=TRIAL_KINDS)
    g = t.add_mutually_exclusive_group(required=True)
    g.add_argument("--ok", action="store_true")
    g.add_argument("--failed", action="store_true")
    t.add_argument("--detail", required=True)
    t.add_argument("--condition")
    t.add_argument("--evidence")
    a = sub.add_parser("advance")
    a.add_argument("--run", required=True)
    a.add_argument("--spark", required=True)
    a.add_argument("--to", required=True)
    a.add_argument("--prediction_after")
    s = sub.add_parser("status")
    s.add_argument("--run", required=True)
    s.add_argument("--spark")
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "new":
            ids = [h.strip() for h in args.hypotheses.split(",") if h.strip()]
            spark = new(args.run, args.observation, args.prediction_before, ids)
            print(f"{spark['id']} {spark['state']}")
        elif args.cmd == "trial":
            trial(args.run, args.spark, args.kind, args.ok, args.detail, args.condition, args.evidence)
            print(line(_find(load(args.run), args.spark)))
        elif args.cmd == "advance":
            spark = advance(args.run, args.spark, args.to, args.prediction_after)
            print(line(spark))
        else:
            doc = load(args.run)
            if args.spark:
                print(json.dumps(_find(doc, args.spark), indent=2, ensure_ascii=False))
            else:
                for spark in doc["sparks"]:
                    print(line(spark))
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
