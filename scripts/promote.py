#!/usr/bin/env python3
"""Promote a candidate skill into the library, only after every task contract passes.

Usage: python3 scripts/promote.py --candidate <skill-dir> [--library <dir>]

The candidate is a skill directory: SKILL.md, references/manifest.json, references/claims.jsonl,
references/evidence.jsonl, plus whatever scripts and fixtures its contracts need.

Gate, in order, nothing written until all of it passes:
  1. manifest matches library/schema/manifest.schema.json (scripts/validate_manifest.py)
  2. SKILL.md passes scripts/validate_skill.py and name matches the directory
  3. integrity.files hashes match the shipped files; refs resolve to shipped claim/evidence ids;
     dependencies are registered and active; skill_id@version not registered yet
  4. every task contract of every active library version, then every candidate contract,
     each run as a command in its own unit directory: fixture hash, exit code, stdout substring

On success: copy into library/units/<skill_id>/<version>/<name>/, write references/validation.json,
append one receipt line, replace registry.json atomically (temp file then rename).
On any failure: print the failing contract(s), exit 1, registry.json byte-identical.

Only the Supervisor runs this. No subagent has Bash, so none can (see tests/test_agents.py).
Standard library only.
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_manifest  # noqa: E402
import validate_skill  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library"
REGISTRY = "registry.json"
RECEIPTS = "receipts.jsonl"
UNITS = "units"
MANIFEST = "references/manifest.json"
VALIDATION = "references/validation.json"
CLAIMS = "references/claims.jsonl"
EVIDENCE = "references/evidence.jsonl"
DEFAULT_TIMEOUT = 60
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def package_sha256(unit_dir):
    """Hash of every file under the unit (sorted path + content), except validation.json."""
    unit_dir = Path(unit_dir)
    h = hashlib.sha256()
    for path in sorted(p for p in unit_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(unit_dir).as_posix()
        if rel == VALIDATION or "__pycache__" in path.parts:
            continue
        h.update(rel.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


def load_registry(library):
    path = Path(library) / REGISTRY
    if not path.is_file():
        raise ValueError(f"no {REGISTRY} in {library}; the library is not initialised")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc.get("entries"), list):
        raise ValueError(f"{path}: 'entries' must be a list")
    return doc


def read_manifest(unit_dir):
    path = Path(unit_dir) / MANIFEST
    if not path.is_file():
        raise ValueError(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"{path}: not valid JSON ({e})") from e


def _ids_in(path, key):
    if not Path(path).is_file():
        return set()
    out = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.add(json.loads(line).get(key))
    return out


def unit_dir_for(library, manifest):
    return Path(library) / UNITS / manifest["skill_id"] / manifest["version"] / manifest["name"]


def check_candidate(candidate, manifest, registry, library):
    """Every static rule. Returns a list of error strings; empty means the contracts may run."""
    candidate = Path(candidate)
    errors = validate_manifest.validate(manifest)
    if errors:
        return [f"manifest: {e}" for e in errors]
    errors = [f"skill: {e}" for e in validate_skill.validate(candidate)]
    if manifest["name"] != candidate.name:
        errors.append(f"manifest: name {manifest['name']!r} must match directory {candidate.name!r}")
    if (candidate / VALIDATION).exists():
        errors.append(f"candidate must not ship {VALIDATION}; the gate writes it")

    for rel, digest in manifest["integrity"]["files"].items():
        path = candidate / rel
        if not path.is_file():
            errors.append(f"integrity: {rel} is listed but not shipped")
        elif sha256_file(path) != digest:
            errors.append(f"integrity: {rel} does not match its recorded sha256")

    known = _ids_in(candidate / CLAIMS, "claim_id") | _ids_in(candidate / EVIDENCE, "evidence_id")
    for ref in manifest["refs"]:
        if ref not in known:
            errors.append(f"refs: {ref} is not in the shipped claims.jsonl or evidence.jsonl")

    for i, contract in enumerate(manifest["task_contracts"]):
        if "fixture" in contract and not (candidate / contract["fixture"]).is_file():
            errors.append(f"task_contracts[{i}]: fixture {contract['fixture']} is not shipped")

    active = {(e["skill_id"], e["version"]) for e in registry["entries"] if e.get("active")}
    for dep in manifest["dependencies"]:
        if (dep["skill_id"], dep["version"]) not in active:
            errors.append(f"dependencies: {dep['skill_id']}@{dep['version']} is not an active library version")

    key = (manifest["skill_id"], manifest["version"])
    if any((e["skill_id"], e["version"]) == key for e in registry["entries"]):
        errors.append(f"registry: {key[0]}@{key[1]} is already registered; versions are immutable, bump it")
    if unit_dir_for(library, manifest).exists():
        errors.append(f"library: {unit_dir_for(library, manifest)} already exists")
    return errors


def run_contract(unit_dir, contract):
    """Run one contract in its unit directory. Returns (ok, detail)."""
    unit_dir = Path(unit_dir)
    if "fixture" in contract:
        path = unit_dir / contract["fixture"]
        if not path.is_file():
            return False, f"fixture {contract['fixture']} missing"
        if sha256_file(path) != contract["fixture_hash"]:
            return False, f"fixture {contract['fixture']} changed since the contract was written"
    try:
        proc = subprocess.run(
            shlex.split(contract["command"]),
            cwd=unit_dir,
            capture_output=True,
            text=True,
            timeout=contract.get("timeout_seconds", DEFAULT_TIMEOUT),
        )
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except OSError as e:
        return False, f"cannot run: {e}"
    if proc.returncode != contract["expected_exit"]:
        return False, f"exit {proc.returncode}, expected {contract['expected_exit']}"
    if contract["expected_stdout"] not in proc.stdout:
        return False, f"stdout lacks {contract['expected_stdout']!r}"
    return True, "ok"


def active_units(library, registry):
    """(entry, unit_dir, manifest) for every active registry entry. A missing unit is an error."""
    out = []
    for entry in registry["entries"]:
        if not entry.get("active"):
            continue
        unit = Path(library) / UNITS / entry["skill_id"] / entry["version"] / entry["name"]
        out.append((entry, unit, read_manifest(unit)))
    return out


def gate(candidate, manifest, library, registry):
    """Run every contract of every active version, then the candidate's. Never samples."""
    results = []
    for entry, unit, retained in active_units(library, registry):
        for contract in retained["task_contracts"]:
            ok, detail = run_contract(unit, contract)
            results.append({"skill_id": entry["skill_id"], "version": entry["version"],
                            "contract": contract["id"], "ok": ok, "detail": detail})
    for contract in manifest["task_contracts"]:
        ok, detail = run_contract(candidate, contract)
        results.append({"skill_id": manifest["skill_id"], "version": manifest["version"],
                        "contract": contract["id"], "ok": ok, "detail": detail})
    return results


