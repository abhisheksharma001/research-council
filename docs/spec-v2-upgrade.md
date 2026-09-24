# Spec v2: upgrades from the 2026-09-25 self-research

Source: `docs/research-upgrade-2026-09-25.md` (section numbers below point there). One step is one
PR, branch `s<n>-<slug>`, squash-merged, each guard with a test seen to fail without it.
Invariants in `CLAUDE.md` are unchanged by every step marked "no invariant change"; the others
need a decision-log entry in `docs/decisions.md` first.

## Today
Hypotheses carry a predicted result but not what would refute them. Nothing makes a run look for
evidence against its favourite. Ranking judges each pair once in one order. The report mixes
observed and inferred claims under one heading. The council runs whenever triage says big, with
no single-agent baseline. Human corrections are not captured. Nobody has measured whether a run
beats a plain agent.

## Instead
Every hypothesis names its refuting observation; every open hypothesis gets at least one recorded
disconfirmation search before it can be Chosen; each pair is judged in both orders and a split
verdict is a draw; the report separates observed from inferred and keeps the strongest dissent;
user corrections become rule candidates a human merges; and a small eval set compares a run with
a plain agent at the same budget.

## Steps

| Step | What | Why (section) | Invariant change | Status |
|---|---|---|---|---|
| S-73 | This research, the merged reading, this spec, and the short prompt `prompts/short-council.md` | all | no | this PR |
| S-74 | Hypothesis gains required `refuting_observation`; goal.py and council.py validators reject a hypothesis without it; generation.md asks for it | 1 | no | next |
| S-75 | evidence.py gains optional `stance` (supports, contradicts, neutral) and `hypothesis_ids`; report.py will not name a hypothesis Chosen unless its run holds one evidence record with stance contradicts or a journal note of kind disconfirm naming it; FINDINGS.md prints "never challenged" otherwise | 2 | no | planned |
| S-76 | references/evidence.md: one lexical negation query per open hypothesis, logged as a disconfirm note | 2 | no | planned |
| S-77 | rank.py pair emits the same pair in both orders; record needs both verdicts; a split is recorded as draw and counted in a new flip rate line of rank.py table | 3 | no | planned |
| S-78 | rank.py table adds a Bradley-Terry column fitted over comparisons.jsonl beside Elo; report uses neither for findings (unchanged) | 3 | no | planned |
| S-79 | report.py splits "What we found" into Observed and Inferred by `claim_type`, and adds "Strongest dissent": the best-rated rival within 16 points plus the top unresolved blocking objection | 4, 5 | no | planned |
| S-80 | Excerpt support check: claims.py refuses a claim whose statement contains a quoted span not found in any cited excerpt; optional local NLI adapter reports but never clears | 5 | no | planned |
| S-81 | triage.py prints a single-agent path for contested-but-sequential problems; council.md says evidence gathering may fan out, judgement stays single; Meta-review records a same-budget single-agent answer to compare | 4 | no | planned |
| S-82 | Worker coverage gate: council.md and the short prompt require a per-question source quota and re-dispatch of early finishers before synthesis | 9 | no | planned |
| S-83 | lessons.py: a user correction becomes a rule candidate (lesson id, the correction verbatim, the run, provenance and lineage); only a human-typed approve moves it into a retained task contract; failures and successes are separate files | 6 | yes: new human write path to the library via promote.py | needs decision |
| S-84 | evals/: 20 golden tasks from past runs with known answers, two planted-false-source traps, one should-change-its-mind case; paired A/B against a plain agent at the same budget, 3 runs each, binary rubric items | 7 | no | needs caps from Abhishek |
| S-85 | Sandbox adapter design only (no code): network-off by default, no path to its own scorer, credentials by proxy | 8 | yes: invariant 8 wording | needs decision |

Deliberately not planned: cross-model-family routing (host capability, not ours; section 4 says
it is second order), verbalized-sampling generation (measured on creative writing only), and any
fine-tuning.

## Acceptance
WHEN S-74 to S-82 are merged THE SYSTEM SHALL refuse to name a Chosen hypothesis that was never
checked against contradicting evidence, record ranking flips, and print observed and inferred
findings apart. Whether this finds more true answers is not claimed until S-84 has run.
