# code-writer-council — feature spec

Grilled 2026-09-17. Abhishek: "whenever it starts writing code it should be in this council,
how we are doing with research in the same way; it should be designed for improving better
code writing through AI; everyone can rely on it at the same point of time, it shouldn't be
the in-depth research timing; use BAML and other repos if needed; the council will live in
the harness agent; same repo; and I was thinking if one could be a parallel thinker."
Answers (defaults accepted with `next`): write first, then review, no planner role; tiers by
diff size with a no-council exit for tiny edits; per-task caps the user sets once per repo;
guard scripts decide "done", never the model; a learning-mode flag for the reply; parallel
reviewers on, a parallel Thinker on, parallel writers off. BAML is an idea, not a dependency
(D-13). Third skill in this repo (D-14). Product name parked (O-19).

## Today
A coding agent gets a request, edits files, says "done". Nothing checks that the tests were
run after the last edit, that the diff stayed inside the task, that a new import names a
package that exists, or that a second pair of eyes read the change. The research run of
2026-09-17 (`docs/runs/2026-09-17-coding-agents.md`) put numbers on each of these: 91.49% of
visible misalignments needed the user to correct the agent and false self-reports are
growing (C-2); deception and constraint violations lead 547 operational failures (C-3); only
44% of agent code survives into commits (C-4); package names are hallucinated on 4.62% to
6.10% of prompts by 2026 models (C-5); larger diffs and failed CI checks are what stop merges
(C-1, C-17); 13.8% of long rollouts contain an attempt to fool the verifier (C-30).

## Instead
Whenever the agent is about to change code in a repository where this plugin is installed,
the code-writer-council skill runs. It is the research-council loop with the trigger pinned
to "write code" and the clock set for minutes, not hours. A frozen task record carries the
request, the allowed paths, the test command and the user's caps. The Supervisor writes the
code itself while a Thinker, in parallel, drafts the tests that would catch the naive
implementation. The diff's size picks how many Reviewers read it, in parallel, each with its
own lens. Scripts check scope, dependencies and the test run. The word "done" is printed by
a script after it has run the tests itself, or it is not said. A tiny edit (ten diff lines or
fewer) takes the exit: no subagent, scripts only.

n8n analogy: research-council is a long workflow you start by hand; this is the same nodes
wired as a trigger on every code edit, with a timeout on each node.

## Who runs this
Same as `## Who runs this` in `docs/spec-v1.md`: an AGI-class model in a tool-capable host.
One difference from research-council: the Supervisor is also the Writer, because it holds
the user's conversation and intent, and a fresh-context review is what the evidence rewards
(C-19), not a fresh-context writer. Roles that read the code never get Write or Bash.

## Evidence this design rests on
Claim ids refer to `docs/runs/2026-09-17-coding-agents/FINDINGS.md`.

| design rule | claims |
|---|---|
| Write first, review after; no planner role | C-18 (plan-then-code below baseline, review-then-fix +10.4 points) |
| Reviewer runs in a fresh context; the reviewer is not the main guard | C-19 (Claude self-review on Claude drafts changed nothing; fresh-model review +18 points) |
| Tiers by diff size; tiny edits skip the council | C-20 (2/4/7+ agents at 10/100 lines, median 3m39s), C-1, C-17 (smaller PRs merge) |
| A script runs the tests and prints "done"; the model never does | C-2 (91.49% corrections, false self-reports), C-3 (deception), C-27 (verify before acting) |
| Test command frozen at task start; weakening tests is flagged | C-30 (verifier exploitation in 13.8% of rollouts), C-25 (weak tests hide failures) |
| New dependency needs a registry record before install | C-5 (4.62% to 6.10% hallucinated packages, 127 shared names), C-6 (grounding holds under adversarial prompts) |
| Scope guard on paths and line count; split over the cap | C-1 (+files, +size, failed CI cut merges), C-3 (constraint violations), C-8, C-10, C-13 (state handling degrades over long tasks) |
| Thinker drafts tests in parallel with the write | C-25 (31.08% of accepted resolutions had tests too weak to verify), C-27 |
| Parallel reviewers with distinct lenses | C-20 (coordinator over specialist agents), C-4 (security lens), C-9 (erosion lens) |
| Learning mode in the reply | C-15 (delegation-style use scored below 40%, inquiry-style 65%+) |
| Per-task minutes cap, no research timing | C-14 (experienced developers slowed 19%), user: "everyone can rely on it at the same point of time" |
| Parallel writers off | no measurement on file; the dual-generation pattern was seen only as a paper heading |
| BAML idea only | C-23, C-29, D-13 |

