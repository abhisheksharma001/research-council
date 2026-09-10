import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("generation", "reflection", "ranking", "meta-review")
RUNTIME_SCRIPTS = ("budget", "claims", "evidence", "fence", "goal", "harness", "journal",
                   "promote", "rank", "report", "retrieve", "spark", "triage",
                   "validate_manifest", "validate_skill")
TOOLS = tuple(name for name in RUNTIME_SCRIPTS
              if name not in ("harness", "promote", "validate_manifest", "validate_skill"))


def layout():
    bundled = ROOT.name == "runtime" and (ROOT.parent / "SKILL.md").is_file()
    skill = ROOT.parent if bundled else ROOT / "skills" / "research-council"
    return skill, "bundle" if bundled else "checkout"


def resources():
    skill, mode = layout()
    anchor = ROOT.parent if mode == "bundle" else ROOT
    files = [(skill / "SKILL.md", Path("SKILL.md"))]
    files += [(path, Path("references") / path.name) for path in sorted((skill / "references").glob("*.md"))]
    files += [(ROOT / "scripts" / f"{name}.py", Path("runtime/scripts") / f"{name}.py")
              for name in RUNTIME_SCRIPTS]
    files += [(ROOT / "agents" / f"{role}.md", Path("runtime/agents") / f"{role}.md") for role in ROLES]
    files += [(ROOT / "strategies/fire.md", Path("runtime/strategies/fire.md")),
              (ROOT / "docs/spec-v1.md", Path("runtime/docs/spec-v1.md"))]
    for source, _ in files:
        if any(part.is_symlink() for part in (source, *source.parents) if part.is_relative_to(anchor)):
            raise ValueError(f"symlink runtime resource is not allowed: {source}")
        if not source.is_file() or not source.resolve().is_relative_to(anchor):
            raise ValueError(f"missing or outside runtime resource: {source}")
    for name in ("goal", "triage", "budget", "evidence", "council", "rank", "curiosity", "report", "library"):
        if not (skill / "references" / f"{name}.md").is_file():
            raise ValueError(f"missing runtime resource: references/{name}.md")
    return files


def context(workspace):
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")
    workspace = Path(workspace).expanduser()
    if not workspace.is_dir():
        raise ValueError(f"workspace must be an existing directory: {workspace}")
    workspace = workspace.resolve()
    resources()
    skill, mode = layout()
    library = ROOT / "library"
    return {
        "schema_version": 1,
        "mode": mode,
        "council_root": str(ROOT),
        "skill": str(skill / "SKILL.md"),
        "workspace": str(workspace),
        "run_root": str(workspace / "AGI_Research/runs"),
        "library": str(library) if mode == "checkout" and (library / "registry.json").is_file() else None,
        "promotion_available": mode == "checkout" and (library / "registry.json").is_file(),
        "python": sys.executable,
        "tools": list(TOOLS),
        "execution_mode": "evidence-only",
        "unverified_capabilities": ["model availability", "source access", "host-enforced worker permissions",
                                    "provider billing", "sandbox for untrusted code"],
    }


def run_tool(workspace, tool, args):
    if tool not in TOOLS:
        raise ValueError(f"unknown or administrative helper: {tool}")
    info = context(workspace)
    args = args[1:] if args[:1] == ["--"] else args
    return subprocess.run([sys.executable, str(ROOT / "scripts" / f"{tool}.py"), *args],
                          cwd=info["workspace"], check=False).returncode


def export(destination):
    files = resources()
    destination = Path(destination).expanduser().absolute()
    if destination.name != "research-council":
        raise ValueError("destination directory must be named research-council")
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists; nothing overwritten: {destination}")
    if not destination.parent.is_dir():
        raise ValueError(f"destination parent must exist: {destination.parent}")
    destination.mkdir()
    try:
        for source, relative in files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    except OSError:
        shutil.rmtree(destination)
        raise
    return destination


def main(argv):
    parser = argparse.ArgumentParser(prog="harness.py")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("context")
    check.add_argument("--workspace", required=True)
    run = sub.add_parser("run")
    run.add_argument("--workspace", required=True)
    run.add_argument("tool", choices=TOOLS)
    run.add_argument("args", nargs=argparse.REMAINDER)
    package = sub.add_parser("export")
    package.add_argument("--destination", required=True)
    args = parser.parse_args(argv[1:])
    try:
        if args.command == "context":
            print(json.dumps(context(args.workspace), indent=2))
        elif args.command == "export":
            print(export(args.destination))
        else:
            return run_tool(args.workspace, args.tool, args.args)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
