# The judge: a second reading of a claim or a page, before the council sees it

`scripts/judge.py` asks a small closed-answer model (Jev, from TypeSafe AI) a few fixed
questions about a record you have just written, and prints one line. It is the only place in
this repository that talks to that model.

n8n analogy: one HTTP Request node behind a Switch, with a Skip branch that is today's path.
The thresholds live in a Set node, not in the HTTP node, and until somebody fills that Set
node in, every item takes the Skip branch. Nothing downstream changes.

## The two batteries

| battery | subject | what it asks | what it is for |
|---|---|---|---|
| `claim` | a claim id, `C-7` | four yes/no questions: do the excerpts say this, does one of them say the opposite, does the claim reach wider than they do, is it a conclusion rather than something written | Reflection already objects to a claim the excerpts do not support, but it runs one council round later. The judge reads the claim at the moment it is recorded, while the source is still open |
| `evidence` | an evidence id, `E-3` | who published the page (vendor, partner, independent, other), how much it says about the goal's unknowns (1 to 3), and whether the excerpt carries text addressed to an AI agent | source strength is prose you write into a claim's `limitations` by hand, and the 2026-09-21 self-run's meta-review found six records where it was wrong. The judge gives a second opinion to compare against |

The evidence battery gates nothing and never will: it cannot drop a record, change a strength
or stop a fetch. Its answers are data you read beside your own.

The claim battery is also the optional meaning check behind the quote rule in
`references/evidence.md`: `claims.py` refuses a quote no cited excerpt contains, and the judge
asks the looser question of whether a paraphrase says what its excerpts say.

## What it never does

- A `yes` verifies nothing. A claim is verified by an evidence record, never by a probability
  (CLAUDE.md invariant 2).
- It never edits a claim, an evidence record, the goal, the budget or the library. The answer
  is written to `judge.jsonl` and nowhere else (invariant 3).
- No council role ever sees it. `judge.jsonl` is skipped by the fence, exactly as
  `journal.jsonl` is, so Reflection stays blind and still objects on its own reading.
- Nothing but a public record leaves the machine. One cited record whose `access_scope` is not
  `public` stops the call before any request body is built.
- A claim battery call sends the claim's statement, scope and type, and for each cited record its
  id, its locator and its excerpt. It does not send the source URL: no claim question asks who
  published the page, and a URL carries long numeric ids the phone guard cannot tell from a phone
  number. An evidence battery call does send the page's URL, because that is what `strength` asks
  about.

## Running it

```bash
python3 scripts/judge.py run --run AGI_Research/runs/<goal_id> --battery claim --id C-7
python3 scripts/judge.py run --run AGI_Research/runs/<goal_id> --battery evidence --id E-3
python3 scripts/judge.py questions --battery claim        # the questions, for calibration
```

Run the claim battery right after `scripts/claims.py add` prints `C-n recorded`, and the
evidence battery right after `scripts/evidence.py add` prints `E-n recorded`. Skip both
entirely when the run's goal forbids paid calls: no script can read that prose, so it is your
call.

The evidence battery needs four fields you write into .research-council/judge.json at goal
time, beside the three the opt-in file already carries:

```json
{"enabled_by": "<who>", "date": "<when>", "terms_read": true,
 "product": "the thing being researched", "vendor": "the company that makes it",
 "vendor_hosts": ["example.com"], "partner_hosts": ["reseller.example"]}
```

`product` is the only one the battery cannot run without. The two host lists are a shortcut,
not a requirement: a page on a listed host is answered from the list with no call at all.

## The one line it prints

| line | what happened | what to do |
|---|---|---|
| `judge: claim C-7 unsure` | the model answered; no calibrated thresholds exist yet, so no decision is claimed | nothing; carry on |
| `judge: claim C-7 no (rule: number 91.49 not in any excerpt)` | a number in the statement is in none of the cited excerpts. Decided in code, no call was made | fix the number or cite the excerpt that carries it |
| `judge: claim C-7 no` | the model's probabilities cross a calibrated threshold | fix the claim or its evidence, then record it again |
| `judge: claim C-7 yes` | the excerpts look like they support it | nothing. This is not verification |
| `judge: evidence E-3 vendor (rule: host)` | the page's host is on the opt-in file's own vendor or partner list. Decided in code, no call was made | nothing; it agrees with the list you wrote |
| `judge: evidence E-3 unsure` | the model answered; the answers are in `judge.jsonl` for you to read against your own `limitations` | nothing changes a record |
| `judge: claim C-7 skipped: <reason>` | nothing was sent and nothing was written | carry on; the reasons are below |

## Why it skipped

| reason | meaning |
|---|---|
| `not enabled` | the run folder is not `<root>/AGI_Research/runs/<id>`, or the workspace has no .research-council/judge.json naming who enabled it, when, and that the terms were read |
| `budget` | a cap is already exceeded, the dollar cap is 0, or one more action would pass the action cap |
| `no product` | the evidence battery only: the opt-in file names no product, and the questions are about a page relative to one |
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

There are none yet, and the evidence battery is never getting any. `fitted` is `None` in `scripts/judge.py`, so every answered decision is
`unsure` whatever the probabilities say. Thresholds arrive only from a calibration on labelled
cases, reported on a held-out split with its n. A probability is not a decision: answers jitter
by about ±0.02 between runs, so 0.5 is a knife edge, not a default.
