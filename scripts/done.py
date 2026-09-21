#!/usr/bin/env python3
"""The script says done; the model copies the line.

Usage:
  python3 scripts/done.py check   --run <run-dir>
  python3 scripts/done.py resolve --run <run-dir> --finding <id> --fixed
  python3 scripts/done.py resolve --run <run-dir> (--finding <id> | --test <id>) --waived "<user's words>"

`check` runs, in order: the budget meter (an exceeded cap stops here), the scope guard, the
dependency guard and an empty-diff test. Only when all are clean it runs task.test_command
in repo_root through the shell, with the minutes left on the cap as the timeout, and writes
that run down as a `command` evidence record (source_uri the command, locator exit code and
duration, excerpt the last 2000 characters of output, access_scope private) plus an `exec`
journal line. Then it reads every review-<n>.json: a finding with severity "blocking" needs
a resolutions.jsonl line {"finding": <id>, "how": "fixed", "diff_sha": <sha>} or
{"finding": <id>, "how": "waived", "user_words": <text>}; a tier 2 or 3 diff with no review
file is not done. When thinker.json exists, each test's name must appear in the added lines
of the diff or in a line {"test": <id>, "how": "waived", "user_words": <text>}; a tier 2 or
3 diff whose caps allow the Thinker (max_subagents 2 or more) needs thinker.json.

Prints `DONE <sha256>` and exits 0 only when every check passed and the test command exited
0. Otherwise prints `NOT DONE` then one reason per line and exits 2. Exit 1 on bad input
(tampered task.json, no git checkout, a review, thinker or resolutions file that does not
parse, a finding id used by two review files). The sha covers `git diff --binary
<start_commit>` plus the bytes of every untracked file, so a new file is part of what is
certified; a test run that writes into the working tree changes that sha and is not done.

`resolve` appends one resolutions.jsonl line and computes diff_sha itself; the model never
types a sha. The id must exist in a review file or thinker.json. A test is never "fixed":
its name is in the diff, or the user waived it.

Never edits the working tree of repo_root; the only writes are inside the run folder.
"""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import deps  # noqa: E402
import evidence  # noqa: E402
import journal  # noqa: E402
import scope  # noqa: E402
import task  # noqa: E402

REVIEW = re.compile(r"^review-\d+\.json$")
RESOLUTIONS = "resolutions.jsonl"
THINKER = "thinker.json"
SEVERITIES = ("blocking", "advisory")
SHA = re.compile(r"^[0-9a-f]{64}$")


def diff_material(root, start_commit):
    """(patch bytes against start_commit, {untracked path: bytes}), without the council's own state."""
    r = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", "diff", "--binary", "--no-color",
                        "--no-ext-diff", "--no-renames", start_commit, "--", ".", f":(exclude){scope.STATE_PREFIX}"],
                       capture_output=True)
    if r.returncode != 0:
        raise ValueError(f"git diff failed in {root}: {r.stderr.decode('utf-8', 'replace').strip()}")
    untracked = {path: (Path(root) / path).read_bytes()
                 for path, (_, _, new) in sorted(scope.changed_files(root, start_commit).items()) if new}
    return r.stdout, untracked


def diff_sha(patch, untracked):
    h = hashlib.sha256(patch)
    for path, data in untracked.items():
        h.update(f"\n+++ untracked: {path}\n".encode("utf-8"))
        h.update(data)
    return h.hexdigest()


def added_text(patch, untracked):
    """Added lines of the patch, then every untracked file's text."""
    lines = [line[1:] for line in patch.decode("utf-8", "replace").splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    return "\n".join(lines) + "\n" + "\n".join(data.decode("utf-8", "replace") for data in untracked.values())


def run_tests(root, command, timeout):
    """(exit code or "timeout", output text, seconds). The command's process group is killed on timeout."""
    start = time.monotonic()
    proc = subprocess.Popen(command, shell=True, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
        code = "timeout"
    return code, (out or b"").decode("utf-8", "replace"), time.monotonic() - start


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"{path.name} does not parse: {e}")


def findings(run):
    """(review file names, {finding id: severity}); an id in two review files is an error."""
    names, out, seen = [], {}, {}
    for path in sorted(p for p in Path(run).iterdir() if REVIEW.match(p.name)):
        names.append(path.name)
        data = read_json(path)
        items = data.get("findings") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError(f"{path.name}: expected an object with a findings list")
        for i, f in enumerate(items):
            fid, sev = (f.get("id"), f.get("severity")) if isinstance(f, dict) else (None, None)
            if not evidence._nonempty_str(fid) or sev not in SEVERITIES:
                raise ValueError(f"{path.name}: finding {i} needs an id and a severity of blocking or advisory")
            if fid in seen:
                raise ValueError(f"finding id {fid} appears in {seen[fid]} and {path.name}")
            seen[fid] = path.name
            out[fid] = sev
    return names, out


def thinker_tests(run):
    """{test id: declared name} from thinker.json; None when the file is absent."""
    path = Path(run) / THINKER
    if not path.is_file():
        return None
    data = read_json(path)
    items = data.get("tests") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"{THINKER}: expected an object with a tests list")
    out = {}
    for i, t in enumerate(items):
        tid, name = (t.get("id"), t.get("name")) if isinstance(t, dict) else (None, None)
        if not evidence._nonempty_str(tid) or not evidence._nonempty_str(name):
            raise ValueError(f"{THINKER}: test {i} needs an id and a name")
        out[tid] = name
    return out