def result_line(r):
    tag = "PASS" if r["ok"] else "FAIL"
    return f"{tag} {r['skill_id']}@{r['version']} {r['contract']}: {r['detail']}"


def promote(candidate, library=LIBRARY, now=None):
    """Full gate then commit. Raises ValueError on a static failure; returns a result dict."""
    candidate, library = Path(candidate), Path(library)
    registry_path = library / REGISTRY
    registry = load_registry(library)
    prior_bytes = registry_path.read_bytes()
    manifest = read_manifest(candidate)
    errors = check_candidate(candidate, manifest, registry, library)
    if errors:
        raise ValueError("\n".join(errors))

    results = gate(candidate, manifest, library, registry)
    if not all(r["ok"] for r in results):
        return {"ok": False, "results": results}

    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    validation_id = str(uuid.uuid4())
    unit = unit_dir_for(library, manifest)
    shutil.copytree(candidate, unit, ignore=IGNORE)
    validation = {"validation_id": validation_id, "validated_at": now,
                  "skill_id": manifest["skill_id"], "version": manifest["version"],
                  "contracts": results}
    (unit / VALIDATION).write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    package = package_sha256(unit)

    entry = {"skill_id": manifest["skill_id"], "version": manifest["version"], "name": manifest["name"],
             "package_sha256": package, "status": "validated", "active": True,
             "validation_id": validation_id, "promoted_at": now}
    new_registry = dict(registry)
    new_registry["entries"] = registry["entries"] + [entry]
    new_bytes = (json.dumps(new_registry, indent=2) + "\n").encode("utf-8")
    temp = library / (REGISTRY + ".tmp")
    temp.write_bytes(new_bytes)
    receipt = {"validation_id": validation_id, "skill_id": manifest["skill_id"],
               "version": manifest["version"], "package_sha256": package,
               "prior_registry_sha256": sha256_bytes(prior_bytes),
               "new_registry_sha256": sha256_bytes(new_bytes), "timestamp": now}
    with open(library / RECEIPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt) + "\n")
    os.replace(temp, registry_path)
    return {"ok": True, "results": results, "validation_id": validation_id,
            "package_sha256": package, "unit": str(unit)}


def main(argv):
    args = argv[1:]
    library = LIBRARY
    if "--library" in args:
        i = args.index("--library")
        library = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2 or args[0] != "--candidate":
        print(__doc__)
        return 2
    try:
        result = promote(args[1], library)
    except (ValueError, OSError, KeyError) as e:
        print(f"refused: {e}")
        return 1
    for r in result["results"]:
        print(result_line(r))
    if not result["ok"]:
        failed = sum(1 for r in result["results"] if not r["ok"])
        print(f"refused: {failed} contract(s) failed; registry untouched")
        return 1
    print(f"promoted {result['unit']} validation {result['validation_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
