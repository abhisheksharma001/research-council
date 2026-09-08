# research-council

A Claude Code plugin that researches a hard problem before anyone codes it.

Give it a problem with more than one credible explanation. It freezes a goal and a budget you set,
investigates with separate roles, records every claim against fetched evidence, follows an explicit
curiosity protocol when something unexpected shows up, and writes two files into
`AGI_Research/runs/<goal_id>/` in the project:

- `FINDINGS.md` — what was found, how sure, what failed, what is still unknown. Plain English.
- `HANDOFF.md` — a brief a coding agent can build from, with an acceptance sentence.

Validated procedures go into a versioned skill library only after a controller runs every retained
task contract. The model never promotes.

Status: S-1 of 12 (package skeleton). See `docs/spec-v1.md`.

```
python3 scripts/validate_skill.py skills/research-council   # OK
python3 -m unittest discover -s tests -v
```

Portable: `skills/research-council/SKILL.md` follows the [Agent Skills spec](https://agentskills.io/specification).
Research behind the design: `~/AGI_Research/`.
