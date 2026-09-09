#!/usr/bin/env python3
"""Proximity retrieval: find prior validated skills whose words overlap a query (S-11).

Lexical only: the score is the number of distinct query words that also appear in a skill's
description (SKILL.md frontmatter), triggers, mechanism, or known counterexamples. Similarity is
not authority: every printed result carries its validation status, and the caller must still run
the skill's task contracts before trusting it.

    retrieve.py --query <text> --library <dir> [--scope public|private]

Only registry entries with status "validated" and active true are searched. Scope "public" (the
default) hides private skills and says how many were hidden; "private" shows both.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote  # noqa: E402
import validate_skill  # noqa: E402

TOP = 5
MIN_TOKEN = 2
STOPWORDS = frozenset(
    "a an and are as at be by for from in is it its no not of on or that the this to was were with".split()
)
NOT_AUTHORITY = ("similarity is not authority: scores count shared words only; "
                 "run each skill's task contracts before trusting it")


def tokens(text):
    """Lowercase alphanumeric words, minus stopwords, words shorter than MIN_TOKEN, and all-digit words."""
    return {t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) >= MIN_TOKEN and t not in STOPWORDS and not t.isdigit()}


def description_of(unit):
    data, _, _ = validate_skill.parse_frontmatter((Path(unit) / "SKILL.md").read_text(encoding="utf-8"))
    return validate_skill.unquote((data or {}).get("description", "")) or ""


def searchable_text(unit, manifest):
    """The four fields the step names, joined. Nothing else in the manifest is searched."""
    app = manifest["applicability"]
    return " ".join([description_of(unit), *app["triggers"], manifest["mechanism"], *app["known_counterexamples"]])


def load_units(library):
    """(entry, unit_dir, manifest) for every validated and active entry. Raises if no library."""
    registry = promote.load_registry(library)
    out = []
    for entry in registry["entries"]:
        if entry.get("status") != "validated" or not entry.get("active"):
            continue
        unit = Path(library) / promote.UNITS / entry["skill_id"] / entry["version"] / entry["name"]
        out.append((entry, unit, promote.read_manifest(unit)))
    return out


def _version_key(v):
    return tuple(int(p) for p in v.split("."))


def retrieve(query, library, scope="public"):
    """{"query_tokens", "results" (top TOP with score > 0), "hidden_private"}."""
    if scope not in ("public", "private"):
        raise ValueError(f"scope must be public or private, got {scope!r}")
    q = tokens(query)
    results, hidden = [], 0
    for entry, unit, manifest in load_units(library):
        if scope == "public" and manifest["access"]["scope"] == "private":
            hidden += 1
            continue
        matched = sorted(q & tokens(searchable_text(unit, manifest)))
        if not matched:
            continue
        results.append({
            "skill_id": entry["skill_id"], "version": entry["version"], "score": len(matched),
            "matched": matched, "status": entry["status"], "validation_id": entry["validation_id"],
            "promoted_at": entry["promoted_at"], "scope": manifest["access"]["scope"],
            "known_counterexamples": manifest["applicability"]["known_counterexamples"],
            "boundary": manifest["curiosity"]["boundary"],
            "contracts": [c["id"] for c in manifest["task_contracts"]],
        })
    results.sort(key=lambda r: (-r["score"], r["skill_id"], tuple(-p for p in _version_key(r["version"]))))
    return {"query_tokens": sorted(q), "results": results[:TOP], "hidden_private": hidden}


def snapshot_line(results):
    """One string for goal.json library_snapshot: skill@version validation <id> contracts T-1,T-2; ..."""
    return "; ".join(f"{r['skill_id']}@{r['version']} validation {r['validation_id']} "
                     f"contracts {','.join(r['contracts'])}" for r in results)


def render(found):
    lines = [NOT_AUTHORITY, f"query tokens: {' '.join(found['query_tokens']) or '(none)'}"]
    for i, r in enumerate(found["results"], 1):
        lines.append(f"{i}. {r['skill_id']}@{r['version']} score {r['score']} status {r['status']} "
                     f"(validation {r['validation_id']}, {r['promoted_at']}) scope {r['scope']}")
        lines.append(f"   matched: {', '.join(r['matched'])}")
        lines.append("   known counterexamples: " + ("; ".join(r["known_counterexamples"]) or "none recorded"))
        lines.append(f"   boundary: {r['boundary'] or 'none recorded'}")
        lines.append(f"   contracts: {', '.join(r['contracts'])}")
    if not found["results"]:
        lines.append("no matching skills")
    if found["hidden_private"]:
        lines.append(f"hidden: {found['hidden_private']} private skill(s); pass --scope private to include them")
    lines.append("snapshot: " + (snapshot_line(found["results"]) or "null"))
    return "\n".join(lines)


def main(argv):
    p = argparse.ArgumentParser(prog="retrieve.py", description=__doc__.splitlines()[0])
    p.add_argument("--query", required=True)
    p.add_argument("--library", default=str(promote.LIBRARY))
    p.add_argument("--scope", choices=("public", "private"), default="public")
    a = p.parse_args(argv)
    try:
        found = retrieve(a.query, a.library, a.scope)
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print(render(found))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
