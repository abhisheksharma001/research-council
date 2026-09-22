# Done is a printed line

A model's "done" is a sentence it believes (research run 2026-09-17, C-2 and C-3). Rule 1
says the word is printed by `scripts/done.py` after it ran the tests, and the reply copies
it. Nothing else in the reply may say the task is done.

n8n analogy: the last node is an IF on the test runner's exit code, and the Slack message
quotes that node's output. Nobody types "all tests pass" into the message by hand.

## The command
```bash
python3 scripts/done.py check --run AGI_Research/code/<task_id>
```
Run it with the interpreter the test command uses (the workspace venv's python when there is
one), from anywhere; it runs the test command in repo_root itself.

Exit 0 prints one line, `DONE <sha256>`. Exit 2 prints `NOT DONE` and one reason per line.
Exit 1 is bad input: a tampered task.json, no git checkout, a review, thinker or resolutions
file that does not parse, one finding id used by two review files. The three files are read
before the test command runs, so a bad file costs no test run and no metered action.

What it does, in order, and stops at the first stage that fails:

1. Budget meter (`budget.py`). An exceeded cap ends the task; nothing else runs.
2. Scope guard, dependency guard, and an empty-diff test. All three report together.
3. review-<n>.json, thinker.json and resolutions.jsonl are read. A file that does not parse
   stops the check here, before anything is spent.
4. The frozen `test_command`, in repo_root, through the shell, with the minutes left on the
   cap as its timeout. The run is written down as a `command` evidence record (exit code,
   duration, the last 2000 characters of output) and an `exec` journal line, so it costs one
   action. A run that writes files into the working tree changes the diff and is not done.
5. Findings and Thinker tests, against resolutions.jsonl.

The sha is sha256 over `git diff --binary <start_commit>` plus the bytes of every untracked
file outside `AGI_Research/`. A new file is part of what is certified; the state folder is
never. Any later edit gives a new sha, so the DONE line belongs to exactly one diff.

## Reasons and what happens next
| line | what the Supervisor does |
|---|---|
| `<file> does not parse` / `finding <n> needs an id and a severity ...` (exit 1, on stderr, before the tests run) | fix the file and run check again; no test run was spent |
| `budget: exceeded <cap> (<spent>/<cap>)` | stop; report the meter line from budget.py and what was not finished |
| `outside:`, `over:`, `verifier-edit:` | the scope guard's lines; `references/tiers.md` says what each means |
| `unresolved dependency: <name>` | the dependency guard's line; `references/deps.md` says how to close it |
| `diff: empty (...)` | nothing changed since start_commit; say so, never claim a change |
| `tests: not run (minutes cap <m> reached)` | the cap is spent; stop and report |
| `tests: exit <code>` | read the excerpt in evidence.jsonl, fix the code (never the test), run again |
| `tests: timed out after <n>s (...)` | the suite did not finish inside the minutes left; stop and report |
| `tests: the run changed the diff (...)` | the tests write into the tree (`__pycache__`, coverage files, fixtures); the workspace must ignore them, ask the user |
| `review: tier <t> diff has no review-<n>.json` | a tier 2 or 3 diff was not reviewed; run the review stage |
| `unresolved finding: <id>` | fix it and record the fix, or record the user's waiver (below) |
| `thinker: no thinker.json for a tier <t> diff` | the caps allow the Thinker and it did not run; run it |
| `missing test: <id> <name>` | add the Thinker's test to the suite under that name, in a verifier file, or record the user's waiver |

## Closing a finding or a Thinker test
```bash
python3 scripts/done.py resolve --run AGI_Research/code/<task_id> --finding R-1 --fixed
python3 scripts/done.py resolve --run AGI_Research/code/<task_id> --finding R-1 --waived "<the user's exact words>"
python3 scripts/done.py resolve --run AGI_Research/code/<task_id> --test T-1 --waived "<the user's exact words>"
```
`--fixed` is recorded after the fix is in the tree: the script computes the diff sha at that
moment and writes `{"finding": "R-1", "how": "fixed", "diff_sha": "<sha>"}` itself. Never
type a sha. `--waived` takes the user's words as written in the conversation, quoted, not a
summary; an empty string is refused (rule 7). A Thinker test is never "fixed": its declared
name is defined in the diff, or the user waived it. Defined means a non-comment added line of a
verifier file (a `tests` folder, `test_*`, `*_test.*`, or the path in `test_command`) holds the
name followed by `(`. A comment, a docstring or a new file that only mentions the name does not
count, so the test has to exist. An id that is in no review file or thinker.json
is refused, so a typo cannot close anything.

Only a finding with `"severity": "blocking"` needs a line; advisory findings are reported in
the reply and left to the user. A "fixed" line does not re-run the review: when the fix is
more than the finding asked for, run the Reviewer again on the new diff.

## The reply
- Done: quote the `DONE <sha>` line verbatim as the first line. Then the budget line from
  `budget.py check`, then the explanation per changed file when task.json has `explain: true`.
- Not done: quote `NOT DONE` and every reason line verbatim, then what happens next in one
  sentence per reason, from the table above. Never rephrase a reason into "almost done".
- Never write the word DONE in a reply that has no printed line behind it.
