# Triage — is this problem big enough?

Do this before anything else. Small problems get a one-line refusal, not a research run.

## Answer six questions from the request text alone

Answer each `true` or `false`. Do not read the workspace yet. Do not guess generously.

| key | question | true when |
|---|---|---|
| q1 | More than one credible explanation? | You can name two different causes a careful engineer would take seriously. |
| q2 | Outcome cannot be verified by one command or one test? | No single command, test, or lookup settles it. |
| q3 | Affects more than one file, service, or user? | The fix or answer touches more than one place, or more than one person depends on it. |
| q4 | User asked for research explicitly? | Words like research, investigate, find out why, compare, which one, what's the best way. |
| q5 | A wrong answer costs money, data, or a client? | Payments, deletions, client-facing systems, provider spend. |
| q6 | Does each step need the result of the step before? | The work is a chain: you cannot know what to check second until the first check is back, as in a debugging trail or a migration plan. False when the questions can be looked into side by side. |

## Rule
- q4 true → big.
- Otherwise big if at least two of q1, q2, q3, q5 are true.
- Else small.
- q6 never changes the size. For a big problem it picks the path: q6 true → `"path": "single"`, q6 false → `"path": "council"`.

## The single path
Multi-agent setups lost 39-70% on sequential planning tasks and gained on parallel ones in a
260-configuration study, and several compute-matched studies find one agent equal or better
(docs/research-upgrade-2026-09-25.md, section 4). So on the single path you are the only one
who reasons: run goal capture, budget and journal, evidence and claims, and the report
yourself, and skip the council roles, ranking and curiosity steps. You may still send workers
out to fetch sources in parallel; what they bring back is evidence, and the judgement stays
with you. Tell the user in one line that triage chose the single path and why.

## Run
```
printf '{"q1":true,"q2":true,"q3":false,"q4":false,"q5":false,"q6":false}' | python3 scripts/triage.py --answers -
```
Exit 0 = big, continue to goal capture on the printed `path`. Exit 3 = small: tell the user in one line which signals were missing and stop. Exit 1 = you passed bad JSON; fix it.

## Say to the user when small
"This looks like a one-step task (no competing explanations, verifiable by one test). research-council is for problems with unknowns. Handling it directly."
