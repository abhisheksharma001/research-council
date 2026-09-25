#!/usr/bin/env python3
"""Paired evals: the research-council skill against a plain agent at the same budget.

Usage:
  python3 scripts/evals.py validate [--complete]
  python3 scripts/evals.py start   --session <name> --usd <cap> --minutes <cap> --runs <n>
  python3 scripts/evals.py next    --session <name>
  python3 scripts/evals.py record  --session <name> --task T-01 --arm council|plain --run <n> \
      --answer <file> --cost_usd <float|null> --minutes <float>
  python3 scripts/evals.py summary --session <name>

A task is evals/tasks/<id>.json: a request with a known answer from a past run, and a rubric of
binary items, each a case-insensitive regular expression the final answer must (`match`) or must
not (`must_not_match`) contain. `files` are written into a fresh workspace for every run, so a
planted false source (a `trap` task) or late contradicting evidence (a `mind_change` task) is the
same for both arms. Scoring is done here, in code; no model grades an answer.

`start` freezes the task files (sha256 each) and the plan: every task, both arms, `--runs`
times, the arm that goes first alternating by task and run so neither arm always runs first.
The two caps are the user's numbers for the whole session; nothing here defaults or raises them.
`next` prints the next planned run, its workspace, and its share of what is left: remaining
dollars and minutes divided by remaining runs, the same share for both arms of a pair. It exits
2 once a cap is reached (minutes are wall clock since `start`) and prints `done` when the plan
is finished. `record` scores one answer and must match the next planned run; it is accepted even
over a cap, because a run that happened is never left unrecorded. `summary` prints per-arm
scores, per-task pairs and spend, and says how much of the plan is missing.

Nothing here spawns an agent or calls a model; the host runs both arms.
Exit 0 ok, 1 bad input or refused, 2 cap reached.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "evals" / "tasks"
SESSIONS = ROOT / "evals" / "sessions"
KINDS = ("golden", "trap", "mind_change")
ARMS = ("council", "plain")
COMPLETE = {"total": 20, "trap": 2, "mind_change": 1}
TASK_FIELDS = ("id", "kind", "request", "known_answer", "source", "rubric")
OPTIONAL_TASK_FIELDS = ("files", "decoy_answer")
TASK_ID = re.compile(r"T-\d{2,}")


def _nonempty(v):
    return isinstance(v, str) and v.strip() != ""


def validate_task(body, stem):
    """Error strings for one task, empty when valid."""
    if not isinstance(body, dict):
        return [f"{stem}: task must be a JSON object"]
    errors = [f"{stem}: unknown field: {k}" for k in body if k not in TASK_FIELDS + OPTIONAL_TASK_FIELDS]
    errors += [f"{stem}: missing field: {k}" for k in TASK_FIELDS if k not in body]
    if errors:
        return errors
    if body["id"] != stem or not TASK_ID.fullmatch(stem):
        errors.append(f"{stem}: id must be T-<nn> and match the file name")
    if body["kind"] not in KINDS:
        errors.append(f"{stem}: kind must be one of {', '.join(KINDS)}")
    for key in ("request", "known_answer", "source", "decoy_answer"):
        if key in body and not _nonempty(body[key]):
            errors.append(f"{stem}: {key} must be a non-empty string")
    files = body.get("files", {})
    if not isinstance(files, dict) or not all(
            _nonempty(k) and isinstance(v, str) and not Path(k).is_absolute() and ".." not in Path(k).parts
            for k, v in files.items()):
        errors.append(f"{stem}: files must map relative paths inside the workspace to text")
    rubric = body["rubric"]
    if not isinstance(rubric, list) or not rubric:
        return errors + [f"{stem}: rubric must be a non-empty list"]
    ids = []
    for item in rubric:
        keys = set(item) if isinstance(item, dict) else set()
        tests = keys & {"match", "must_not_match"}
        if keys - {"id", "text", "match", "must_not_match"} or len(tests) != 1 \
                or not _nonempty(item.get("id")) or not _nonempty(item.get("text")):
            errors.append(f"{stem}: each rubric item has id, text and exactly one of "
                          f"match or must_not_match")
            continue
        ids.append(item["id"])
        try:
            re.compile(item[tests.pop()])
        except (re.error, TypeError):
            errors.append(f"{stem}: rubric {item['id']} is not a valid regular expression")
    if len(set(ids)) != len(ids):
        errors.append(f"{stem}: rubric ids repeat")
    return errors


def load_tasks(folder=None):
    """{id: task} for every evals/tasks/*.json. Raises ValueError listing every problem."""
    folder = Path(folder or TASKS)
    tasks, errors = {}, []
    for path in sorted(folder.glob("*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            errors.append(f"{path.stem}: not JSON: {error}")
            continue
        found = validate_task(body, path.stem)
        errors += found
        if not found:
            tasks[path.stem] = body
    if errors:
        raise ValueError("\n".join(errors))
    return tasks


def counts(tasks):
    out = {"total": len(tasks)}
    for kind in KINDS:
        out[kind] = sum(1 for t in tasks.values() if t["kind"] == kind)
    return out


def score(task, answer):
    """{rubric id: passed} for one answer text."""
    out = {}
    for item in task["rubric"]:
        if "match" in item:
            out[item["id"]] = re.search(item["match"], answer, re.IGNORECASE) is not None
        else:
            out[item["id"]] = re.search(item["must_not_match"], answer, re.IGNORECASE) is None
    return out


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _session_dir(name, sessions=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name or ""):
        raise ValueError("session name: letters, digits, - and _ only")
    return Path(sessions or SESSIONS) / name


def plan(task_ids, runs):
    """[(task, arm, run)] with both arms of a pair adjacent and the first arm alternating."""
    out = []
    for run in range(1, runs + 1):
        for index, tid in enumerate(sorted(task_ids)):
            arms = ARMS if (index + run) % 2 == 0 else ARMS[::-1]
            out += [(tid, arm, run) for arm in arms]
    return out


def start(name, usd, minutes, runs, tasks_dir=None, sessions=None, now=None):
    folder = _session_dir(name, sessions)
    if folder.exists():
        raise ValueError(f"session {name} already exists; a session is started once")
    for label, value in (("usd", usd), ("minutes", minutes)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"--{label} must be a number above 0, set by the user")
    if type(runs) is not int or runs < 1:
        raise ValueError("--runs must be a whole number of at least 1")
    tasks_dir = Path(tasks_dir or TASKS)
    tasks = load_tasks(tasks_dir)
    if not tasks:
        raise ValueError(f"no tasks in {tasks_dir}")
    session = {"started_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
               "caps": {"usd": usd, "minutes": minutes, "set_by": "user"}, "runs": runs,
               "tasks_dir": str(tasks_dir),
               "tasks": {tid: _digest(tasks_dir / f"{tid}.json") for tid in sorted(tasks)},
               "plan": [list(entry) for entry in plan(tasks, runs)]}
    folder.mkdir(parents=True)
    (folder / "session.json").write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return session


def _load(name, sessions=None):
    folder = _session_dir(name, sessions)
    try:
        session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
    except OSError:
        raise ValueError(f"no session {name}; run start first") from None
    path = folder / "results.jsonl"
    results = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if path.is_file() else []
    return folder, session, results


def spent(session, results, now=None):
    now = now or datetime.now(timezone.utc)
    usd = sum(r["cost_usd"] for r in results if r["cost_usd"] is not None)
    minutes = (now - datetime.fromisoformat(session["started_at"])).total_seconds() / 60
    return {"usd": usd, "minutes": minutes,
            "unmetered": sum(1 for r in results if r["cost_usd"] is None)}


def next_run(name, sessions=None, now=None):
    """(status, info): status is 'done', 'cap' or 'run'. Writes the run's workspace for 'run'."""
    folder, session, results = _load(name, sessions)
    left = session["plan"][len(results):]
    if not left:
        return "done", {}
    s = spent(session, results, now)
    caps = session["caps"]
    over = [k for k in ("usd", "minutes") if s[k] >= caps[k]]
    if over:
        return "cap", {"over": over, "spent": s}
    tid, arm, run = left[0]
    task = json.loads((Path(session["tasks_dir"]) / f"{tid}.json").read_text(encoding="utf-8"))
    work = folder / "work" / f"{tid}-{arm}-{run}"
    work.mkdir(parents=True, exist_ok=True)
    for rel, text in task.get("files", {}).items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text, encoding="utf-8")
    share = {"usd": (caps["usd"] - s["usd"]) / len(left), "minutes": (caps["minutes"] - s["minutes"]) / len(left)}
    return "run", {"task": tid, "arm": arm, "run": run, "workspace": str(work),
                   "request": task["request"], "share": share, "left": len(left)}


def record(name, tid, arm, run, answer_path, cost_usd, minutes, sessions=None):
    folder, session, results = _load(name, sessions)
    left = session["plan"][len(results):]
    if not left:
        raise ValueError("the plan is finished; nothing is waiting to be recorded")
    if [tid, arm, run] != left[0]:
        raise ValueError(f"next planned run is {left[0][0]} {left[0][1]} run {left[0][2]}, "
                         f"not {tid} {arm} run {run}")
    task_path = Path(session["tasks_dir"]) / f"{tid}.json"
    if _digest(task_path) != session["tasks"][tid]:
        raise ValueError(f"{tid} changed since start; a frozen task cannot be scored")
    if cost_usd is not None and (isinstance(cost_usd, bool) or not isinstance(cost_usd, (int, float))
                                 or cost_usd < 0):
        raise ValueError("--cost_usd must be a number from 0, or null when unmetered")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes < 0:
        raise ValueError("--minutes must be a number from 0")
    answer = Path(answer_path).read_text(encoding="utf-8")
    if not answer.strip():
        raise ValueError("the answer file is empty")
    passed = score(json.loads(task_path.read_text(encoding="utf-8")), answer)
    line = {"task": tid, "arm": arm, "run": run, "cost_usd": cost_usd, "minutes": minutes,
            "passed": passed, "score": sum(passed.values()) / len(passed),
            "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    answers = folder / "answers"
    answers.mkdir(exist_ok=True)
    (answers / f"{tid}-{arm}-{run}.md").write_text(answer, encoding="utf-8")
    with (folder / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")
    return line


def summary(name, sessions=None, now=None):
    """Lines of text. Only complete pairs (both arms of one task and run) are compared."""
    folder, session, results = _load(name, sessions)
    s = spent(session, results, now)
    caps = session["caps"]
    out = [f"runs: {len(results)} of {len(session['plan'])} planned"]
    for arm in ARMS:
        mine = [r for r in results if r["arm"] == arm]
        if mine:
            mean = sum(r["score"] for r in mine) / len(mine)
            full = sum(1 for r in mine if r["score"] == 1)
            out.append(f"{arm}: {len(mine)} runs, mean rubric {mean:.2f}, fully passed {full}")
        else:
            out.append(f"{arm}: no runs")
    pairs = {}
    for r in results:
        pairs.setdefault((r["task"], r["run"]), {})[r["arm"]] = r["score"]
    by_task = {}
    for (tid, _), arms in pairs.items():
        if len(arms) == 2:
            by_task.setdefault(tid, []).append(arms["council"] - arms["plain"])
    wins = sum(1 for d in by_task.values() if sum(d) > 0)
    losses = sum(1 for d in by_task.values() if sum(d) < 0)
    ties = len(by_task) - wins - losses
    out.append(f"paired tasks: {len(by_task)}; council better {wins}, plain better {losses}, equal {ties}")
    out.append(f"spent: ${s['usd']:.2f}/${caps['usd']:g}, {s['minutes']:.0f}/{caps['minutes']:g} min "
               f"(unmetered: {s['unmetered']})")
    if len(results) < len(session["plan"]):
        out.append("incomplete: a partial plan says nothing about the tasks it did not reach")
    return out


def _cost(value):
    return None if value == "null" else float(value)


def main(argv):
    p = argparse.ArgumentParser(prog="evals.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("--complete", action="store_true")
    s = sub.add_parser("start")
    s.add_argument("--session", required=True)
    s.add_argument("--usd", type=float, required=True)
    s.add_argument("--minutes", type=float, required=True)
    s.add_argument("--runs", type=int, required=True)
    for cmd in ("next", "summary"):
        sub.add_parser(cmd).add_argument("--session", required=True)
    r = sub.add_parser("record")
    r.add_argument("--session", required=True)
    r.add_argument("--task", required=True)
    r.add_argument("--arm", required=True, choices=ARMS)
    r.add_argument("--run", type=int, required=True)
    r.add_argument("--answer", required=True)
    r.add_argument("--cost_usd", type=_cost, required=True)
    r.add_argument("--minutes", type=float, required=True)
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "validate":
            found = counts(load_tasks())
            print(", ".join(f"{k} {v}" for k, v in found.items()))
            short = [k for k, v in COMPLETE.items() if found[k] < v]
            if args.complete and short:
                print("incomplete: need " + ", ".join(f"{k} {COMPLETE[k]}" for k in short), file=sys.stderr)
                return 1
        elif args.cmd == "start":
            session = start(args.session, args.usd, args.minutes, args.runs)
            print(f"session {args.session}: {len(session['plan'])} runs planned, "
                  f"caps ${args.usd:g} and {args.minutes:g} min")
        elif args.cmd == "next":
            status, info = next_run(args.session)
            if status == "done":
                print("done")
            elif status == "cap":
                print(f"cap reached: {', '.join(info['over'])}; stop and run summary")
                return 2
            else:
                print(json.dumps(info, ensure_ascii=False))
        elif args.cmd == "record":
            line = record(args.session, args.task, args.arm, args.run, args.answer,
                          args.cost_usd, args.minutes)
            print(f"{line['task']} {line['arm']} run {line['run']}: "
                  f"{sum(line['passed'].values())}/{len(line['passed'])} rubric items")
        else:
            print("\n".join(summary(args.session)))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
