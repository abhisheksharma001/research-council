# The judge: a second reading of a claim, before the council sees it

`scripts/judge.py` asks a small closed-answer model (Jev, from TypeSafe AI) four yes/no
questions about a claim you have just recorded, and prints one line. It is the only place in
this repository that talks to that model.

n8n analogy: one HTTP Request node behind a Switch, with a Skip branch that is today's path.
The thresholds live in a Set node, not in the HTTP node, and until somebody fills that Set
node in, every item takes the Skip branch. Nothing downstream changes.

## What it is for

Reflection already objects to a claim the excerpts do not support, but Reflection runs one
council round later. The judge reads the same claim at the moment it is recorded, so the
Supervisor can fix the record while the source is still open.

## What it never does

- A `yes` verifies nothing. A claim is verified by an evidence record, never by a probability
  (CLAUDE.md invariant 2).
- It never edits a claim, an evidence record, the goal, the budget or the library. The answer
  is written to `judge.jsonl` and nowhere else (invariant 3).
- No council role ever sees it. `judge.jsonl` is skipped by the fence, exactly as
  `journal.jsonl` is, so Reflection stays blind and still objects on its own reading.
- Nothing but a public record leaves the machine. One cited record whose `access_scope` is not
  `public` stops the call before any request body is built.

## Running it

```bash
python3 scripts/judge.py run --run AGI_Research/runs/<goal_id> --battery claim --id C-7
python3 scripts/judge.py questions --battery claim        # the four questions, for calibration
```

Run it right after `scripts/claims.py add` prints `C-n recorded`. Skip it entirely when the
run's goal forbids paid calls: no script can read that prose, so it is your call.

## The one line it prints

| line | what happened | what to do |
|---|---|---|
| `judge: claim C-7 unsure` | the model answered; no calibrated thresholds exist yet, so no decision is claimed | nothing; carry on |
| `judge: claim C-7 no (rule: number 91.49 not in any excerpt)` | a number in the statement is in none of the cited excerpts. Decided in code, no call was made | fix the number or cite the excerpt that carries it |
| `judge: claim C-7 no` | the model's probabilities cross a calibrated threshold | fix the claim or its evidence, then record it again |
| `judge: claim C-7 yes` | the excerpts look like they support it | nothing. This is not verification |
| `judge: claim C-7 skipped: <reason>` | nothing was sent and nothing was written | carry on; the reasons are below |

## Why it skipped

| reason | meaning |
|---|---|
| `not enabled` | the run folder is not `<root>/AGI_Research/runs/<id>`, or the workspace has no `.research-council/judge.json` naming who enabled it, when, and that the terms were read |
| `budget` | a cap is already exceeded, the dollar cap is 0, or one more action would pass the action cap |
| `egress private E-3` | a cited record is not marked `public` |
| `egress address` / `egress phone` / `egress key` / `egress home path` | the assembled state matched a pattern that must not leave the machine |
| `size` | the state is over 60000 characters, well under the model's own limit |
| `no key` | `TYPESAFE_API_KEY` is not set in this shell |
| `adapter <error>` | the call failed. This is the outage rule: an outage is a skipped line and exit 0, never a stalled run |

Every one of those exits 0 and leaves the run folder byte-identical. With no opt-in file the
judge is a no-op, which is how this repository's own self-runs behave.

## Cost and metering

One call is about 600 input tokens, roughly $0.000025 at $0.042 per 1M input tokens (checked
2026-09-21). Every recorded decision writes one `judge` line to `journal.jsonl` carrying the
measured cost, written *before* the judge record, so a call that happened is never unlogged.
`budget.py` counts it as an action like any other.

## Thresholds

There are none yet. `fitted` is `None` in `scripts/judge.py`, so every answered decision is
`unsure` whatever the probabilities say. Thresholds arrive only from a calibration on labelled
cases, reported on a held-out split with its n. A probability is not a decision: answers jitter
by about ±0.02 between runs, so 0.5 is a knife edge, not a default.