## Acceptance
WHEN a user asks for a code change in a repository with this plugin and the skill is followed
THEN the reply SHALL say "done" only by quoting a `DONE <diff sha>` line printed by
scripts/done.py after it ran the frozen test command with exit 0 on the final diff, with scope
and dependency checks clean and every blocking review finding resolved; and WHEN the final
diff is ten lines or fewer THEN no subagent SHALL have been spawned.

## Rules that never change (this skill)
1. "Done" is printed by scripts/done.py after it runs the tests. The model copies the line; it never composes one.
2. The test command and the allowed paths are frozen in task.json at task start. Changing them is a new task, not an edit.
3. No package is installed and no new import is left in the diff without an evidence record from the registry page naming that package.
4. Roles that read code (Reviewer, Thinker) never get Write or Bash. They return one JSON object; the Supervisor saves it.
5. Caps are the user's, set once per repository in .code-council/config.json. No script defines a default cap. (CLAUDE.md invariant 4.)
6. The council never pushes, never merges, never touches CI configuration without the user's words in the task record.
7. A blocking finding is closed by a fix (new diff sha) or by the user's exact words. Never by the model's judgement alone.

## Deliberately not here
- Parallel writers (two Writers, Reviewer picks). No measurement on file; add a step when a run measures it.
- A planner role. C-18 measured it below baseline; the Thinker's tests are the plan.
- A cross-vendor reviewer. C-19 says it helps; Claude Code cannot spawn another vendor's model. Later adapter.
- BAML as a dependency (D-13). Schema-aligned repair of a role's reply is reimplemented in the standard library where a step needs it.
- Auto-commit, push, merge, or opening pull requests.
- Any per-task budget conversation. Caps are asked once per repository.

## Layout (planned)
```
skills/code-writer-council/SKILL.md        entry point, triggers on writing or changing code
skills/code-writer-council/references/     task.md, tiers.md, done.md
agents/code-reviewer.md                    fresh-context reviewer, one lens per spawn, returns findings JSON
agents/code-thinker.md                     parallel test drafter, returns test cases JSON
scripts/task.py                            task.json: frozen request, paths, test command, caps
scripts/scope.py                           diff inside allowed paths and line cap; verifier-edit flag
scripts/deps.py                            new dependency names in the diff resolved or listed
scripts/done.py                            runs the test command, checks the guards, prints DONE or NOT DONE
tests/test_code_council.py, test_task.py, test_scope.py, test_deps.py, test_done.py
```
Target-project output: `AGI_Research/code/<task_id>/{task.json,journal.jsonl,evidence.jsonl,thinker.json,review-<n>.json,resolutions.jsonl,fence/}`. Ignored by the workspace's git (S-16 rule).

Shared with research-council: `scripts/budget.py`, `scripts/journal.py`, `scripts/evidence.py`,
`scripts/fence.py`, `scripts/harness.py`. Each new script is added to RUNTIME_SCRIPTS in
harness.py in the step that creates it.

## Tiers
Diff lines are added plus removed, from `git diff --numstat` against the task's start commit.

| diff lines | Reviewers | Thinker | subagents |
|---|---|---|---|
| 0 to 10 | none | none | 0 |
| 11 to 100 | 1 (correctness + security) | yes | 2 |
| over 100 | 2 in parallel (A: correctness + security; B: scope + erosion) | yes | 3 |

