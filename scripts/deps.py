#!/usr/bin/env python3
"""No new dependency without a record that the package exists.

Usage:
  python3 scripts/deps.py check --run <run-dir>

Reads task.json, then collects the names the diff since start_commit introduces:

  Python   `import x` and `from x import` lines added to *.py files (top-level name;
           relative imports skipped)
  pypi     names in requirements*.txt, and in pyproject.toml dependency arrays
           ([project] dependencies and optional-dependencies, [dependency-groups],
           [build-system] requires, [tool.poetry] dependencies and groups),
           that the file holds now and did not hold at start_commit
  npm      names under dependencies or devDependencies in package.json, same rule

A name is resolved when: it is in sys.stdlib_module_names; a module or folder with that
name exists in the repository; importlib.util.find_spec finds it in this interpreter (run
the script with the interpreter the test command uses); a manifest or lock file at
start_commit names it (requirements*.txt, pyproject.toml, package.json, poetry.lock,
uv.lock, pdm.lock, Pipfile.lock, package-lock.json, yarn.lock, pnpm-lock.yaml); or
evidence.jsonl in the run holds a `web` record whose source_uri is the registry page of
that exact name: https://pypi.org/project/<name>/ for Python, https://www.npmjs.com/package/<name>
for npm. Python names compare PEP 503 style (case and -_. folded), so typing_extensions
matches typing-extensions.

Exit 0 prints `new: <n>` then one `resolved: <name> (<how>)` per name. Exit 2 prints one
`unresolved: <name>` per name and nothing else. Exit 1 on bad input (tampered task.json,
no git checkout, a manifest that does not parse).

Offline: fetches nothing, installs nothing, edits nothing. The Supervisor fetches the
registry page and records it with evidence.py (references/deps.md).
"""
import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence  # noqa: E402
import scope  # noqa: E402
import task  # noqa: E402

REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
LOCK_AT = re.compile(r"""^\s*["']?/?(@?[A-Za-z0-9][\w.\-]*(?:/[A-Za-z0-9][\w.\-]*)?)@""", re.M)
REGISTRY = {
    "pypi": re.compile(r"^https?://(?:www\.)?pypi\.org/project/([^/?#]+)/?$"),
    "npm": re.compile(r"^https?://(?:www\.)?npmjs\.com/package/((?:@[^/?#]+/)?[^/?#]+)/?$"),
}
NPM_LOCKS = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
PYPI_LOCKS = ("poetry.lock", "uv.lock", "pdm.lock", "Pipfile.lock")


def norm(eco, name):
    return re.sub(r"[-_.]+", "-", name).lower() if eco == "pypi" else name.lower()


def python_imports(lines):
    """Top-level module names from added `import` / `from ... import` lines."""
    names = set()
    for line in lines:
        s = line.strip()
        if s.startswith("import "):
            heads = [part.split()[0] for part in s[7:].split(",") if part.split()]
        elif s.startswith("from ") and " import" in s:
            heads = [s[5:].split()[0]]
        else:
            continue
        for head in heads:
            top = head.split(".")[0]
            if top.isidentifier():
                names.add(top)
    return names


def requirements_names(text):
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-") or ("://" in line and " @ " not in line):
            continue
        m = REQ_NAME.match(line)
        if m:
            names.add(m.group(1))
    return names


def pyproject_names(text):
    data = tomllib.loads(text)
    project = data.get("project", {})
    specs = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        specs += group
    for group in data.get("dependency-groups", {}).values():
        specs += [s for s in group if isinstance(s, str)]
    specs += data.get("build-system", {}).get("requires", [])
    poetry = data.get("tool", {}).get("poetry", {})
    names = {k for k in poetry.get("dependencies", {}) if k != "python"}
    for group in poetry.get("group", {}).values():
        names |= set(group.get("dependencies", {}))
    for spec in specs:
        m = REQ_NAME.match(spec)
        if m:
            names.add(m.group(1))
    return names


def package_names(text):
    data = json.loads(text)
    names = set()
    for key in ("dependencies", "devDependencies"):
        names |= set(data.get(key) or {})
    return names


def lock_names(name, text):
    if name in ("Pipfile.lock", "package-lock.json"):
        data = json.loads(text)
        names = set()
        for key in ("dependencies", "default", "develop"):
            names |= set(data.get(key) or {})
        return names | {p.rsplit("node_modules/", 1)[-1] for p in (data.get("packages") or {}) if p}
    if name in ("yarn.lock", "pnpm-lock.yaml"):
        return set(LOCK_AT.findall(text))
    return {p["name"] for p in tomllib.loads(text).get("package", []) if "name" in p}


MANIFESTS = {"requirements": ("pypi", requirements_names), "pyproject": ("pypi", pyproject_names),
             "package": ("npm", package_names)}


