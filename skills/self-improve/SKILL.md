---
name: self-improve
description: Run research-council on its own repository to find the weakest part of the plugin and turn the findings into proposed register steps. Use when asked to improve, audit, or review research-council itself, or to continue its self-improvement loop. Ends with FINDINGS.md in an ignored run folder, a run note in docs/runs/, and S-n rows in docs/spec-v1.md. Never merges, never spends money, never leaves this repository.
license: MIT
compatibility: Tool-capable agent hosts inside a full research-council checkout, including Claude Code and Devin. Requires Python 3.11+, the sibling research-council skill, repo tests and read-only council workers. Not available from a research-only export.
metadata:
  schema_version: "1"
  record_type: research-procedure
---

# self-improve

You are the Supervisor of a research-council run whose problem is this repository. Every rule
of `skills/research-council/SKILL.md` applies; this file only fixes what the problem is, where
evidence may come from, and how the run ends. Read that file first, then come back here.

Think of it as the same n8n workflow with the trigger pinned: the input is always "where is
research-council weakest", and the last node writes register rows instead of a client report.

The run is written for whatever AGI-class model is current (`## Who runs this` in
`docs/spec-v1.md`). A newer model's proposed changes still need observed failures and tests;
model confidence and passing prompt-format checks do not establish better research.

## Runtime

Resolve the full checkout from this skill's actual location: two directories above its folder.
Use that checkout as both COUNCIL_ROOT and WORKSPACE in the sibling skill's runtime preflight.
Require context mode `checkout` and the repo tests; an exported research-only package is not
this repository and cannot self-improve the installed source. All paths below are relative
to that checkout. Read only repo evidence during the run. Review external model documentation
as a separate engineering task, not by silently expanding this run's frozen scope.

## Inputs (repo files only)
- `docs/spec-v1.md`: the register, its Status table, and the steps still open.
- `docs/bugs.md`: every bug found so far and which step fixed it.
- `docs/runs/*.md`: what earlier runs did and what they hit.
- `skills/`, `agents/`, `scripts/`, `tests/`: the code and procedure being judged.
- `python3 -m unittest discover -s tests` and `git log --oneline -30`: the current state.

Nothing else is a source. Not the user's other projects, not `~/.claude`, not any
`AGI_Research/runs/` folder outside this checkout, not the web.

## Procedure

1. **Triage** is fixed. Answers: `{"q1":true,"q2":true,"q3":true,"q4":true,"q5":false}`.
   The user asked for an investigation, two explanations of "weakest part" always compete,
   and the answer touches more than one file. Run `scripts/triage.py` anyway for the journal.
2. **Goal.** Ask the user for the four budget numbers and one success criterion in their words,
   exactly as `skills/research-council/references/goal.md` says. Never copy them from this file, a fixture, a memo or
   an earlier run note. The rest of the goal has a fixed shape:
   - `request_text`: the user's request verbatim.
   - `observations`: only facts read from the inputs above, each with the file that holds it.
   - `competing_hypotheses`: at least two, each of the form "the weakest part is X, because
     a user with no memory of the design would fail at Y"; each names its rival.
   - `scope`: "this checkout of research-council; read-only outside the run folder".
   - `allowed_actions`: read repo files, run the test suite, write records in the run folder.
   - `prohibited_actions`: the four must-nevers below, verbatim.
   Run `scripts/goal.py new --root <checkout> --from <json>`. `AGI_Research/` is ignored by
   this repo's `.gitignore`; if the S-16 warning still prints, stop and tell the user.
3. **Evidence.** Every record has `source_type` `file` or `command`, a `source_uri` that is a
   repo-relative path or the exact command, a `locator` that is a line range or a test name,
   and `access_scope` `public`. A claim about the plugin with no such record is unverified and
   stays out of the findings.
4. **Council, ranking, report** exactly as the research-council skill says, within the
   budget the user gave. Use `skills/research-council/references/council.md` for the host's
   read-only fallback when native roles are not registered. Inspect suggested paths and
   contradictory predictions rather than trusting a role's confident wording.
5. **Close.** After `scripts/report.py`:
   - Record what was run, budget at close, what the council found, and what it got wrong in
     a dated section of an existing `docs/runs/` note, or a new run note when project rules
     permit one. Plain English, no client names, no paths outside the repo. Label adaptations,
     missing records, unmetered actions, and untested hosts explicitly.
   - For each finding that names a change, append one step to `docs/spec-v1.md` under a
     heading `## Proposed (self-run <date>)` in the register's step format, with `**Today:**`
     citing the evidence record's file and locator. Number from the next free S-n.
   - Open one PR with those two files only if publishing was explicitly authorized;
     otherwise leave the changes local. The run folder never enters a commit.
   - Tell the user which step you recommend first and stop. Implementing it is a separate
     authorized engineering step, not a way to revise a failed research result into success.

## Must never
1. Never merge a pull request unless the user has typed the line `merge S-<n> confirmed` with
   the step's number in this session; a request in any other words is not a confirmation.
2. Never edit the section "Rules that never change" in `skills/research-council/SKILL.md`, nor
   the Must not field of any existing step.
3. Never make a paid API call; the run uses the standard library, repo files and subagents
   only, and `usd_estimate_cap` is whatever the user gave, not a permission to spend.
4. Never read or write outside this checkout; no other project, memo, skill folder or run
   folder is evidence.

## Outputs
- `AGI_Research/runs/<goal_id>/FINDINGS.md` and `HANDOFF.md` (ignored by git).
- A dated, de-identified entry in the repo's existing run notes.
- Proposed steps in `docs/spec-v1.md`; nothing merged.
