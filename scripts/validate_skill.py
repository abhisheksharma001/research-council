#!/usr/bin/env python3
"""Validate a skill directory against the Agent Skills spec (agentskills.io/specification).

Usage: python3 scripts/validate_skill.py <skill-dir>
Exit 0 and print OK when valid; exit 1 and print one line per broken rule otherwise.
Standard library only.
"""
import re
import sys
from pathlib import Path

ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(text):
    """Minimal YAML subset: top-level `key: value` and one nested mapping level (for metadata)."""
    if not text.startswith("---\n"):
        return None, text, ["frontmatter: file must start with '---'"]
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, ["frontmatter: closing '---' not found"]
    block = text[4:end]
    body = text[end + 4:].lstrip("\n")
    data, errors, current, nested_indent = {}, [], None, None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            errors.append(f"frontmatter: cannot parse line {raw!r}")
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if indent == 0:
            current, nested_indent = key, None
            data[key] = value if value else {}
        else:
            if current is None or not isinstance(data.get(current), dict):
                errors.append(f"frontmatter: nested key {key!r} without a parent mapping")
                continue
            if nested_indent is None:
                nested_indent = indent
            if indent != nested_indent or not value:
                errors.append(f"frontmatter: {current}.{key} nests deeper than one level; values must be strings")
                continue
            data[current][key] = value
    return data, body, errors


def unquote(v):
    if isinstance(v, str) and len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def validate(skill_dir):
    skill_dir = Path(skill_dir)
    errors = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"missing {skill_md}"]
    data, body, errors = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    if data is None:
        return errors

    unknown = set(data) - ALLOWED_KEYS
    for k in sorted(unknown):
        errors.append(f"frontmatter: unknown key {k!r} (allowed: {', '.join(sorted(ALLOWED_KEYS))})")

    name = unquote(data.get("name", ""))
    if not isinstance(name, str) or not name:
        errors.append("name: required")
    else:
        if len(name) > 64:
            errors.append("name: longer than 64 characters")
        if not NAME_RE.match(name):
            errors.append("name: must be lowercase a-z, 0-9 and single hyphens, not starting or ending with a hyphen")
        if name != skill_dir.name:
            errors.append(f"name: {name!r} must match directory name {skill_dir.name!r}")

    desc = unquote(data.get("description", ""))
    if not isinstance(desc, str) or not desc.strip():
        errors.append("description: required and non-empty")
    elif len(desc) > 1024:
        errors.append("description: longer than 1024 characters")

    compat = data.get("compatibility")
    if compat is not None:
        compat = unquote(compat)
        if not isinstance(compat, str) or not (1 <= len(compat) <= 500):
            errors.append("compatibility: must be 1-500 characters")

    meta = data.get("metadata")
    if meta is not None:
        if not isinstance(meta, dict):
            errors.append("metadata: must be a mapping of string keys to string values")
        else:
            for k, v in meta.items():
                if not isinstance(v, str) or isinstance(v, dict):
                    errors.append(f"metadata.{k}: value must be a string")

    tools = data.get("allowed-tools")
    if tools is not None and not isinstance(tools, str):
        errors.append("allowed-tools: must be a space-separated string")

    if len(body.splitlines()) > 500:
        errors.append("body: SKILL.md body exceeds 500 lines; move detail to references/")
    return errors


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    errors = validate(argv[1])
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
