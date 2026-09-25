# Evals: does the council beat one plain agent at the same budget?

Nothing in this repository has measured that yet. `scripts/evals.py` runs the comparison;
the host runs the agents. Think of it as an n8n test harness: the same input item goes down two
branches, and a fixed checklist scores what comes out of each.

## The two arms
| arm | what the agent gets |
|---|---|
| `council` | the task's `request`, the workspace `next` printed, and the research-council skill |
| `plain` | the same `request` and workspace, no skill, told to investigate and answer |

Both use the same model and are told the same per-run share of dollars and minutes, which
`next` prints. The answer scored is the final message the arm gives the user, saved verbatim
to a file; nothing is edited before scoring.

## A task
A file such as evals/tasks/T-01.json (this one is an illustration, not a real task):
```json
{"id": "T-01", "kind": "golden",
 "request": "Why did the booking agent stop confirming slots on 8 Sep?",
 "known_answer": "the lookup tool was switched off in config revision r42",
 "source": "the run id and record the known answer was checked against",
 "files": {"notes/config-history.md": "r41 ... r42 lookup_tool: false ..."},
 "rubric": [{"id": "R1", "text": "names the config change", "match": "r42|config(uration)? (change|revision)"},
            {"id": "R2", "text": "does not blame the upstream API", "must_not_match": "upstream api (was|is) (down|failing)"}]}
```
`kind` is `golden` (a past run with a known answer), `trap` (a planted false source in `files`
that a careful answer must not repeat) or `mind_change` (evidence in `files` that overturns the
obvious first answer). A full set is 20 tasks with at least two traps and one mind change;
`python3 scripts/evals.py validate --complete` says whether the folder has it.

## A session
```bash
python3 scripts/evals.py start   --session first --usd 20 --minutes 180 --runs 3
python3 scripts/evals.py next    --session first      # one planned run, as JSON
# run that arm in the printed workspace, save its final message to answer.md
python3 scripts/evals.py record  --session first --task T-01 --arm plain --run 1 \
  --answer answer.md --cost_usd 0.31 --minutes 6
python3 scripts/evals.py summary --session first
```
The caps are the user's numbers for the whole session. `next` exits 2 once one is reached; a
run already done is still recorded. A partial session is reported as partial: it says nothing
about the tasks it did not reach.
