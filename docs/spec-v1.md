# research-council v1 — feature spec

## Today
A user with a hard problem ("webhook sometimes double-books", "which STT provider", "why does recall drop after batch 24") asks a coding agent. The agent guesses one explanation and starts coding. Nothing is recorded, nothing is reusable, alternatives are never tested.

## Instead
User runs `/research-council <problem>` in Claude Code. If the problem is small, it says so and stops. Otherwise it: freezes a goal with competing explanations and a user-set budget, retrieves prior validated skills, runs a bounded investigation with separate roles, records every claim against fetched evidence, follows the fire protocol when something unexpected shows up, writes `AGI_Research/runs/<goal_id>/FINDINGS.md` in plain English plus `HANDOFF.md` a coding agent can build from, and offers a skill to the library where a controller runs the full regression suite before accepting it.

## Acceptance
WHEN a user gives one real problem with at least two credible explanations THEN the plugin SHALL produce FINDINGS.md where every claim links to an evidence record with a locator, HANDOFF.md with an EARS acceptance sentence, a journal showing spend against the user-set budget, and zero library changes unless `scripts/promote.py` reports every task contract passed.

## Deliberately not in v1
- Codex / Cursor / Gemini adapters (D-01, later)
- Sandbox execution of experiments (evidence-only mode; invariant 8)
- Compression-progress bit counting with held-out probes (needs labelled probes; v1 schedules by hypothesis elimination and fire-protocol state)
- Embedding retrieval (lexical only)
- Case-study ingestion pipeline
- Any UI beyond markdown files

## Layout (planned)
```
.claude-plugin/plugin.json
skills/research-council/SKILL.md          entry point, Agent Skills spec
skills/research-council/references/       procedure docs loaded on demand
agents/*.md                               council roles as Claude Code subagents
strategies/*.md                           curiosity strategies (fire.md first)
scripts/*.py                              triage, goal, budget, journal, evidence, claims, rank, spark, report, promote, retrieve, validate_skill
library/                                  versioned validated skills + registry.json + receipts.jsonl
tests/
```
Target-project output: `AGI_Research/runs/<goal_id>/{goal.json,journal.jsonl,evidence.jsonl,claims.jsonl,hypotheses.json,spark.json,FINDINGS.md,HANDOFF.md}`

---

# Step register

### S-1 — Plugin skeleton that a validator accepts
**PR:** one.
**Depends on:** nothing.
**Files:** `.claude-plugin/plugin.json`, `skills/research-council/SKILL.md`, `scripts/validate_skill.py`, `tests/test_validate_skill.py`, `README.md`.
**Today:** empty repo.
**Change:** plugin.json with name `research-council`, version 0.1.0. SKILL.md with frontmatter `name: research-council`, a description that says what it does and when to use it (mentions "research", "investigate", "competing explanations", "not for small tasks"), body with sections When to use / When not to use / Procedure (placeholder pointing at later steps). validate_skill.py enforces the Agent Skills spec: name 1-64 chars lowercase a-z0-9 and hyphens, no leading/trailing/double hyphen, matches directory; description 1-1024 chars; only allowed frontmatter keys (name, description, license, compatibility, metadata, allowed-tools); metadata values are strings; compatibility ≤500 chars; body under 500 lines.
**Acceptance:** WHEN `python3 scripts/validate_skill.py skills/research-council` runs THEN it SHALL exit 0 and print `OK`, and WHEN the name is changed to `Research-Council` THEN it SHALL exit 1 naming the rule broken.
**Verify:** `python3 -m unittest discover -s tests -v` → all pass. `python3 scripts/validate_skill.py skills/research-council` → `OK`.
**Must not:** add any pip dependency; add any behaviour beyond validation.

### S-2 — Triage refuses small problems with a reason
**PR:** one.
**Depends on:** S-1.
**Files:** `scripts/triage.py`, `skills/research-council/references/triage.md`, `tests/test_triage.py`, `skills/research-council/SKILL.md` (Procedure step 1 only).
**Today:** plugin accepts anything.
**Change:** triage.py reads the request text from stdin or a file and a JSON of answers to five fixed yes/no questions the agent must answer first: (1) more than one credible explanation? (2) outcome cannot be verified by one command or one test? (3) affects more than one file, service, or user? (4) user asked for research explicitly? (5) a wrong answer costs money, data, or a client? Rule: big if (4) or at least two of (1)(2)(3)(5). Output JSON `{"verdict":"big|small","reasons":[...]}`. triage.md tells the agent to answer the five questions from the request before calling the script and to stop with the printed reason when small. Deterministic. No LLM call inside the script.
**Acceptance:** WHEN answers are all "no" THEN verdict SHALL be `small` with reasons listing the failed questions, and WHEN (4) is "yes" THEN verdict SHALL be `big`.
**Verify:** `python3 -m unittest tests.test_triage -v` → 4 tests pass (all-no, explicit-ask, two-of-four, one-of-four).
**Must not:** call any model; read the workspace.

