#!/usr/bin/env python3
"""Validate a library manifest against library/schema/manifest.schema.json.

Usage: python3 scripts/validate_manifest.py <manifest.json> [--schema <schema.json>]
Exit 0 and print OK when valid; exit 1 and print one FAIL line per broken rule otherwise.

The schema uses a small subset of JSON Schema and this file is the only checker for it
(standard library only, no jsonschema package): type, required, properties,
additionalProperties, enum, const, items, minItems, minLength, pattern.
Unknown schema keywords are an error, not silently ignored.
"""
import json
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "library" / "schema" / "manifest.schema.json"
KNOWN_KEYWORDS = {
    "$comment", "type", "required", "properties", "additionalProperties", "enum", "const",
    "items", "minItems", "minLength", "pattern",
}
TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _is_type(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, TYPES[name])


def check(value, schema, path="$"):
    """Return a list of error strings for value against schema; empty means valid."""
    errors = []
    unknown = set(schema) - KNOWN_KEYWORDS
    if unknown:
        return [f"{path}: schema uses unsupported keyword(s) {sorted(unknown)}"]

    if "const" in schema and value != schema["const"]:
        return [f"{path}: must equal {schema['const']!r}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: must be one of {schema['enum']}"]

    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, t) for t in allowed):
            return [f"{path}: must be {' or '.join(allowed)}"]

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: shorter than {schema['minLength']} characters")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append(f"{path}: does not match {schema['pattern']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(value):
                errors.extend(check(item, schema["items"], f"{path}[{i}]"))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                errors.extend(check(value[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(props)):
                errors.append(f"{path}.{key}: not an allowed field")
    return errors


def load_schema(path=SCHEMA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(manifest, schema=None):
    """Errors for a manifest dict. Adds the two cross-field rules the schema cannot say."""
    errors = check(manifest, schema or load_schema())
    if errors:
        return errors
    for i, contract in enumerate(manifest["task_contracts"]):
        has_fixture, has_hash = "fixture" in contract, "fixture_hash" in contract
        if has_fixture != has_hash:
            errors.append(f"$.task_contracts[{i}]: fixture and fixture_hash must be given together")
    for key, digest in manifest["integrity"]["files"].items():
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"$.integrity.files.{key}: must be a sha256 hex digest")
    return errors


def main(argv):
    args = argv[1:]
    schema_path = SCHEMA
    if "--schema" in args:
        i = args.index("--schema")
        schema_path = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    try:
        manifest = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FAIL cannot read manifest: {e}")
        return 1
    errors = validate(manifest, load_schema(schema_path))
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
