#!/usr/bin/env python3
"""The diff stays inside the task: paths, line cap and verifier edits.

Usage:
  python3 scripts/scope.py check --run <run-dir>

Reads task.json, then in repo_root runs `git diff --numstat <start_commit>` (tracked files)
and `git status --porcelain` (new untracked files). Prints one line per violation:

  outside: <path>                      a changed or new file matching no allowed_paths glob
  over: <n>/<max_diff_lines> lines     added plus removed lines above the task's cap
  verifier-edit: <path>: <reason>      a test file (a `tests` folder, `test_*`, `*_test.*`),
                                       CI config (`.github/`) or a file named in test_command
                                       lost a non-blank non-comment line, or gained a line
                                       with a skip or expected-failure marker; silenced only
                                       by allow_verifier_edits: true in task.json

A comment is decided by the file's own language: `#` in Python, shell and YAML, `//` and `/*` in
the C family, `--` in SQL, `<!--` in HTML and Markdown, and `#` or `//` when the extension is
unknown. So a removed `--flag` line of a shell verifier is a real removed line, and a removed
`-- seed` line of a SQL one is not.

With no violation prints `tier: 1|2|3` and `lines: <n>` (tiers.md holds the table).
Files under AGI_Research/ are the council's own state, never part of the task's diff.

Globs: `*` and `?` stay inside one path segment, `**` crosses segments, `[...]` is a
character class; a pattern must match the whole path relative to repo_root.

Exit 0 clean, 2 on any violation, 1 on bad input (tampered task.json, no git checkout,
unreadable start_commit). Reads only; never edits the working tree; calls no model.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task  # noqa: E402

STATE_PREFIX = "AGI_Research/"
HASH = ("#",)
C_LIKE = ("//", "/*", "*")
DASH = ("--",)
MARKUP = ("<!--",)
COMMENT_STARTS = {
    ".py": HASH, ".sh": HASH, ".bash": HASH, ".zsh": HASH, ".rb": HASH, ".pl": HASH, ".r": HASH,
    ".yml": HASH, ".yaml": HASH, ".toml": HASH, ".cfg": HASH, ".ini": HASH, ".mk": HASH, ".tf": HASH,
    ".c": C_LIKE, ".h": C_LIKE, ".cc": C_LIKE, ".cpp": C_LIKE, ".hpp": C_LIKE, ".java": C_LIKE,
    ".js": C_LIKE, ".jsx": C_LIKE, ".mjs": C_LIKE, ".cjs": C_LIKE, ".ts": C_LIKE, ".tsx": C_LIKE,
    ".go": C_LIKE, ".rs": C_LIKE, ".cs": C_LIKE, ".swift": C_LIKE, ".kt": C_LIKE, ".php": C_LIKE,
    ".scala": C_LIKE, ".css": C_LIKE, ".scss": C_LIKE, ".less": C_LIKE,
    ".sql": DASH, ".lua": DASH, ".hs": DASH,
    ".html": MARKUP, ".xml": MARKUP, ".md": MARKUP, ".vue": MARKUP,
}
COMMENT_NAMES = {"makefile": HASH, "dockerfile": HASH, "justfile": HASH}
FALLBACK_COMMENT_STARTS = ("#", "//")
WEAKENING_MARKERS = ("skip", "xfail", "expectedfailure", "xit(", "xdescribe(", ".only(", "@ignore", "@disabled")
TIERS = ((10, 1), (100, 2))


def translate(pattern):
    """Regex for one allowed_paths glob, anchored to the whole relative path."""
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[" and pattern.find("]", i + 1) != -1:
            j = pattern.find("]", i + 1)
            inner = pattern[i + 1:j]
            out.append("[" + ("^" + inner[1:] if inner.startswith("!") else inner) + "]")
            i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("".join(out) + r"\Z")


def allowed(path, patterns):
    return any(translate(p).match(path) for p in patterns)


def is_verifier(path, test_command):
    parts = PurePosixPath(path).parts
    name = parts[-1]
    return ("tests" in parts[:-1] or name.startswith("test_") or re.search(r"_test\.[^.]+\Z", name) is not None
            or parts[0] == ".github" or path in test_command)


def comment_starts(path):
    """The comment prefixes of the file's own language; a common pair when the name is unknown."""
    posix = PurePosixPath(path)
    suffix = posix.suffix.lower()
    if suffix in COMMENT_STARTS:
        return COMMENT_STARTS[suffix]
    return COMMENT_NAMES.get(posix.name.lower(), FALLBACK_COMMENT_STARTS)