### S-3 — Goal capture, frozen revision
**PR:** one.
**Depends on:** S-2.
**Files:** `scripts/goal.py`, `skills/research-council/references/goal.md`, `tests/test_goal.py`.
**Today:** no goal record.
**Change:** `goal.py new --root <dir> --from <json>` writes `AGI_Research/runs/<goal_id>/goal.json` with required fields: goal_id (uuid4), revision (1), request_text, observations[], suggested_explanations[], desired_outcome, scope, unknowns[], competing_hypotheses[] (≥2 entries each with id, statement, predicted_result, strongest_alternative), success_criteria[] (each: measurement, evaluator, environment, pass_condition), baseline, allowed_actions[], prohibited_actions[], budget (S-4 schema), library_snapshot (string or null), created_at, frozen_sha256 (hash of all fields above). `goal.py revise` creates revision n+1 with `reason` and keeps prior revisions in `goal.history.jsonl`. Missing required field → exit 1 naming it. goal.md gives the agent the goal-statement template from the design and the rule "an unknown stays unknown".
**Acceptance:** WHEN a goal JSON lacks `competing_hypotheses` or has fewer than two THEN `goal.py new` SHALL exit 1 naming the field, and WHEN a valid goal is written THEN `frozen_sha256` SHALL change only via `goal.py revise`.
**Verify:** `python3 -m unittest tests.test_goal -v` → pass. Manual: run `new` on `tests/fixtures/goal_booking.json`, cat the output.
**Must not:** invent success criteria when absent (must fail instead).

### S-4 — Budget block and journal with running spend
**PR:** one.
**Depends on:** S-3.
**Files:** `scripts/budget.py`, `scripts/journal.py`, `skills/research-council/references/budget.md`, `tests/test_budget.py`.
**Today:** nothing tracks spend.
**Change:** budget schema in goal.json: `{minutes, max_actions, max_subagents, usd_estimate_cap, set_by:"user"}`. All four numbers required; no defaults in code. `journal.py add --run <dir> --kind <fetch|read|write|subagent|exec|note> --cost_usd <float|null> --detail <text>` appends a JSON line with timestamp. `budget.py check --run <dir>` sums elapsed minutes since goal.created_at, action count, subagent count, and usd (nulls counted as 0 and reported as "unmetered: N"); prints a one-line status `spent: 12/60 min, 30/200 actions, 2/4 subagents, ~$0.40/$5 (unmetered: 3)`; exits 2 when any cap is exceeded. budget.md tells the agent to ask the user for the four numbers before starting and to run `budget.py check` before every subagent spawn and every ten actions.
**Acceptance:** WHEN actions exceed `max_actions` THEN `budget.py check` SHALL exit 2 and name the exceeded cap, and WHEN goal.json has no budget THEN `goal.py new` (S-3) SHALL exit 1.
**Verify:** `python3 -m unittest tests.test_budget -v` → pass.
**Must not:** default any cap; raise a cap from inside any script.

### S-5 — Evidence and claim records
**PR:** one.
**Depends on:** S-3.
**Files:** `scripts/evidence.py`, `scripts/claims.py`, `skills/research-council/references/evidence.md`, `tests/test_evidence.py`.
**Today:** claims live only in chat.
**Change:** `evidence.py add` writes to `evidence.jsonl`: evidence_id, source_type (web|file|command|user|paper), source_uri, title, locator (page/section/line-range/timestamp/artifact key, required), excerpt (required, ≤2000 chars), retrieved_at, sha256 of excerpt, access_scope. `claims.py add` writes to `claims.jsonl`: claim_id, statement, claim_type (observed|inferred|predicted), scope, evidence_ids (must all exist in evidence.jsonl, else exit 1), test_ids[], limitations. `claims.py list --unverified` prints claims with zero evidence_ids. evidence.md: "every quantitative claim points to a locator; a missing artifact blocks the claim".
**Acceptance:** WHEN a claim references an evidence_id not in evidence.jsonl THEN `claims.py add` SHALL exit 1 and write nothing.
**Verify:** `python3 -m unittest tests.test_evidence -v` → pass.
**Must not:** accept an evidence record without a locator.

