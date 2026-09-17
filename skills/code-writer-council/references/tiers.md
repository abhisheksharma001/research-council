# Tiers and the scope guard

The size of the diff picks how many fresh-context readers it gets. Lines are added plus
removed, measured by `scripts/scope.py` against the task's `start_commit`; the model never
estimates them.

n8n analogy: a Switch node on one number, with the number computed by a Code node, not typed
by hand.

## Tier table
| diff lines | Reviewers | Thinker | subagents |
|---|---|---|---|
| 0 to 10 | none | none | 0 |
| 11 to 100 | 1 (correctness + security) | yes | 2 |
| over 100 | 2 in parallel (A: correctness + security; B: scope + erosion) | yes | 3 |

Drop order when `max_subagents` in task.json is below the tier's count: Reviewer B first,
then the Thinker. The reply names what was dropped. Reviewer A is never dropped: a tier 2 or
3 diff with no reviewer is not done.

The Thinker starts with the write when task.json says `expected_small: false`. When a task
expected small ends over ten lines, the Thinker runs after the write and the journal gets a
`note` line saying `misestimate`.

## The scope guard
```bash
python3 scripts/scope.py check --run AGI_Research/code/<task_id>
```
Exit 0 prints `tier: 1|2|3` and `lines: <n>`; copy the tier from there. Exit 2 prints one
line per violation and no tier; exit 1 means bad input (tampered task.json, a workspace
that is not a git checkout).

| line | meaning | what the Supervisor does |
|---|---|---|
| `outside: <path>` | a changed or new file matches no `allowed_paths` glob | revert that file, or stop and tell the user the task needs that path: a new task with it listed (rule 2) |
| `over: <n>/<max> lines` | the diff passed `max_diff_lines` | propose a split into tasks, each with its own task.json and its own done.py run; the user picks |
| `verifier-edit: <path>: <reason>` | a test file, CI config or a file named in `test_command` lost a real line or gained a skip or expected-failure marker | undo it; when the user's task is to change those tests, that is a new task with `allow_verifier_edits: true` |

What counts as a verifier file: any path with a `tests` folder in it, a file named `test_*`
or `*_test.*`, anything under `.github/`, and any path that appears in `test_command`.
Blank and comment lines never count as a real line, so reformatting a docstring in a test
does not trip the guard. Markers checked on added lines, case-insensitive: `skip`, `xfail`,
`expectedFailure`, `xit(`, `xdescribe(`, `.only(`, `@Ignore`, `@Disabled`.

Globs in `allowed_paths`: `*` and `?` stay inside one folder level, `**` crosses levels,
and a pattern must match the whole path from the workspace root. `scripts/*.py` allows
`scripts/triage.py` but not `scripts/lib/util.py`; `scripts/**` allows both. Files under
`AGI_Research/` are the council's own state and are never part of the diff.

Nothing here edits the working tree. The guard runs before the tier is chosen, again after
every fix, and once more inside done.py.