def is_comment(line, path):
    stripped = line.strip()
    return not stripped or stripped.startswith(comment_starts(path))


def verifier_reasons(added, removed, path):
    """Reasons a change to a verifier file weakens it. Comment and blank lines never count."""
    reasons = []
    for line in removed:
        if not is_comment(line, path):
            reasons.append(f"removed line: {line.strip()}")
    for line in added:
        if not is_comment(line, path):
            low = line.lower()
            hits = [m for m in WEAKENING_MARKERS if m in low]
            if hits:
                reasons.append(f"added {hits[0]!r} marker: {line.strip()}")
    return reasons


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError(f"git {args[0]} failed in {root}: {r.stderr.strip()}")
    return r.stdout


def untracked_lines(root, path):
    return (Path(root) / path).read_text(encoding="utf-8", errors="replace").splitlines()


def changed_files(root, start_commit):
    """{path: (added, removed, untracked)} since start_commit, without the council's own state."""
    files = {}
    for entry in git(root, "diff", "--numstat", "-z", "--no-renames", start_commit).split("\0"):
        if entry:
            add, rem, path = entry.split("\t", 2)
            files[path] = (0 if add == "-" else int(add), 0 if rem == "-" else int(rem), False)
    for entry in git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames").split("\0"):
        if entry.startswith("?? "):
            path = entry[3:]
            files[path] = (len(untracked_lines(root, path)), 0, True)
    return {p: v for p, v in files.items() if not p.startswith(STATE_PREFIX)}


def diff_lines(root, start_commit, path):
    """(added, removed) content lines of one tracked file's diff; headers and markers skipped."""
    added, removed = [], []
    in_hunk = False
    for line in git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames",
                    start_commit, "--", path).splitlines():
        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            added.append(line[1:])
        elif in_hunk and line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def check(run):
    """(violations, lines) for the run's task. Raises ValueError on bad input."""
    t = task.load(run)
    root = Path(t["repo_root"])
    if not root.is_dir():
        raise ValueError(f"repo_root is not a directory: {root}")
    if t["start_commit"] == "none":
        raise ValueError("start_commit is none: the scope guard needs a git checkout with at least one commit")
    violations = []
    lines = 0
    for path, (add, rem, untracked) in sorted(changed_files(root, t["start_commit"]).items()):
        lines += add + rem
        if not allowed(path, t["allowed_paths"]):
            violations.append(f"outside: {path}")
        if not t.get("allow_verifier_edits") and is_verifier(path, t["test_command"]):
            added, removed = (untracked_lines(root, path), []) if untracked else diff_lines(root, t["start_commit"], path)
            violations += [f"verifier-edit: {path}: {reason}"
                           for reason in verifier_reasons(added, removed, path)]
    if lines > t["max_diff_lines"]:
        violations.append(f"over: {lines}/{t['max_diff_lines']} lines")
    return violations, lines


def tier(lines):
    for cap, level in TIERS:
        if lines <= cap:
            return level
    return 3


def main(argv):
    p = argparse.ArgumentParser(prog="scope.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        violations, lines = check(args.run)
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if violations:
        print("\n".join(violations))
        return 2
    print(f"tier: {tier(lines)}")
    print(f"lines: {lines}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
