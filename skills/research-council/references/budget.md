# Budget and journal

The budget is the user's four numbers in `goal.json`. Nothing in this repo has a default
for any of them, and no script can raise one. Think of `budget.py` as a meter on the
pipeline: every node logs what it did, and the meter refuses to let the run continue once a
cap is passed.

## Before starting
Ask the user for all four numbers and write them into the goal (S-3):

| cap | meaning |
|---|---|
| `minutes` | wall-clock minutes since `created_at` |
| `max_actions` | journal lines of kind fetch, read, write, subagent, exec (`note` does not count) |
| `max_subagents` | journal lines of kind `subagent` |
| `usd_estimate_cap` | sum of `cost_usd`; `null` counts as 0 and is reported as `unmetered: N` |

If the user cannot give a number, stop and say so. Do not guess one.

## During the run
Log every action right after it happens:
```bash
python3 scripts/journal.py add --run AGI_Research/runs/<goal_id> --kind fetch --cost_usd null --detail "GET https://example.org/status"
python3 scripts/journal.py add --run AGI_Research/runs/<goal_id> --kind subagent --cost_usd 0.12 --detail "reflection on H1"
```
Use `--cost_usd null` when the cost is unknown; never invent a number. Caps and metered
costs must be finite, representable numbers, and costs cannot be negative. NaN, infinity,
booleans, and missing cost fields are invalid, not free work. The CLI, append API, and journal
reader reject invalid costs; a legacy bad entry or overflowed total stops budget checking
with exit 1. Correct the record with the user rather than substituting zero or raising a cap.

Run the check **before every subagent spawn and after every ten actions**:
```bash
python3 scripts/budget.py check --run AGI_Research/runs/<goal_id>
# spent: 12/60 min, 30/200 actions, 2/4 subagents, ~$0.40/$5 (unmetered: 3)
```
- exit 0: continue.
- exit 2: a cap is exceeded; stderr names it. Stop all work, report the line to the user,
  and finish with what exists. The user may start a new run with a bigger budget; a running
  goal cannot be raised (`goal.py revise` refuses it).
- exit 1: goal.json missing, tampered, or has no budget. Fix with the user; do not proceed.
