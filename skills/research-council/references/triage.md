# Triage — is this problem big enough?

Do this before anything else. Small problems get a one-line refusal, not a research run.

## Answer five questions from the request text alone

Answer each `true` or `false`. Do not read the workspace yet. Do not guess generously.

| key | question | true when |
|---|---|---|
| q1 | More than one credible explanation? | You can name two different causes a careful engineer would take seriously. |
| q2 | Outcome cannot be verified by one command or one test? | No single command, test, or lookup settles it. |
| q3 | Affects more than one file, service, or user? | The fix or answer touches more than one place, or more than one person depends on it. |
| q4 | User asked for research explicitly? | Words like research, investigate, find out why, compare, which one, what's the best way. |
| q5 | A wrong answer costs money, data, or a client? | Payments, deletions, client-facing systems, provider spend. |

## Rule
- q4 true → big.
- Otherwise big if at least two of q1, q2, q3, q5 are true.
- Else small.

## Run
```
printf '{"q1":true,"q2":true,"q3":false,"q4":false,"q5":false}' | python3 scripts/triage.py --answers -
```
Exit 0 = big, continue to goal capture. Exit 3 = small: tell the user in one line which signals were missing and stop. Exit 1 = you passed bad JSON; fix it.

## Say to the user when small
"This looks like a one-step task (no competing explanations, verifiable by one test). research-council is for problems with unknowns. Handling it directly."