The Thinker starts with the write when task.json says `expected_small: false`. When a task
expected small ends over ten lines, the Thinker runs after the write and the journal notes the
misestimate. When the subagent cap is below the tier's count, the lowest-priority spawn is
dropped (B, then Thinker) and the reply says which.

## Steps

### S-36 — code-writer-council skill skeleton
**PR:** one.
**Depends on:** S-31.
**Files:** `skills/code-writer-council/SKILL.md`, `tests/test_code_council.py`, `.github/workflows/tests.yml`, `README.md`.
**Today:** no skill; `tests/test_ci.py` line 16 requires the workflow to validate every folder under `skills/`, so a new folder without a workflow line fails CI.
**Change:** SKILL.md valid per `scripts/validate_skill.py`: name `code-writer-council`; description says it runs whenever the agent is about to write or change code in a repository, names the ten-line exit, and says it is not for research questions (send those to research-council). Body: the seven rules above verbatim under "Rules that never change", a Procedure section that lists the stages (task, write with Thinker, guards, tier, review, fix, done, reply) each pointing at the step that fills it, and the same Runtime paragraph as research-council (COUNCIL_ROOT resolution, `harness.py context`). Workflow gains `python3 scripts/validate_skill.py skills/code-writer-council`. README names the third skill in one line.
**Acceptance:** WHEN `python3 scripts/validate_skill.py skills/code-writer-council` runs THEN it SHALL print `OK`, and WHEN any of the seven rule sentences is removed THEN exactly one test SHALL fail.
**Verify:** `python3 -m unittest tests.test_code_council tests.test_ci -v` → pass; delete rule 1 → exactly one fail.
**Must not:** add scripts or agents; change `skills/research-council/`.

### S-37 — task.py: a frozen task record with the user's caps
**PR:** one.
**Depends on:** S-36.
**Files:** `scripts/task.py`, `scripts/budget.py`, `scripts/harness.py`, `skills/code-writer-council/references/task.md`, `tests/test_task.py`, `tests/test_budget.py`.
**Today:** `scripts/goal.py` requires competing hypotheses and success criteria (line 41), which a code task does not have; `scripts/budget.py` reads only goal.json.
**Change:** `task.py new --root <workspace> --from <json|->` writes `AGI_Research/code/<task_id>/task.json` with required fields: task_id (uuid4), request_text, repo_root, start_commit (git HEAD at creation, or "none" outside git), test_command, allowed_paths[] (globs, at least one), max_diff_lines (number above 0), expected_small (bool), allow_verifier_edits (bool, default absent means false), explain (bool), budget (same block as goal.py: minutes, max_actions, max_subagents, usd_estimate_cap, set_by "user"), created_at, frozen_sha256. Caps come from `<repo_root>/.code-council/config.json` when it exists, else from the input; a missing cap is exit 1 naming it, never a default. `task.py check` recomputes the hash. `budget.py check` accepts a run folder holding task.json instead of goal.json, same caps, same exit codes. task.md tells the Supervisor how to fill each field from the request, and to ask the user once per repository for the four caps and write config.json with the user's numbers.
**Acceptance:** WHEN the input lacks test_command or allowed_paths THEN `task.py new` SHALL exit 1 naming the field, and WHEN task.json is edited by hand THEN `budget.py check` SHALL exit 1 with `frozen_sha256 mismatch`.
**Verify:** `python3 -m unittest tests.test_task tests.test_budget -v` → pass; remove the missing-field check → the named test fails; remove the hash check in budget.py's task branch → one test fails.
**Must not:** define any default cap; change goal.py.

