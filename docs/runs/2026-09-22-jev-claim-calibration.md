# Jev claim battery — first calibration (S-53, 2026-09-22)

**Verdict: below the bar, and too few cases to fit anything.** The `fitted` block in
`scripts/judge.py` stays None, gate mode stays refused, and every in-run decision stays `unsure`.
The numbers below give direction only. They do not certify the battery.

## What was sent, and who allowed it
- **Go:** Abhishek on 2026-09-22 ("spend the type safe (no worries on that)").
- **Terms (R-1):** read by Claude on 2026-09-22, not by Abhishek. The opt-in file
  .research-council/judge.json was therefore **not** created, so the in-run judge stays off here.
- **Sources:** cases from five personal research runs (no client workspace), plus 30 synthetic
  cases. Every run case passed the same egress guard the in-run judge uses.
- **Key:** loaded per command from `~/.zshrc`, never written to a file.
- **Model:** every response reported `model: jev-1.13.0`. `GET /v1/models` lists only
  `jev-latest` and `jev-preview`, yet the pinned id is still accepted.
- **Spend:** 218 calls and 202,173 input tokens, **$0.0085** at $0.042/M. The first pass was 115
  cases; the rewrite was 103 cases on the candidate wording.

## Cases (`judge.py cases`, final labels)
Five runs were read: 622aeb79, 80e03afb, e322c3a5, 65a47056 and 07faefbd.

| outcome | count |
|---|---|
| positive (observed, read by Reflection, no objection) | 27 |
| negative (provenance / scope / type objection) | 43 |
| accepted inferred (labels `inferred` only) | 3 |
| synthetic hard negatives | 30 |
| **written** | **103** |
| excluded: not read by Reflection | 33 |
| excluded: counterexample | 22 |
| excluded: egress phone | 22 |
| excluded: superseded | 16 |
| excluded: number rule answers in code | 14 |
| excluded: egress private | 7 |
| excluded: egress address | 3 |
| excluded: egress key | 1 |

**How "read by Reflection" was decided (R-3):** in four runs the fence snapshot's sha matched a
line-prefix of claims.jsonl. Run 622aeb79 has no fence folder, so it fell back to "ids at or below
the highest objected id". Seen per run: 80e03afb 25, e322c3a5 21, 65a47056 87, 07faefbd 7 (fence);
622aeb79 18 (fallback).

## Held-out split (calibrate.py, eval fraction 0.3 by id hash)
- **Size:** 26 eval cases.
  - By class: 8 supported and 13 unsupported. The other 5 carry only an `inferred` label.
  - By source: 65a47056 9, synthetic 7, 80e03afb 5, 622aeb79 3, e322c3a5 2, 07faefbd 0.
  - Synthetic share: 7 of 26.
- **Claim level** (flag = supported below its threshold, or any other question at or above its
  own; single train-fitted thresholds): **TPR 0.85 on unsupported (11/13), TNR 0.62 on supported
  (5/8).** The bar is TPR ≥ 0.90 at TNR ≥ 0.85, with eval n ≥ 20 per class. It is missed on
  TNR, and neither class has n ≥ 20.
- **Unsure share:** 100% of in-run decisions today, because `fitted` is None. Under the three-way
  band, `supported` has no safe confident zone on train, so every case would still go to the
  fallback. Of all answers, 77 of 412 fell in the 0.35–0.65 middle.

| question | eval n | TP | FP | FN | TN | TPR | TNR | train band (low / high) |
|---|---|---|---|---|---|---|---|---|
| supported | 18 | 8 | 2 | 0 | 8 | 1.00 | 0.80 | none safe |
| contradicted | 13 | 5 | 0 | 0 | 8 | 1.00 | 1.00 | 0.55 / 0.55 |
| wider | 11 | 2 | 2 | 1 | 6 | 0.67 | 0.75 | 0.27 / 0.81 |
| inferred | 13 | 2 | 2 | 3 | 6 | 0.40 | 0.75 | 0.22 / 0.83 |

- **Synthetic hard negatives:** all 30 were flagged across both splits:
  - numbers in words: 8/8
  - wrong entity: 7/7
  - flipped polarity: 7/7
  - quoted instruction: 8/8

  The real misses come from Reflection's own labels, not from these textbook cases.

## What changed during the step
1. **Two labelling rules were wrong and were fixed before scoring.** The train-only misses packet
   showed the problems.
   - **counterexample:** agents/reflection.md lets it name any evidence record on file, and the
     case holds only the cited excerpts. So a counterexample claim is now excluded rather than
     labelled `contradicted`.
   - **inferred:** claims Reflection accepted as `inferred` or `predicted` had been labelled
     "not inferred". They are now labelled `inferred` only.

   The same answers were re-scored, with no new calls. First pass (115 cases): TPR 0.58 at TNR
   0.62. After the fix (103 cases): TPR 0.85 at TNR 0.62.
2. **One question rewrite was tried and not kept.** `wider` and `inferred` were reworded from the
   train misses only. `optimize_questions.py compare` accepted both on train loss, but both got
   one error worse on eval (`wider` 3 → 4, `inferred` 5 → 6), and `wider`'s log-loss rose from
   0.55 to 1.28. The tool itself flagged that as likely overfit, so the baseline wording stays.

## Who labelled
- **Real cases:** the Reflection role's objections, plus the fence prefix for what it read.
  Nobody hand-checked them. Some negatives are Reflection's judgement about the `scope` field
  rather than the excerpt.
- **Synthetic cases:** written by Claude, in `tests/fixtures/judge/synthetic-claims.jsonl`.

## Incumbent
Today nothing checks a claim at add time, so the Supervisor adds every one of these negatives
unchallenged, by construction. Even at this bar, Jev in shadow mode would have flagged 11 of 13
held-out unsupported claims one council round earlier. What stops a gate is the other number:
about 3 in 8 good claims would be flagged as well.

## What would settle it
- At least 20 supported eval cases, which means about 70 positives in total. That needs more
  Reflection-reviewed runs or a hand-labelled set.
- A fresh calibration on those cases, with the bar unchanged.
- The egress phone rule stopped 22 cases across five runs. Measuring that on the three runs
  outside this repository is the cheapest way to recover positives.
