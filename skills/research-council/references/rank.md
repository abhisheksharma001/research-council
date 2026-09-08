# Ranking tournament (rank.py)

Elo is a rating that moves after every head-to-head result: beat a stronger opponent, gain
more; lose to a weaker one, lose more. Here it orders which hypothesis gets investigated
next. It is not a verdict. A rating of 1400 with no evidence is still unverified.

## Files in the run folder
- `hypotheses.json` — Generation's file. `rank.py` adds `elo` (start 1200) and
  `comparisons` (count) to each entry the first time it reads them and updates them on
  every `record`. Nothing else in the file is touched.
- `pairs.jsonl` — one line per issued pair: `pair_id`, which id is A and which is B, seed.
  Only the Supervisor and the script read it. Never paste it into a Ranking prompt.
- `comparisons.jsonl` — one line per recorded result with both ids, winner, judgment,
  ratings before and after. Meta-review reads this.

## Loop, one pair at a time
```bash
python3 scripts/rank.py pair --run <run> --seed <n>       # prints blinded JSON: pair_id, A, B
# spawn Ranking with that JSON in the prompt (council.md: budget check before, journal after)
python3 scripts/rank.py record --run <run> --pair P-3 --winner A --judgment "<its judgment text>"
```
`pair` refuses with exit 1 when fewer than two hypotheses are `open`. It picks the
hypothesis with the fewest comparisons (ties: highest rating), then an opponent it has not
met, preferring one that shares opponents (so cycles can show), then the highest rating.
Use a fresh seed per call; the seed only shuffles which side is A.

`record` refuses an unknown pair, a pair already recorded, and an empty judgment, and
writes nothing on refusal. Scores: win 1, draw 0.5, loss 0; K = 16.

## Reading the result
```bash
python3 scripts/rank.py table  --run <run>    # ratings, highest first, with comparison counts
python3 scripts/rank.py cycles --run <run>    # X > Y > Z > X triples; draws ignored
```
A cycle means the judgments disagree with each other; open a spark on the shared
measurement (S-8) rather than trusting the table. Two candidates within 16 points are a
tie for scheduling purposes (curiosity.md, S-8).

## Never
- Never edit `elo` or `comparisons` by hand or in a prompt.
- Never let a rating decide what goes in FINDINGS.md; only evidence-backed claims do.
- Never show a Ranking spawn an id, a rating, a parent, an author, or `pairs.jsonl`.
