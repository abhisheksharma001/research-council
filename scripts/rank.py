#!/usr/bin/env python3
"""Blinded Elo tournament over a run's hypotheses.json.

Usage:
  python3 scripts/rank.py pair   --run <run-dir> --seed <n>
  python3 scripts/rank.py record --run <run-dir> --pair <P-n> --winner A|B|draw --judgment <text>
  python3 scripts/rank.py cycles --run <run-dir>
  python3 scripts/rank.py table  --run <run-dir>
  python3 scripts/rank.py stop   --run <run-dir> --hyp <H-n> --reason <text>

pair    Every pair is judged twice, once in each order, by separate spawns. When a pair
        has its order-1 verdict and order 2 is not issued, pair issues order 2: the same
        pair with A and B swapped. Otherwise it picks two open hypotheses (fewest
        comparisons first, then highest rating; the opponent prefers a pair that has not
        been drawn, then shared opponents, then rating; a pair already issued and not yet
        recorded counts as drawn and is refused) in seed-shuffled order as order 1. The
        pair is written to pairs.jsonl and printed as a blinded JSON object: pair_id,
        order, and sides A and B carrying only statement, predicted_result,
        needed_evidence and stop_condition. No id, rating, parent or status reaches the
        Ranking agent.
record  looks the pair up. The order-1 verdict goes to verdicts.jsonl and changes no
        rating. The order-2 verdict (refused until order 2 is issued) completes the pair:
        both verdicts agree -> that result; they disagree -> draw with `split: true`.
        One line goes to comparisons.jsonl and `elo` and `comparisons` are updated on
        both hypotheses (start 1200, K=16, win 1 / draw 0.5 / loss 0). The winner is read
        case-insensitively and stored as A, B or draw, in order-1 labels.
cycles  prints every non-transitive triple X > Y > Z > X among recorded wins.
table   prints ratings, highest first, with comparison counts and status, then the flip
        rate: how many pairs judged in both orders came back split.
stop    sets one open hypothesis to status `stopped` with `stopped_reason` (the Supervisor
        runs it for each id Meta-review names; no council role may). Ratings untouched;
        `pair` never draws a stopped hypothesis.

Ratings order scheduling only. This script never reads claims, writes no status other
than `stopped`, and has no path to the library or the promote script.

Exit 0 ok, 1 invalid input or refused.
"""
import argparse
import json
import random
import string
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402  (next_id only)

HYPOTHESES = "hypotheses.json"
PAIRS = "pairs.jsonl"
VERDICTS = "verdicts.jsonl"
COMPARISONS = "comparisons.jsonl"
START = 1200.0
K = 16
SCORE = {"A": (1.0, 0.0), "B": (0.0, 1.0), "draw": (0.5, 0.5)}
BLIND_FIELDS = ("statement", "predicted_result", "needed_evidence", "stop_condition")
ELIGIBLE_STATUS = "open"
STOPPED_STATUS = "stopped"


def _jsonl(path):
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load(run):
    """Return the hypotheses.json document with elo/comparisons defaulted on every entry."""
    path = Path(run) / HYPOTHESES
    if not path.is_file():
        raise ValueError(f"no {HYPOTHESES} in {run}; spawn Generation first")
    doc = json.loads(path.read_text(encoding="utf-8"))
    for h in doc.get("hypotheses", []):
        h.setdefault("elo", START)
        h.setdefault("comparisons", 0)
    return doc


def save(run, doc):
    (Path(run) / HYPOTHESES).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")


def _by_id(doc):
    return {h["id"]: h for h in doc["hypotheses"]}


def _opponents(run):
    """id -> set of ids it has been drawn against, issued but unjudged pairs included."""
    run = Path(run)
    opp = {}
    for c in _jsonl(run / PAIRS) + _jsonl(run / COMPARISONS):
        opp.setdefault(c["a"], set()).add(c["b"])
        opp.setdefault(c["b"], set()).add(c["a"])
    return opp


def _outstanding(run):
    """{frozenset({a, b}): pair_id} for every issued pair that has no comparison line yet."""
    run = Path(run)
    recorded = {c["pair_id"] for c in _jsonl(run / COMPARISONS)}
    return {frozenset((p["a"], p["b"])): p["pair_id"]
            for p in _jsonl(run / PAIRS) if p["pair_id"] not in recorded}