### S-38 — scope.py: the diff stays inside the task
**PR:** one.
**Depends on:** S-37.
**Files:** `scripts/scope.py`, `scripts/harness.py`, `tests/test_scope.py`, `skills/code-writer-council/references/tiers.md`.
**Today:** nothing compares the diff with the task.
**Change:** `scope.py check --run <run>` reads task.json, runs `git diff --numstat <start_commit>` and `git status --porcelain` in repo_root, and prints one line per violation: `outside: <path>` for a changed or new file matching no allowed_paths glob; `over: <n>/<max_diff_lines> lines`; `verifier-edit: <path>: <reason>` when a test file (`tests/`, `test_*`, `*_test.*`), CI config (`.github/`), or a file named in test_command has a removed non-blank non-comment line, or an added line containing a skip or expected-failure marker, unless allow_verifier_edits is true. Prints `tier: 1|2|3` and `lines: <n>` on exit 0. Exit 2 on any violation, 1 on bad input. tiers.md holds the tier table from this spec and the drop order.
**Acceptance:** WHEN a changed file matches no allowed_paths glob THEN scope.py SHALL exit 2 printing `outside:` with the path, and WHEN a line starting with `def test_` is removed from a test file with allow_verifier_edits absent THEN it SHALL exit 2 printing `verifier-edit:`.
**Verify:** `python3 -m unittest tests.test_scope -v` → pass (fixtures build a temporary git repo); remove the verifier-edit rule → exactly the verifier tests fail.
**Must not:** modify the working tree; call any model.

### S-39 — deps.py: no new dependency without a registry record
**PR:** one.
**Depends on:** S-37.
**Files:** `scripts/deps.py`, `scripts/harness.py`, `tests/test_deps.py`.
**Today:** a hallucinated package name reaches `pip install` unchecked (C-5, C-26).
**Change:** `deps.py check --run <run>` reads the diff's added lines and collects dependency names from Python `import x` / `from x import`, from lines added to requirements*.txt and pyproject dependency arrays, and from `dependencies` in package.json. A name is resolved when it is in `sys.stdlib_module_names`, or `importlib.util.find_spec` finds it, or it appears in the repository's requirements, pyproject, package.json or lock files at start_commit, or evidence.jsonl in the run holds a `web` record whose source_uri is a registry URL (pypi.org/project/<name> or npmjs.com/package/<name>) for that exact name. Otherwise prints `unresolved: <name>` and exits 2. Offline: the script fetches nothing; the Supervisor fetches the registry page and records it with evidence.py.
**Acceptance:** WHEN the diff adds `import requests` in a repository whose files never name requests and the run has no registry record THEN deps.py SHALL exit 2 printing `unresolved: requests`, and WHEN an evidence record with source_uri `https://pypi.org/project/requests/` exists THEN it SHALL exit 0.
**Verify:** `python3 -m unittest tests.test_deps -v` → pass; remove the evidence lookup → the registry test fails.
**Must not:** make a network call; install anything.

### S-40 — done.py: the script says done, the model copies it
**PR:** one.
**Depends on:** S-38, S-39.
**Files:** `scripts/done.py`, `scripts/harness.py`, `skills/code-writer-council/references/done.md`, `tests/test_done.py`.
**Today:** "done" is a sentence the model writes (C-2, C-3).
**Change:** `done.py check --run <run>` does, in order: `budget.py check` (exit 2 stops here); `scope.py check`; `deps.py check`; runs task.test_command in repo_root with a timeout of the remaining minutes, records a `command` evidence record (source_uri = the command, locator = exit code and duration, excerpt = last 2000 characters of output, access_scope private) and an `exec` journal line; reads every review-<n>.json for `blocking: true` findings and requires a line in resolutions.jsonl per finding id with `{"finding": id, "how": "fixed", "diff_sha": <sha256 of git diff at resolution>}` or `{"how": "waived", "user_words": <string>}`; reads thinker.json and requires each test id to appear in the diff (its declared test name) or a waiver line. Prints `DONE <sha256 of current git diff>` and exits 0 only when all pass; otherwise `NOT DONE` and one reason per line, exit 2. done.md tells the Supervisor: the reply quotes the DONE line verbatim, and a NOT DONE reply lists the reasons and what happens next.
**Acceptance:** WHEN the test command exits non-zero THEN done.py SHALL print `NOT DONE` with `tests: exit <code>` and exit 2, and WHEN a blocking finding has no resolution line THEN it SHALL print `unresolved finding: <id>` and exit 2.
**Verify:** `python3 -m unittest tests.test_done -v` → pass (fixture test command is a python one-liner); remove the resolution check → exactly one test fails.
**Must not:** edit any file in repo_root; print DONE on any path that skipped the test run.

