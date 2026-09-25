# Task record

The task is written once and frozen. Every later stage reads from it and none may rewrite
it: `scripts/task.py` has no revise command. If the test command or the allowed paths must
change, that is a new task with its own task.json (rule 2).

n8n analogy: the trigger node's fixed input. The scope guard, the reviewers and done.py all
read their limits from here, never from the conversation.

## Caps: ask once per repository
The four caps live in `<workspace>/.code-council/config.json`, written once with the user's
numbers. When that file exists, `task.py new` reads the caps from it and the task body must
not carry a `budget` block. When it does not exist, ask the user for all four numbers now,
write the file exactly as below with what they said, and then run `task.py new`. Never copy
numbers from a fixture, a memo, an earlier task, this file or the register; never write
`set_by: user` for a number the user did not say.

```json
{"budget": {"minutes": 0, "max_actions": 0, "max_subagents": 0, "usd_estimate_cap": 0, "set_by": "user"}}
```
(The zeros above are placeholders, not values: `task.py new` refuses a zero for anything but
`usd_estimate_cap`, and `usd_estimate_cap: 0` means the first metered cost stops the task.)

| cap | meaning |
|---|---|
| `minutes` | wall-clock minutes since `created_at` |
| `max_actions` | journal lines of kind fetch, read, write, subagent, exec, judge (`note` and `disconfirm` do not count) |
| `max_subagents` | journal lines of kind `subagent`; the tier table needs 0, 2 or 3 |
| `usd_estimate_cap` | sum of `cost_usd`; `null` counts as 0 and is reported as `unmetered: N` |

If the user cannot give a number, stop and say so. Do not guess one.

## Template
| field | what goes there |
|---|---|
| `request_text` | the user's request, verbatim |
| `test_command` | the one command that proves the change, runnable from the workspace root (for this repo: `python3 -m unittest discover -s tests`); done.py runs it itself |
| `allowed_paths` | at least one path or glob relative to the workspace root that the change may touch; the scope guard flags anything else. Tests the Thinker drafts count, so list their file too |
| `max_diff_lines` | added plus removed lines the diff may reach, a whole number above 0; over it the guard asks for a split |
| `expected_small` | `true` when the change should end at ten diff lines or fewer (no Thinker, no Reviewer); `false` starts the Thinker with the write |
| `allow_verifier_edits` | optional, default `false`; `true` only when the user said the task is to change or delete existing tests |
| `explain` | `true` for learning mode: the reply explains each changed file, why, and which test proves it |
| `budget` | the four caps plus `"set_by": "user"`, only when no config.json exists |

Fill `request_text` from the user's words, not a paraphrase. Pick `test_command` from the
repository's own test setup (its README, CI workflow or Makefile); if the repository has no
tests, say so and ask the user which command counts as proof; never write an empty one.

The script adds `task_id`, `repo_root`, `start_commit` (git HEAD, or `none` outside git),
`created_at` and `frozen_sha256`. The diff every later guard measures is against `start_commit`.

## Commands
```bash
python3 scripts/task.py new --root /absolute/workspace --from task.json   # prints the task.json path
python3 scripts/task.py check --run AGI_Research/code/<task_id>           # exit 1 if edited by hand
python3 scripts/budget.py check --run AGI_Research/code/<task_id>         # same meter as a research run
```
`new` exits 1 and names every missing or invalid field; a missing cap is named, never
defaulted. If it prints `warning: AGI_Research/ is not ignored`, the workspace is a git
checkout that would track the task folder: tell the user and add `AGI_Research/` to the
workspace `.gitignore` only with their go. The printed folder is the run folder for every
later stage: journal.py, budget.py and the guards all take it as `--run`.
