# self-improve — feature spec

Grilled 2026-09-09. Abhishek: "run it on yourself, with a self-improving skill so I can ask any
updated AGI model to improve the whole thing through time." Answers: scope = this plugin repo
only; form = second skill in this repo; the loop never merges without a typed confirmation,
never edits the invariants, never spends money, never touches private run folders; first
self-run budget 30 min, 100 actions, 4 subagents, $0; criterion = one proposed step Abhishek
accepts.

## Today
Improving research-council depends on whoever is in the chat remembering the design, the dry
run and the bug log. A new model with no memory has no procedure to follow, so it either
guesses at improvements or rewrites what already works.

## Instead
Any model runs `/self-improve` in this checkout. The skill points research-council at its own
repo as the problem, with a fixed goal shape and the four budget numbers asked from the user.
The run ends with FINDINGS.md and HANDOFF.md in an ignored run folder, a de-identified run
note in `docs/runs/`, and proposed steps appended to the register in the S-n format. A human
ships each step as its own PR; the skill never merges unless the user types the exact
confirmation line.

## Acceptance
WHEN a model with no memory of this conversation runs `/self-improve` in a clean checkout THEN
it SHALL end with at least one proposed S-n step in `docs/spec-v1.md` whose claims each cite a
repo file and locator, and SHALL have merged nothing.

## Deliberately not here
- Self-merging, cron loops, or any autonomy beyond one run per invocation.
- Editing "Rules that never change" in `skills/research-council/SKILL.md`.
- Running on anything outside this repo (the user's other projects, memos, skills).
- Promotion into `library/`; a self-run is evidence-only.

## Steps

### S-21 — self-improve skill
**PR:** one.
**Depends on:** S-16.
**Files:** `skills/self-improve/SKILL.md`, `tests/test_self_improve.py`, `.gitignore`, `docs/decisions.md`.
**Today:** no skill; `library/` empty; `.gitignore` does not ignore `AGI_Research/`, so a self-run would show the S-16 warning and could be committed.
**Change:** write `skills/self-improve/SKILL.md` (valid per `scripts/validate_skill.py`) carrying: the fixed goal shape; the instruction to ask the user for the four budget numbers and one criterion; evidence from repo files only; the four must-nevers; the typed confirmation line `merge S-<n> confirmed`; the closing step that appends proposed steps and writes the run note. Add `AGI_Research/` to `.gitignore`. Add decision D-09.
**Acceptance:** WHEN `python3 scripts/validate_skill.py skills/self-improve` runs THEN it SHALL print `OK`, and WHEN any of the four must-never sentences or the confirmation line is removed THEN exactly one test SHALL fail.
**Verify:** `python3 -m unittest tests.test_self_improve -v` → pass; remove one must-never sentence → exactly one fail.
**Must not:** change `skills/research-council/`, `scripts/`, or `agents/`.

### S-22 — first self-run
**PR:** one (docs only).
**Depends on:** S-21.
**Files:** `docs/runs/2026-09-09-self-run.md`, `docs/spec-v1.md` (proposed steps section).
**Today:** the loop has never run.
**Change:** follow `skills/self-improve/SKILL.md` with the budget Abhishek gave (30 min, 100 actions, 4 subagents, $0) and the criterion "one proposed step I accept". Write the run note and append the proposed steps.
**Acceptance:** WHEN the PR is opened THEN `docs/spec-v1.md` SHALL contain at least one proposed step in the S-n format whose Today field cites a repo file and locator, and the run folder SHALL be absent from the diff.
**Verify:** `git diff main --stat` shows only the two files; `python3 -m unittest discover -s tests` still passes.
**Must not:** merge anything; write to `library/`; read outside this repo.

### S-23 — A zero dollar cap is a valid budget
**PR:** one.
**Depends on:** S-4.
**Files:** `scripts/goal.py`, `tests/test_goal.py`, `tests/test_budget.py`, `skills/research-council/references/goal.md`.
**Today:** `goal.py` line 109 rejects every budget number at or below zero, so `"usd_estimate_cap": 0` fails with `must be a number above 0` and a no-spend run cannot be expressed (bug 9).
**Change:** accept `0` for `usd_estimate_cap` only; goal.md says zero means no paid call.
**Acceptance:** WHEN the budget carries `"usd_estimate_cap": 0` THEN `goal.py new` SHALL write the goal, and WHEN the journal's first metered cost is recorded THEN `budget.py check` SHALL exit 2.
**Verify:** `python3 -m unittest tests.test_goal tests.test_budget -v` → pass; revert the condition → the two new tests fail.
**Must not:** change the other three floors or `budget.py`.

## Status
| step | status | learned |
|---|---|---|
| S-23 | done 2026-09-09 (PR #17) | Found in the first minute of the first self-run: the user's own must-never ("never spend") was not expressible as a budget. The fix is one condition, but it was queued and shipped before the run instead of using a made-up `$1`, because a value the user did not say is bug 1 again. Reverting the condition fails two tests, one per script, since goal.py accepts and budget.py enforces. The goal.md note is unguarded. |
