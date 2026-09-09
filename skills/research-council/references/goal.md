# Goal capture

The goal is written once, frozen, and changed only through `scripts/goal.py revise`.
Think of it as the trigger node's fixed input: every later step reads from it, and nothing
downstream may rewrite it.

## Before writing the goal
1. Ask the user for the four budget numbers (`minutes`, `max_actions`, `max_subagents`,
   `usd_estimate_cap`). The script has no defaults and will refuse a goal without them.
   `usd_estimate_cap` may be `0`: it means no paid call is allowed, and the first metered
   cost makes `scripts/budget.py check` exit 2. The other three must be above zero.
2. Ask for at least one success criterion in the user's words. If the user cannot give one,
   stop and say so. Never invent one. If the user has not given the numbers or the
   criterion in this session, stop and ask again. Never copy them from a fixture, a memo
   or an earlier run, and never write `set_by: user` for a value the user did not say.
3. Run `python3 scripts/retrieve.py --query "<request text>" --library library` before writing
   `competing_hypotheses`. Add `--scope private` only when the goal's scope allows private
   skills (client data). The score counts shared words, nothing more; a word that is all
   digits (a date, a count, an id) never counts, so `Sep 04 774 calls failed` searches on
   `calls failed sep` only. Similarity is not authority, so read each hit's counterexamples
   and boundary, and treat its status line as the only claim of validity. Copy the printed
   `snapshot:` line into `library_snapshot`, keeping only the skills the run will actually
   use (their contract ids come with them); write `null` when nothing is used.

## Template
Fill every field. Lists may be empty only where nothing is known; say so in `unknowns`.

| field | what goes there |
|---|---|
| `request_text` | the user's request, verbatim |
| `observations` | facts already seen, one per line, no interpretation |
| `suggested_explanations` | explanations the user or the request text already offered |
| `desired_outcome` | what a good answer looks like to the user |
| `scope` | what data and systems are in bounds |
| `unknowns` | what nobody knows yet; leave them as questions |
| `competing_hypotheses` | at least two; each has `id`, `statement`, `predicted_result`, `strongest_alternative` (the id of the rival it must beat) |
| `success_criteria` | at least one; each has `measurement`, `evaluator`, `environment`, `pass_condition` |
| `baseline` | what is believed today, before any work |
| `allowed_actions` | what the run may do |
| `prohibited_actions` | what it may never do (money, live systems, clients) |
| `budget` | the four numbers plus `"set_by": "user"` |
| `library_snapshot` | the `snapshot:` line from `scripts/retrieve.py` trimmed to the skills used, or `null` |

Example: `tests/fixtures/goal_booking.json`.

## Rules
- **An unknown stays unknown.** Do not turn an `unknowns` entry into an observation or a
  hypothesis without an evidence record. The goal records what is not known so the run can
  be judged on whether it found out.
- Every hypothesis must name a rival. A hypothesis with no `strongest_alternative` is a
  conclusion, not a hypothesis.
- `predicted_result` says what the evidence will look like if the hypothesis is true. If two
  hypotheses predict the same result, they are one hypothesis.

## Commands
```bash
python3 scripts/goal.py new --root . --from goal.json          # prints the goal.json path
python3 scripts/goal.py check --run AGI_Research/runs/<goal_id>  # exit 1 if edited by hand
python3 scripts/goal.py revise --run AGI_Research/runs/<goal_id> --from goal2.json --reason "..."
```
`new` exits 1 and names every missing or invalid field. `revise` keeps the previous revision
in `goal.history.jsonl` and refuses to raise any budget cap.