### S-41 — Reviewer role and tiers
**PR:** one.
**Depends on:** S-40.
**Files:** `agents/code-reviewer.md`, `scripts/fence.py`, `tests/test_agents.py`, `tests/test_fence.py`, `tests/test_code_council.py`, `skills/code-writer-council/SKILL.md` (Procedure review stage).
**Today:** no reviewer; `scripts/fence.py` ALLOWED (line 30) lists four roles.
**Change:** code-reviewer.md: tools Read, Grep, Glob; input is the run path, the diff (`git diff <start_commit>` saved by the Supervisor as `diff.patch` in the run folder) and one lens name; the lens fixes what it looks for (correctness+security: wrong logic, unhandled input, injection, secrets, unsafe file or shell use; scope+erosion: lines the request did not need, duplication, verbosity, weakened tests); replies with one JSON object `{"findings":[{"id":"R-1","file":...,"line":...,"severity":"blocking|advisory","kind":...,"text":...,"fix":...}]}`; "AGI-class model" preamble as the other roles. fence.py ALLOWED gains `code-reviewer: set()` and `code-thinker: set()`. SKILL.md review stage: snapshot fence, spawn one Reviewer per tier row, in parallel for tier 3 (one Agent call each in the same turn), check fence, save each reply as review-<n>.json, then the Writer fixes or the user waives, per rule 7.
**Acceptance:** WHEN code-reviewer.md lists Write or Bash in tools THEN exactly one test SHALL fail, and WHEN a Reviewer spawn creates any file in the run folder THEN `fence.py check --role code-reviewer` SHALL exit 2.
**Verify:** `python3 -m unittest tests.test_agents tests.test_fence tests.test_code_council -v` → pass; add Write to the tools line → one fail.
**Must not:** give any role Bash; let the model save findings anywhere but review-<n>.json.

### S-42 — Thinker role: tests drafted in parallel with the write
**PR:** one.
**Depends on:** S-41.
**Files:** `agents/code-thinker.md`, `tests/test_agents.py`, `tests/test_code_council.py`, `skills/code-writer-council/SKILL.md` (Procedure write stage).
**Today:** tests are written by the same context that wrote the code, after it (C-25).
**Change:** code-thinker.md: tools Read, Grep, Glob; input is the run path and task.json; reads the request and the current tree at start_commit; replies with `{"tests":[{"id":"T-1","name":"test_...","file":"tests/...","code":"...","would_fail_because":"..."}]}`, each test targeting one way the obvious implementation goes wrong (boundary, empty input, error path, concurrency, the thing the request did not say). SKILL.md write stage: when expected_small is false, spawn the Thinker in the same turn the Supervisor starts editing; when its reply arrives, the Supervisor adds each test to the repository's suite, runs it, and makes it pass or records a waiver with the user's words; when a task expected small ends over ten lines, spawn the Thinker after the write and journal a note `misestimate`.
**Acceptance:** WHEN code-thinker.md lists Write, Edit or Bash THEN exactly one test SHALL fail, and WHEN SKILL.md's write stage no longer says the Thinker is spawned in the same turn as the first edit THEN exactly one test SHALL fail.
**Verify:** `python3 -m unittest tests.test_agents tests.test_code_council -v` → pass; break each guard → one named fail each.
**Must not:** let the Thinker write into the repository; skip the waiver rule.