### S-6 — Council roles as subagents
**PR:** one.
**Depends on:** S-5.
**Files:** `agents/generation.md`, `agents/reflection.md`, `agents/ranking.md`, `agents/meta-review.md`, `skills/research-council/references/council.md`, `tests/test_agents.py`.
**Today:** one context does everything.
**Change:** four Claude Code subagent definitions with frontmatter (name, description, tools). Generation: produces hypotheses + discriminating investigations, each with predicted_result, strongest_alternative, needed_evidence, stop_condition; writes only `hypotheses.json`. Reflection: audits provenance, lists counterexamples, issues blocking objections referencing claim_ids; cannot add evidence; writes `objections.json`. Ranking: pairwise comparisons per S-7 rubric; writes `comparisons.jsonl`. Meta-review: synthesises recurring weaknesses and next investigation; writes `meta.md`; may recommend stop. Tools restricted: Generation/Reflection/Ranking get Read + the run dir; only the Supervisor (main context) gets Write outside the run dir. Evolution and Proximity are not agents in v1: Evolution = Generation with a `parent_id`; Proximity = S-11 script. council.md gives the dispatch order per lifecycle stage.
**Acceptance:** WHEN each agent file is parsed THEN it SHALL have name, description, and a tools list that excludes Write for reflection and ranking.
**Verify:** `python3 -m unittest tests.test_agents -v` → pass.
**Must not:** give any subagent access to `library/` or `scripts/promote.py`.

### S-7 — Blinded Elo tournament
**PR:** one.
**Depends on:** S-6.
**Files:** `scripts/rank.py`, `tests/test_rank.py`.
**Today:** no ranking.
**Change:** `rank.py pair --run <dir> --seed <n>` picks two eligible hypotheses (prefers new + top, shared opponents), emits a blinded pair (A/B, random order, author stripped) for the Ranking agent. `rank.py record --run <dir> --pair <id> --winner A|B|draw --judgment <text>` appends to `comparisons.jsonl` and updates Elo in `hypotheses.json` with start 1200, K=16, scores 1/0.5/0. `rank.py cycles` reports non-transitive triples. `rank.py table` prints ratings with comparison counts. Elo affects only scheduling order.
**Acceptance:** WHEN A (1200) beats B (1200) THEN A SHALL be 1208 and B 1192, and WHEN A>B, B>C, C>A are recorded THEN `rank.py cycles` SHALL list that triple.
**Verify:** `python3 -m unittest tests.test_rank -v` → pass.
**Must not:** let Elo gate promotion or mark a claim verified.

### S-8 — Fire protocol (curiosity strategy 1)
**PR:** one.
**Depends on:** S-5.
**Files:** `strategies/fire.md`, `scripts/spark.py`, `skills/research-council/references/curiosity.md`, `tests/test_spark.py`.
**Today:** unexpected observations are lost.
**Change:** fire.md is the strategy in plain English, six states with the trigger, action, and stop rule for each: SPARK (log an observation that contradicts a prediction; no reward), REPEAT (reproduce ≥2 times under same conditions; if it does not repeat → mark noise, stop), VARY (change one condition at a time; record each trial as evidence), BOUNDARY (write the conditions where it works and where it fails as a claim with scope), COMBINE (try composing with one existing library skill or one extra ingredient), NAME (draft a skill candidate with applicability + failure boundaries). `spark.py new/advance/status` keeps `spark.json` per observation with state, trials[], and `prediction_before`/`prediction_after`; `advance` to BOUNDARY requires ≥2 successful repeats and at least one failed variation; reward field `progress` is set only when prediction_after is more specific than prediction_before (string test in v1: the scope narrowed). curiosity.md tells the agent when to open a spark: any observation that contradicts a hypothesis's predicted_result, or any time two candidates tie in Elo within 16 points.
**Acceptance:** WHEN a spark has one successful repeat THEN `advance --to BOUNDARY` SHALL exit 1 saying "need 2 repeats", and WHEN it has two repeats and one failed variation THEN it SHALL advance.
**Verify:** `python3 -m unittest tests.test_spark -v` → pass.
**Must not:** award progress for novelty, volume, or confidence text.

### S-9 — FINDINGS.md and HANDOFF.md from records only
**PR:** one.
**Depends on:** S-5, S-7, S-8.
**Files:** `scripts/report.py`, `skills/research-council/references/report.md`, `tests/test_report.py`, `tests/fixtures/run_min/`.
**Today:** no output document.
**Change:** `report.py --run <dir>` renders FINDINGS.md with sections: What you asked; What we found (one paragraph per claim with evidence links `[E-3]` → locator); How sure (claim_type + limitations); What we tried that did not work (refuted hypotheses + sparks marked noise); What is still unknown; What to build now (points to HANDOFF.md); Spend (from budget.py). Claims with zero evidence render under "Unverified". HANDOFF.md: goal statement, chosen approach and the alternative it beat (with Elo table), EARS acceptance sentence taken from success_criteria, files likely touched (from evidence of type file), must-not list from prohibited_actions. Plain English, no jargon without a one-line gloss.
**Acceptance:** WHEN a claim has no evidence_ids THEN it SHALL appear only under "Unverified" in FINDINGS.md, and WHEN the fixture run is rendered THEN HANDOFF.md SHALL contain one line starting with "WHEN " and containing " SHALL ".
**Verify:** `python3 -m unittest tests.test_report -v` → pass; open the fixture output and read it as the user would.
**Must not:** include any sentence not traceable to goal.json, claims.jsonl, evidence.jsonl, hypotheses.json, or spark.json.