def kind(path):
    name = PurePosixPath(path).name
    if name.endswith(".py"):
        return "py"
    if name == "pyproject.toml":
        return "pyproject"
    if name == "package.json":
        return "package"
    if name.startswith("requirements") and name.endswith(".txt"):
        return "requirements"
    if name in NPM_LOCKS or name in PYPI_LOCKS:
        return "lock"
    return None


def names_in(parse, text, path):
    if not text.strip():
        return set()
    try:
        return parse(text)
    except (ValueError, TypeError, AttributeError) as e:
        raise ValueError(f"{path} does not parse: {e}") from e


def show(root, commit, path):
    """The file's text at commit, or "" when it did not exist there."""
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"],
                       capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def new_names(root, start_commit, changed):
    """{(eco, name): first path} the diff introduces."""
    new = {}
    for path, (_, _, untracked) in sorted(changed.items()):
        k = kind(path)
        if k == "py":
            added = scope.untracked_lines(root, path) if untracked else scope.diff_lines(root, start_commit, path)[0]
            eco, names = "pypi", python_imports(added)
        elif k in MANIFESTS:
            eco, parse = MANIFESTS[k]
            now = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).is_file() else ""
            names = names_in(parse, now, path) - names_in(parse, show(root, start_commit, path), path)
        else:
            continue
        for name in names:
            new.setdefault((eco, name), path)
    return new


def context(root, start_commit, run, changed):
    """What the repository at start_commit and the run's evidence already know."""
    tracked = [p for p in scope.git(root, "ls-tree", "-r", "--name-only", "-z", start_commit).split("\0") if p]
    local = set()
    for p in tracked + [p for p, (_, _, untracked) in changed.items() if untracked]:
        local |= {seg[:-3] if seg.endswith(".py") else seg for seg in PurePosixPath(p).parts}
    known = {"pypi": {}, "npm": {}}
    for p in tracked:
        k = kind(p)
        if k in MANIFESTS:
            eco, parse = MANIFESTS[k]
            names = names_in(parse, show(root, start_commit, p), p)
        elif k == "lock":
            name = PurePosixPath(p).name
            eco = "npm" if name in NPM_LOCKS else "pypi"
            names = names_in(lambda text: lock_names(name, text), show(root, start_commit, p), p)
        else:
            continue
        for n in names:
            known[eco].setdefault(norm(eco, n), p)
    records = {"pypi": {}, "npm": {}}
    for r in evidence.read(run):
        if r.get("source_type") != "web":
            continue
        for eco, pattern in REGISTRY.items():
            m = pattern.match(unquote(str(r.get("source_uri", "")).strip()))
            if m:
                records[eco].setdefault(norm(eco, m.group(1)), r.get("evidence_id"))
    return {"local": local, "known": known, "records": records}


def resolve(eco, name, ctx):
    """How the name is known, or None."""
    if eco == "pypi":
        if name in sys.stdlib_module_names:
            return "stdlib"
        if name in ctx["local"]:
            return "in the repository"
        try:
            if importlib.util.find_spec(name) is not None:
                return "installed"
        except (ImportError, ValueError, AttributeError):
            pass
    n = norm(eco, name)
    if n in ctx["known"][eco]:
        return f"in {ctx['known'][eco][n]} at start_commit"
    if n in ctx["records"][eco]:
        return f"evidence {ctx['records'][eco][n]}"
    return None


def check(run):
    """(resolved [(name, how)], unresolved [name]) for the run's task. Raises ValueError."""
    t = task.load(run)
    root = Path(t["repo_root"])
    if not root.is_dir():
        raise ValueError(f"repo_root is not a directory: {root}")
    if t["start_commit"] == "none":
        raise ValueError("start_commit is none: the dependency guard needs a git checkout with at least one commit")
    changed = scope.changed_files(root, t["start_commit"])
    ctx = context(root, t["start_commit"], run, changed)
    resolved, unresolved = [], []
    for (eco, name), _ in sorted(new_names(root, t["start_commit"], changed).items(), key=lambda kv: kv[0][::-1]):
        how = resolve(eco, name, ctx)
        if how:
            resolved.append((name, how))
        elif name not in unresolved:
            unresolved.append(name)
    return resolved, unresolved


def main(argv):
    p = argparse.ArgumentParser(prog="deps.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    args = p.parse_args(argv[1:])
    try:
        resolved, unresolved = check(args.run)
    except (ValueError, OSError, KeyError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if unresolved:
        print("\n".join(f"unresolved: {name}" for name in unresolved))
        return 2
    print(f"new: {len(resolved)}")
    for name, how in resolved:
        print(f"resolved: {name} ({how})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