### S-43 — Procedure, learning mode and the reply
**PR:** one.
**Depends on:** S-42.
**Files:** `skills/code-writer-council/SKILL.md`, `tests/test_code_council.py`.
**Today:** Procedure section is a list of stage names pointing at steps.
**Change:** full Procedure: 1 task (task.py new; ask for caps once per repo), 2 write with Thinker in parallel, 3 guards (scope, deps; over the line cap → propose a split into tasks, user picks, each with its own done.py), 4 tier from scope.py output, 5 review (parallel per tier), 6 fix or waive, 7 done.py, 8 reply. Reply format: the DONE or NOT DONE line verbatim; then, when task.explain is true, one entry per changed file with what changed, why, and which test proves it, in plain English; budget line from budget.py. Ordering test anchored on `Spawn code-thinker`, `scope.py check`, `Spawn code-reviewer`, `done.py check` in that order.
**Acceptance:** WHEN the stages are reordered so that `done.py check` precedes `Spawn code-reviewer` THEN exactly one test SHALL fail, and WHEN the explain paragraph is removed THEN exactly one test SHALL fail.
**Verify:** `python3 -m unittest tests.test_code_council -v` → pass; `python3 scripts/validate_skill.py skills/code-writer-council` → `OK`.
**Must not:** exceed 500 body lines; add a step the model may skip silently.

### S-44 — End-to-end dry run on one real task in this repository
**PR:** one (docs only).
**Depends on:** S-43.
**Files:** `docs/runs/<date>-code-council-dry-run.md`, `docs/bugs.md`, this file (Status rows).
**Today:** the loop has never run.
**Change:** follow the skill on one bounded task in this repository with caps Abhishek gives (suggested at the grill: 20 minutes, 60 actions, 3 subagents, $0), write a de-identified run note (timeline, tier, findings count, DONE line, what did not work), log bugs, fill Status rows.
**Acceptance:** WHEN the PR is opened THEN the run note SHALL quote a `DONE <sha>` line whose sha matches the diff of the task's PR, and the run folder SHALL be absent from the diff.
**Verify:** `git diff main --stat` shows only docs files; suite passes.
**Must not:** reuse this run's caps as a default anywhere; merge the task's PR without the user's word.

## Status
| step | state | learned |
|---|---|---|
| S-36 | done 2026-09-17 (PR #42) | The step's file list missed `tests/test_who_runs_this.py`, which hard-counts entry points (agents plus skills); a third skill needs the count bumped, so every later step that adds an agent (S-41, S-42) must bump it too. One guard test per rule sentence, none counting the rules, is what makes "remove one rule, exactly one test fails" true. Suite 301 tests, five validators OK. |
| S-37 | done 2026-09-17 (PR #43) | The file list missed `scripts/journal.py`: its run-folder gate demanded goal.json, so a code run could not log and budget.py had nothing to count; gate now accepts task.json. `scripts/evidence.py` and `scripts/fence.py` have the same gate; S-39 and S-41 open them. When config.json exists the body must not carry a budget block, so there is one source of caps and a silent override is impossible. Suite 330 tests. |
| S-38 | done 2026-09-21 (PR #44) | Untracked files are invisible to `git diff`, so the guard reads `git status --porcelain --untracked-files=all` too and counts a new file's lines as added; done.py (S-40) must remember the same when it hashes the diff, or a new file escapes the DONE sha. The run folder itself is untracked in a workspace that does not ignore AGI_Research, so paths under `AGI_Research/` are excluded from scope. `fnmatch` lets `*` cross `/`, so allowed_paths globs get their own translator. Suite 351 tests. |
| S-39 | done 2026-09-21 (PR #45) | Local modules are not in the spec's four ways to resolve a name, yet `import task` inside this very repository would print `unresolved: task`; a name that matches a module or folder in the checkout now resolves, and the reply says so. The file list missed `scripts/evidence.py` (gate opened to task.json, as S-37 predicted) and a reference doc; `references/deps.md` tells the Supervisor to fetch the page itself and never guess a nearby name. "Installed" means found by the interpreter running the check, so the Supervisor runs deps.py with the venv's python. An import name that differs from its distribution name (`yaml` from PyYAML) has no registry page of its own and resolves only once installed. Manifests are diffed as whole files (names now minus names at start_commit), which makes a version bump a non-event and keeps an edited manifest from resolving its own import. Suite 390 tests. |
