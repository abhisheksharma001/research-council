# Report — FINDINGS.md and HANDOFF.md

One command, run when the council says stop or the budget says stop:
```bash
python3 scripts/report.py --run <run>
```
It writes `FINDINGS.md` and `HANDOFF.md` into the run folder and prints both paths.
It reads `goal.json`, `claims.jsonl`, `evidence.jsonl`, `hypotheses.json`, `spark.json`
and the spend line from `scripts/budget.py`. It writes nothing else and edits nothing.

Every sentence in the output is either copied from one of those records or is one of the
fixed headings and glosses listed in `FIXED` inside `scripts/report.py`. The script does
not summarise, infer, or reword. If the report reads badly, fix the record, then rerun.
You never edit FINDINGS.md or HANDOFF.md by hand.

## FINDINGS.md, what each section holds
| Section | Comes from |
|---|---|
| What you asked | `request_text` and `desired_outcome` in goal.json |
| What we found | every claim with at least one evidence id; `[E-n] title, locator` after each |
| Unverified | every claim with no evidence id, marked "Not findings" (invariant 2) |
| Superseded | every claim a later `claims.py supersede` record replaced, with the replacing id and the reason; it appears nowhere else |
| How sure | claim_type (observed / inferred / predicted, glossed) and limitations, verified claims only |
| What we tried that did not work | hypotheses with status `refuted`; sparks in NOISE |
| What is still unknown | `unknowns` from goal.json; sparks still in progress |
| What to build now | points at HANDOFF.md |
| Spend | the `budget.py check` line |

## HANDOFF.md, what each section holds
| Section | Comes from |
|---|---|
| Goal | `desired_outcome` and `scope` |
| Chosen approach | highest-rated non-refuted hypothesis, the one below it, and the `rank.py table` |
| Acceptance | one `WHEN ... THEN ... SHALL` line per success criterion, built from its four fields |
| Files likely touched | `source_uri` of every evidence record with `source_type: file` |
| Must not | `prohibited_actions` verbatim |

## Before running it
1. `scripts/claims.py list --run <run> --unverified`: each line will land under Unverified.
   If a claim should be a finding, add its evidence first.
2. `scripts/rank.py table --run <run>`: the top row becomes "Chosen". If two rows sit
   within 16 points, the choice is a coin flip; say so to the user or open a spark.
3. `scripts/budget.py check --run <run>`: the Spend line is what the user will read.

## Refusals
- `frozen_sha256 mismatch`: goal.json was edited by hand. Nothing is written. Use
  `goal.py revise`.
- Missing `hypotheses.json` or `spark.json` is not an error: those sections say
  "None recorded."

## Never
- Never add a sentence to either file. A gap in the report is a gap in the records.
- Never rate, rank, or verify anything here. Elo orders investigation; evidence verifies.
- Never write the files anywhere but the run folder.