def choose(doc, opponents):
    """Return (first, second) hypothesis dicts, or raise ValueError when fewer than two are open."""
    open_ = [h for h in doc["hypotheses"] if h.get("status") == ELIGIBLE_STATUS]
    if len(open_) < 2:
        raise ValueError(f"fewer than two open hypotheses ({len(open_)}); nothing to pair")
    first = min(open_, key=lambda h: (h["comparisons"], -h["elo"], h["id"]))
    seen = opponents.get(first["id"], set())

    def rank(h):
        shared = len(seen & opponents.get(h["id"], set()))
        return (h["id"] in seen, -shared, -h["elo"], h["comparisons"], h["id"])

    second = min((h for h in open_ if h is not first), key=rank)
    return first, second


def _blind(h):
    return {f: h.get(f) for f in BLIND_FIELDS}


def pair(run, seed):
    """Issue order 2 of a half-judged pair, else choose and shuffle a new pair as order 1.

    Persists to pairs.jsonl and returns the blinded object.
    """
    run = Path(run)
    doc = load(run)
    issued = _jsonl(run / PAIRS)
    second = {p["pair_id"] for p in issued if p.get("order") == 2}
    for v in _jsonl(run / VERDICTS):
        if v["pair_id"] not in second:
            first = next(p for p in issued if p["pair_id"] == v["pair_id"])
            rec = {"pair_id": first["pair_id"], "a": first["a"], "b": first["b"], "order": 2,
                   "seed": seed, "issued_at": datetime.now(timezone.utc).isoformat()}
            with (run / PAIRS).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            by_id = _by_id(doc)
            return {"pair_id": rec["pair_id"], "order": 2,
                    "A": _blind(by_id[rec["b"]]), "B": _blind(by_id[rec["a"]])}
    first, second = choose(doc, _opponents(run))
    pending = _outstanding(run).get(frozenset((first["id"], second["id"])))
    if pending:
        raise ValueError(f"pair {pending} is already issued for {first['id']} vs {second['id']} "
                         f"and not recorded; record it or judge it first")
    sides = [first, second]
    random.Random(seed).shuffle(sides)
    rec = {"pair_id": evidence.next_id([p["pair_id"] for p in issued], "P-"),
           "a": sides[0]["id"], "b": sides[1]["id"], "order": 1, "seed": seed,
           "issued_at": datetime.now(timezone.utc).isoformat()}
    with (run / PAIRS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return {"pair_id": rec["pair_id"], "order": 1, "A": _blind(sides[0]), "B": _blind(sides[1])}


def elo_update(ra, rb, sa, sb):
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
    eb = 1.0 - ea
    return ra + K * (sa - ea), rb + K * (sb - eb)


def winner_key(value):
    """The SCORE key `value` names, read case-insensitively: "a" -> "A", "Draw." -> "draw".

    A Ranking reply worth a whole spawn should not be discarded for a capital letter (bug 28).
    The key, not the spelling, is what is stored: every later reader indexes SCORE by it.
    """
    folded = value.strip().strip(string.punctuation).casefold() if isinstance(value, str) else None
    for key in SCORE:
        if key.casefold() == folded:
            return key
    raise ValueError("winner must be A, B or draw")


def record(run, pair_id, winner, judgment):
    """Record one order's verdict. Order 1 is held in verdicts.jsonl and returned with
    `complete: False`; order 2 completes the pair, updates both ratings and returns the
    comparison line. Raises ValueError."""
    run = Path(run)
    winner = winner_key(winner)
    if not isinstance(judgment, str) or not judgment.strip():
        raise ValueError("judgment must be a non-empty string")
    lines = [p for p in _jsonl(run / PAIRS) if p["pair_id"] == pair_id]
    if not lines:
        raise ValueError(f"unknown pair: {pair_id}")
    if any(c["pair_id"] == pair_id for c in _jsonl(run / COMPARISONS)):
        raise ValueError(f"pair already recorded: {pair_id}")
    first = next((v for v in _jsonl(run / VERDICTS) if v["pair_id"] == pair_id), None)
    a_id, b_id = lines[0]["a"], lines[0]["b"]
    now = datetime.now(timezone.utc).isoformat()
    if first is None:
        verdict = {"pair_id": pair_id, "order": 1,
                   "winner_id": {"A": a_id, "B": b_id, "draw": None}[winner],
                   "judgment": judgment, "ts": now}
        with (run / VERDICTS).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(verdict, ensure_ascii=False) + "\n")
        return {**verdict, "complete": False}
    if not any(p.get("order") == 2 for p in lines):
        raise ValueError(f"order 2 of {pair_id} is not issued; run pair to get it judged in the swapped order")
    second_id = {"A": b_id, "B": a_id, "draw": None}[winner]
    split = second_id != first["winner_id"]
    winner = "draw" if split or second_id is None else ("A" if second_id == a_id else "B")
    doc = load(run)
    by_id = _by_id(doc)
    a, b = by_id[a_id], by_id[b_id]
    before = (a["elo"], b["elo"])
    sa, sb = SCORE[winner]
    a["elo"], b["elo"] = elo_update(a["elo"], b["elo"], sa, sb)
    a["comparisons"] += 1
    b["comparisons"] += 1
    line = {"pair_id": pair_id, "a": a["id"], "b": b["id"], "winner": winner,
            "winner_id": {"A": a["id"], "B": b["id"], "draw": None}[winner],
            "split": split, "verdicts": [first["winner_id"], second_id],
            "judgment": f"order 1: {first['judgment']} | order 2: {judgment}",
            "elo_before": list(before), "elo_after": [a["elo"], b["elo"]], "ts": now}
    save(run, doc)
    with (run / COMPARISONS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def stop(run, hyp_id, reason):
    """Mark one open hypothesis stopped with a reason. Writes nothing on refusal. Raises ValueError."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string (the objection id)")
    doc = load(run)
    h = _by_id(doc).get(hyp_id)
    if h is None:
        raise ValueError(f"unknown hypothesis: {hyp_id}")
    if h.get("status") != ELIGIBLE_STATUS:
        raise ValueError(f"{hyp_id} is {h.get('status')}, not open; only an open hypothesis can be stopped")
    h["status"] = STOPPED_STATUS
    h["stopped_reason"] = reason.strip()
    save(run, doc)
    return h


def cycles(run):
    """Return sorted list of (x, y, z) with x beat y, y beat z, z beat x. Draws are ignored."""
    beats = {}
    for c in _jsonl(Path(run) / COMPARISONS):
        if c["winner_id"] is None:
            continue
        loser = c["b"] if c["winner_id"] == c["a"] else c["a"]
        beats.setdefault(c["winner_id"], set()).add(loser)
    found = set()
    for x, ys in beats.items():
        for y in ys:
            for z in beats.get(y, ()):
                if x in beats.get(z, ()):
                    start = min(x, y, z)
                    tri = (x, y, z)
                    while tri[0] != start:
                        tri = tri[1:] + tri[:1]
                    found.add(tri)
    return sorted(found)


def table(doc):
    rows = sorted(doc["hypotheses"], key=lambda h: (-h["elo"], h["id"]))
    out = [f"{'id':<6} {'elo':>6} {'cmp':>4} {'status':<8} statement"]
    for h in rows:
        out.append(f"{h['id']:<6} {round(h['elo']):>6} {h['comparisons']:>4} "
                   f"{h.get('status', ''):<8} {h.get('statement', '')[:70]}")
    return "\n".join(out)


def flip_rate(run):
    """One line: how many pairs judged in both orders came back split."""
    both = [c for c in _jsonl(Path(run) / COMPARISONS) if "split" in c]
    if not both:
        return "flip rate: no pair judged in both orders yet"
    n = sum(c["split"] for c in both)
    return f"flip rate: {n} of {len(both)} pairs split ({round(100 * n / len(both))}%)"


def main(argv):
    p = argparse.ArgumentParser(prog="rank.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("pair")
    s.add_argument("--run", required=True)
    s.add_argument("--seed", type=int, required=True)
    s = sub.add_parser("record")
    s.add_argument("--run", required=True)
    s.add_argument("--pair", required=True)
    s.add_argument("--winner", required=True, type=winner_key, choices=sorted(SCORE))
    s.add_argument("--judgment", required=True)
    for name in ("cycles", "table"):
        sub.add_parser(name).add_argument("--run", required=True)
    s = sub.add_parser("stop")
    s.add_argument("--run", required=True)
    s.add_argument("--hyp", required=True)
    s.add_argument("--reason", required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "pair":
            print(json.dumps(pair(args.run, args.seed), ensure_ascii=False))
        elif args.cmd == "record":
            line = record(args.run, args.pair, args.winner, args.judgment)
            if not line.get("complete", True):
                print(f"{line['pair_id']} order 1 recorded; run pair for order 2")
            else:
                ra, rb = line["elo_after"]
                print(f"{line['pair_id']} {line['winner']}{' (split)' if line['split'] else ''}: "
                      f"{line['a']} {round(ra)}, {line['b']} {round(rb)}")
        elif args.cmd == "stop":
            h = stop(args.run, args.hyp, args.reason)
            print(f"{h['id']} {h['status']}: {h['stopped_reason']}")
        elif args.cmd == "cycles":
            found = cycles(args.run)
            for x, y, z in found:
                print(f"{x} > {y} > {z} > {x}")
            print(f"{len(found)} cycle(s)")
        else:
            print(table(load(args.run)))
            print(flip_rate(args.run))
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