def _valid_resolution(line):
    if not isinstance(line, dict):
        return False
    key = "finding" if "finding" in line else "test" if "test" in line else None
    if key is None or not evidence._nonempty_str(line[key]):
        return False
    if line.get("how") == "fixed":
        return key == "finding" and isinstance(line.get("diff_sha"), str) and SHA.match(line["diff_sha"]) is not None
    return line.get("how") == "waived" and evidence._nonempty_str(line.get("user_words"))


def resolutions(run):
    """{("finding"|"test", id): line} from resolutions.jsonl; a malformed line is an error."""
    path = Path(run) / RESOLUTIONS
    out = {}
    if not path.is_file():
        return out
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{RESOLUTIONS} line {n} does not parse: {e}")
        if not _valid_resolution(line):
            raise ValueError(f"{RESOLUTIONS} line {n}: expected {{finding, how: fixed, diff_sha}} "
                             "or {finding|test, how: waived, user_words}")
        key = "finding" if "finding" in line else "test"
        out[(key, line[key])] = line
    return out


def check(run, now=None):
    """(sha, []) when done, else (None, reasons). Raises ValueError on bad input."""
    t = task.load(run)
    root = Path(t["repo_root"])
    if not root.is_dir():
        raise ValueError(f"repo_root is not a directory: {root}")
    if t["start_commit"] == "none":
        raise ValueError("start_commit is none: done.py needs a git checkout with at least one commit")
    now = now or datetime.now(timezone.utc)
    st = budget.status(run, now)
    if st["exceeded"]:
        return None, [f"budget: exceeded {k} ({st['spent'][k]}/{st['caps'][k]})" for k in st["exceeded"]]
    violations, lines = scope.check(run)
    _, unresolved = deps.check(run)
    reasons = violations + [f"unresolved dependency: {name}" for name in unresolved]
    patch, untracked = diff_material(root, t["start_commit"])
    if not patch and not untracked:
        reasons.append("diff: empty (nothing changed since start_commit)")
    cap = st["caps"]["minutes"]
    left = cap * 60 - (now - datetime.fromisoformat(t["created_at"])).total_seconds()
    if left <= 0:
        reasons.append(f"tests: not run (minutes cap {cap} reached)")
    if reasons:
        return None, reasons
    before = diff_sha(patch, untracked)
    code, out, secs = run_tests(root, t["test_command"], left)
    evidence.add(run, {"source_type": "command", "source_uri": t["test_command"], "title": "test command",
                       "locator": f"exit {code} after {secs:.1f}s", "excerpt": out[-evidence.EXCERPT_MAX:] or "(no output)",
                       "access_scope": "private"})
    journal.add(run, "exec", 0.0, f"done.py check: test command exit {code} after {secs:.1f}s")
    if code == "timeout":
        reasons.append(f"tests: timed out after {left:.0f}s (minutes cap {cap})")
    elif code != 0:
        reasons.append(f"tests: exit {code}")
    patch, untracked = diff_material(root, t["start_commit"])
    sha = diff_sha(patch, untracked)
    if sha != before:
        reasons.append("tests: the run changed the diff (files written into the working tree)")
    tier = scope.tier(lines)
    names, found = findings(run)
    done = resolutions(run)
    if tier >= 2 and not names:
        reasons.append(f"review: tier {tier} diff has no review-<n>.json")
    reasons += [f"unresolved finding: {fid}" for fid, sev in found.items()
                if sev == "blocking" and ("finding", fid) not in done]
    tests = thinker_tests(run)
    if tests is None:
        if tier >= 2 and st["caps"]["max_subagents"] >= 2:
            reasons.append(f"thinker: no {THINKER} for a tier {tier} diff")
    else:
        added = added_text(patch, untracked)
        reasons += [f"missing test: {tid} {name}" for tid, name in tests.items()
                    if name not in added and ("test", tid) not in done]
    return (None, reasons) if reasons else (sha, [])


def resolve(run, finding=None, test=None, fixed=False, user_words=None):
    """Append one resolutions.jsonl line. Returns it. Raises ValueError."""
    t = task.load(run)
    if (finding is None) == (test is None):
        raise ValueError("give exactly one of --finding or --test")
    if fixed == (user_words is not None):
        raise ValueError("give exactly one of --fixed or --waived")
    if finding is not None:
        if finding not in findings(run)[1]:
            raise ValueError(f"unknown finding: {finding} (not in any review-<n>.json)")
        line = {"finding": finding}
    else:
        if test not in (thinker_tests(run) or {}):
            raise ValueError(f"unknown test: {test} (not in {THINKER})")
        if fixed:
            raise ValueError("a test is proven by its name in the diff, not by a fixed line; use --waived")
        line = {"test": test}
    if fixed:
        line.update(how="fixed", diff_sha=diff_sha(*diff_material(Path(t["repo_root"]), t["start_commit"])))
    else:
        if not evidence._nonempty_str(user_words):
            raise ValueError("--waived needs the user's exact words, not an empty string")
        line.update(how="waived", user_words=user_words)
    with (Path(run) / RESOLUTIONS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def main(argv):
    p = argparse.ArgumentParser(prog="done.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("--run", required=True)
    r.add_argument("--finding")
    r.add_argument("--test")
    r.add_argument("--fixed", action="store_true")
    r.add_argument("--waived", metavar="USER_WORDS")
    args = p.parse_args(argv[1:])
    try:
        if args.cmd == "resolve":
            print(json.dumps(resolve(args.run, args.finding, args.test, args.fixed, args.waived), ensure_ascii=False))
            return 0
        sha, reasons = check(args.run)
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if reasons:
        print("NOT DONE")
        print("\n".join(reasons))
        return 2
    print(f"DONE {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
