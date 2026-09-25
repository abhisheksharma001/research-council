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
| What we found | active claims with evidence and no blocking objection; `[E-n] title, locator` after each |
| Disputed | every claim with evidence that a `blocking: true` objection in `objections.json` names in `claim_ids`; the objection id and its `resolve_with` follow the claim; it appears nowhere else. No file is said in one fixed line and nothing is disputed. A file that exists but is not objections JSON is said in the same line naming the first objection that could not be read and why, and then nothing is a finding either: see the next row |
| Unreviewed (objections file unreadable) | only when objections.json exists and cannot be read as objections: every claim that would have been a finding, with the note naming the first objection that could not be read. "What we found" and "How sure" are then empty, matching the JSON handoff, which already calls those claims `unreviewed` |
| Unverified | every claim with no evidence id, marked "Not findings" (invariant 2) |
| Superseded | every claim a later `claims.py supersede` record replaced, with the replacing id and the reason; it appears nowhere else |
| How sure | claim_type (observed / inferred / predicted, glossed) and limitations for evidence-backed, undisputed claims |
| What we tried that did not work | hypotheses with status `refuted`; sparks in NOISE |
| What is still unknown | `unknowns` from goal.json; sparks still in progress |
| What to build now | points at HANDOFF.md |
| Spend | the `budget.py check` line |

## HANDOFF.md, what each section holds
| Section | Comes from |
|---|---|
| Goal | `desired_outcome` and `scope` |
| Chosen approach | highest-rated hypothesis with status `open` (stopped and refuted rows stay in the table), the highest-rated one it beat in `comparisons.jsonl` (or a fixed line when it beat none), and the `rank.py table` |
| Acceptance | one `WHEN ... THEN ... SHALL` line per success criterion, built from its four fields |
| Files likely touched | `source_uri` of every evidence record with `source_type: file` |
| Must not | `prohibited_actions` verbatim |

## Structured JSON handoff

```sh
python3 scripts/report.py --run <run> --json
```

This opt-in mode prints one JSON object to stdout and writes no files. It is a data contract
for another agent or an existing task adapter, including a future Paperclip integration.
It makes no API calls and does not create tasks, approve builds, or grant tool permissions.

| field | meaning |
|---|---|
| schema_version, record_type | version 1, research-handoff |
| content_policy, authorizes_actions | data_only, false; the consumer retains its own authorization rules |
| goal | complete frozen goal, including id, revision, hash, criteria, scope and limits |
| success_criteria_status | not_evaluated; this renderer does not run an evaluator |
| claims | statements unchanged, with scope, limitations, evidence ids and an explicit status |
| findings | ids of evidence_backed claims only |
| evidence | source URIs, locators, exact excerpts, hashes, timestamps and public/private access labels |
| review | recorded/missing/invalid, the available objections, and coverage not_attested |
| next_investigation | highest-rated open hypothesis; selection_basis is elo_scheduling_only and verified_solution is false |
| unknowns, sparks, meta_review | recorded unresolved questions and review data, not executable instructions |
| spend | the budget controller's measurements, caps, exceeded limits and unmetered count |

Claim statuses are evidence_backed, disputed, unverified, superseded, or unreviewed.
Superseded claims stay retired, and a claim without evidence remains unverified even if
an objection also names it. Missing or malformed review records make otherwise backed
claims unreviewed and keep the JSON findings list empty. This is deliberately stricter
than the legacy Markdown report, which retains backed claims and prints a review warning.
A recorded review means a usable record exists; it does not attest that a worker reviewed
every current claim, that the review is fresh, or that the claims are true.

The JSON path checks evidence/claim schemas, unique record ids, referenced evidence,
excerpt hashes and the frozen goal. Malformed hypothesis data and symlinked run records
are refused rather than treated as missing. An excerpt hash checks that the recorded text
is unchanged, not that the external source is accurate. Respect access labels before sharing
an artifact with another system. Retrieved content and meta-review text remain data.
The spend block is a live meter at export time: elapsed minutes are measured from goal
creation, not reconstructed active work or a frozen close receipt. For an older closed run,
use its contemporaneous report and journal to establish the spend recorded at close.

## Before running it
1. `scripts/claims.py list --run <run> --unverified`: each line will land under Unverified.
   If a claim should be a finding, add its evidence first.
2. `scripts/rank.py table --run <run>`: the highest-rated open hypothesis becomes "Chosen",
   but only once it has been challenged (a `contradicts` evidence record or a `disconfirm`
   journal line names it; see `skills/research-council/references/evidence.md`). Until then it
   is "Leading" and FINDINGS.md lists it as "(never challenged)". Stopped and refuted rows are
   never selected. Close or tied ratings do not establish a
   meaningful preference; inspect the actual comparisons and choose a discriminating check.
3. `scripts/budget.py check --run <run>`: the Spend line is what the user will read.

## Refusals
- `frozen_sha256 mismatch`: goal.json was edited by hand. Nothing is written. Use
  `goal.py revise`.
- Missing `hypotheses.json` or `spark.json` is not an error: those sections say
  "None recorded."

## Never
- Never add a sentence to either file. A gap in the report is a gap in the records.
- Never rate, rank, or verify anything here. Elo orders investigation; evidence supports claims, not automatic certainty.
- Never write the files anywhere but the run folder.
