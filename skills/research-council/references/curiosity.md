# Curiosity — when to open a spark

A spark is one unexpected observation tracked through the fire protocol
(`strategies/fire.md`). Open one in exactly two situations:

1. **Contradiction.** An observation contradicts a hypothesis's `predicted_result` in
   `hypotheses.json`. Example: H1 predicts tool calls carry error results, and the export
   shows the calls were never attempted.
2. **Tie.** Two hypotheses sit within 16 points of each other in `scripts/rank.py table`
   after each has been compared at least twice. The ranking cannot separate them, so the
   shared measurement is the observation to chase. Name both ids.

Do not open a spark for something merely interesting. Curiosity here is paid for a
prediction that got sharper (CLAUDE.md invariant 7), and only the two triggers above
produce one.

## Commands
```bash
python3 scripts/spark.py new     --run <run> --observation "..." --prediction_before "..." --hypotheses H1[,H2]
python3 scripts/spark.py advance --run <run> --spark SP-1 --to REPEAT
python3 scripts/spark.py trial   --run <run> --spark SP-1 --kind repeat --ok --detail "..."
python3 scripts/spark.py trial   --run <run> --spark SP-1 --kind vary --failed --condition "..." --detail "..." --evidence E-4
python3 scripts/spark.py advance --run <run> --spark SP-1 --to BOUNDARY --prediction_after "..."
python3 scripts/spark.py status  --run <run> [--spark SP-1]
```
Copy `prediction_before` from the hypothesis's `predicted_result` word for word. The
`prediction_after` is that same sentence plus the conditions you found; the script decides
whether that counts as progress, you do not.

After every `spark.py` call run `scripts/journal.py add --kind write`. A trial that used a
fetch or a command also gets its own journal line and, if a record was made, an
`evidence.py add` whose id goes on the trial.

## Reading status
`SP-1 VARY repeat 2 ok/0 failed, vary 1 ok/1 failed, combine 0, progress no`
means: in VARY, two good repeats, one variation broke it, boundary not yet written.
`spark.py status --spark SP-1` prints the full record including every trial.

## Refusals
- `need 2 repeats`: log more `repeat` trials before leaving REPEAT.
- `need 1 failed variation`: you have not seen it fail; keep varying.
- `a repeat trial needs REPEAT`: advance the spark first; the state names what you are doing.
- `sparks only move forward`: there is no undo. Open a new spark if the story changed.
- `prediction_after is written only when advancing to BOUNDARY`: the boundary is the one
  place a prediction changes.

## Never
- Never set `progress` by hand. The script writes it once, from the string test.
- Never open a spark on a claim, a rating, or an agent's opinion. Only on an observation.
- Never treat NOISE as an error. It goes into FINDINGS.md as something tried that did not repeat.
- Never let a spark promote anything. NAME hands a candidate to the gate (S-11); the gate decides.