### S-10 — Library with promotion gate
**PR:** one.
**Depends on:** S-9.
**Files:** `scripts/promote.py`, `scripts/validate_manifest.py`, `library/registry.json`, `library/receipts.jsonl`, `library/schema/manifest.schema.json`, `tests/test_promote.py`, `tests/fixtures/skill_min/`.
**Today:** no library.
**Change:** layout `library/units/<skill_id>/<version>/<name>/` with SKILL.md, `references/manifest.json`, `references/claims.jsonl`, `references/evidence.jsonl`, `references/validation.json`. Manifest fields per design (schema_version, skill_id, name, version, record_type, evidence_level, origin, goal, applicability, inputs, outputs, mechanism, procedure, dependencies, conflicts, refs, task_contracts[], curiosity, lineage, integrity, access). `promote.py --candidate <dir>`: validates manifest against schema; runs `validate_skill.py`; runs every task contract of every active library version plus the candidate's contracts (each contract = a command with expected exit code and expected stdout substring, fixture_hash checked); on any failure prints the failing contract and exits 1 with registry untouched; on success writes validation.json, appends a receipt (package sha256, prior registry sha256, new registry sha256, timestamp), updates registry.json atomically (write temp, rename). Registry entry: skill_id, version, package_sha256, status validated, active true, validation_id.
**Acceptance:** WHEN any retained task contract fails THEN `promote.py` SHALL exit 1 and registry.json SHALL be byte-identical to before, and WHEN all pass THEN registry.json SHALL list the new version and receipts.jsonl SHALL gain one line.
**Verify:** `python3 -m unittest tests.test_promote -v` → pass. Break test: edit fixture contract's expected output, rerun, see refusal.
**Must not:** sample the suite; skip a contract; be callable from any subagent.

### S-11 — Proximity retrieval at goal start
**PR:** one.
**Depends on:** S-10.
**Files:** `scripts/retrieve.py`, `tests/test_retrieve.py`, `skills/research-council/references/goal.md` (add step).
**Today:** prior skills unused.
**Change:** `retrieve.py --query <text> --library <dir>` lexical search (token overlap, stdlib only) over description, triggers, mechanism, known_counterexamples of validated+active versions; filters by access scope; prints top 5 with skill_id, version, score, and the failure boundaries. goal.md: run before writing competing hypotheses; loaded skills' contracts go in `library_snapshot`.
**Acceptance:** WHEN the query shares three tokens with one skill's triggers and none with another THEN that skill SHALL rank first, and WHEN a skill is status deprecated THEN it SHALL not appear.
**Verify:** `python3 -m unittest tests.test_retrieve -v` → pass.
**Must not:** treat similarity as authority (output must show validation status).

### S-12 — End-to-end dry run on one real problem
**PR:** one (docs + bug log only).
**Depends on:** S-1..S-11.
**Files:** `docs/runs/2026-xx-first-run.md`, `docs/bugs.md`, `docs/spec-v1.md`.
**Today:** never run on a real problem.
**Change:** run `/research-council` on a real problem Abhishek names (candidate: Rush booking-failure audit, fixtures in memo `rush-audit`). Evidence-only mode. Record what broke as bugs, correct the spec where wrong, queue fixes as S-13+.
**Acceptance:** WHEN the run finishes THEN FINDINGS.md and HANDOFF.md SHALL exist with zero claims outside "Unverified" lacking evidence, and every bug found SHALL be in docs/bugs.md with a repro.
**Verify:** read the two files; `python3 scripts/claims.py list --unverified` matches the Unverified section.
**Must not:** promote anything to the library during the dry run without Abhishek's go.

## Status
| step | state | learned |
|---|---|---|
| S-1 | done 2026-09-09 | Minimal YAML parser silently flattened two-level metadata; caught by the nested-metadata test, fixed by rejecting any nested key deeper than one level or with an empty value. Break tests: removing the lowercase rule fails exactly test_uppercase_name_rejected; removing the directory-match rule fails exactly test_name_must_match_directory. Register edit was lost once because a string replace missed silently and the commit went through on an unrelated pyc change: replace scripts now assert the match. |
| S-2 | done 2026-09-09 (PR #1) | Kept the model out of the script: the agent answers five yes/no questions, the script applies the rule. This makes triage testable and prevents the LLM from talking itself into 'big'. Exit code 3 for small so the skill can branch on it without parsing JSON. Break tests: q4 shortcut removal fails 2 named tests; MIN_YES=1 fails exactly one. No CI on the repo yet, so 'wait for CI' was skipped; tests ran locally. |
| S-3..S-12 | todo | |
