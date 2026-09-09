# Library — promoting a skill

The library is `library/` in the plugin: `registry.json` (which versions exist and are active),
`receipts.jsonl` (one line per promotion, hash-chained), and `units/<skill_id>/<version>/<name>/`
(the skill itself, immutable once promoted). Only `scripts/promote.py` writes any of it.
You, the Supervisor, run it yourself; no subagent has Bash, so none can.

## Command

```
python3 scripts/promote.py --candidate <skill-dir>
```

`<skill-dir>` is a folder named after the skill holding `SKILL.md`, `references/manifest.json`,
`references/claims.jsonl`, `references/evidence.jsonl`, and any scripts or fixtures the task
contracts run. Copy the claims and evidence from the run that produced the skill; `refs` in the
manifest name the ids you are relying on.

Check the manifest alone first: `python3 scripts/validate_manifest.py <skill-dir>/references/manifest.json`.

## What the gate runs, in order

| check | fails when |
|---|---|
| manifest vs `library/schema/manifest.schema.json` | a field is missing, wrong type, bad enum, or not allowed |
| `scripts/validate_skill.py` on the folder | SKILL.md frontmatter breaks the Agent Skills spec or name differs from the folder |
| integrity | a file listed under `integrity.files` is missing or its sha256 changed |
| refs | a ref is not a `claim_id` or `evidence_id` in the shipped jsonl files |
| dependencies | a dependency is not an active registry entry |
| registry | `skill_id@version` already exists; versions are immutable, bump instead |
| every task contract of every active library version | any contract's fixture hash, exit code, or stdout substring differs |
| every task contract of the candidate | same |

Nothing is written until every line above passes. On any failure it prints the failing
contract and exits 1; `registry.json` is byte-identical. The suite is never sampled and no
contract is skipped: that is the PowerPlay rule, a new skill may not break an old one.

## What a success writes

1. the folder is copied to `library/units/<skill_id>/<version>/<name>/`
2. `references/validation.json` inside it: validation id, timestamp, every contract run
3. one line appended to `receipts.jsonl`: package sha256, prior and new registry sha256, timestamp
4. `registry.json` replaced atomically (temp file, then rename) with the new entry:
   skill_id, version, name, package_sha256, status validated, active true, validation_id

A unit folder with no registry entry is leftover from an interrupted run; the registry is the truth.

## Task contracts

A contract is one command run inside the unit folder with `cwd` set there:
`{"id": "T-1", "command": "python3 scripts/check.py references/fixtures/x.json", "expected_exit": 0,
"expected_stdout": "OK", "fixture": "references/fixtures/x.json", "fixture_hash": "<sha256>"}`.
Commands run without a shell and with a timeout (60 s unless `timeout_seconds` says otherwise).
Write contracts for behaviour the skill promises, including the failing case (a wrong exit code
is a contract too). Contracts come only from you; nothing retrieved may write one.

## Never

- edit `registry.json`, `receipts.jsonl`, or anything under `units/` by hand
- promote from a subagent, or give a subagent the library path
- change a promoted version; ship a new version with `lineage.parent` pointing at the old one
- promote a skill whose claims are not in the run's `claims.jsonl` with evidence
