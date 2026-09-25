# Ranking tournament (rank.py)

Elo is a rating that moves after every head-to-head result: beat a stronger opponent, gain
more; lose to a weaker one, lose more. Here it orders which hypothesis gets investigated
next. It is not a verdict. A rating of 1400 with no evidence is still unverified.

## Files in the run folder
- `hypotheses.json` — Generation's file. `rank.py` adds `elo` (start 1200) and
  `comparisons` (count) to each entry the first time it reads them and updates them on
  every `record`. Nothing else in the file is touched.
- `pairs.jsonl` — one line per issued order: `pair_id`, which id is A and which is B in
  order 1, `order` (1 or 2), seed. Only the Supervisor and the script read it. Never paste it
  into a Ranking prompt.
- `verdicts.jsonl` — the order-1 verdict of each pair, held until order 2 is judged.
- `comparisons.jsonl` — one line per completed pair with both ids, winner, `split`, both
  `verdicts`, both judgments, ratings before and after. Meta-review reads this.

## Loop, one pair at a time, judged in both orders
A judge tends to favour whichever side it reads first, so every pair is judged twice: once
as issued (order 1) and once with A and B swapped (order 2), each by a separate Ranking
spawn that never sees the other verdict. Two spawns per pair means ranking costs twice the
subagent launches it used to; budget for it.
```bash
python3 scripts/rank.py pair --run <run> --seed <n>       # blinded JSON: pair_id, order 1, A, B
# spawn Ranking with that JSON in the prompt (council.md: budget check before, journal after)
python3 scripts/rank.py record --run <run> --pair P-3 --winner A --judgment "<its judgment text>"
# P-3 order 1 recorded; run pair for order 2
python3 scripts/rank.py pair --run <run> --seed <n>       # same P-3, order 2, A and B swapped
# spawn a fresh Ranking worker with that JSON
python3 scripts/rank.py record --run <run> --pair P-3 --winner B --judgment "<its judgment text>"
# P-3 A: H2 1208, H1 1192
```
Each `--winner` is the letter the worker saw. If both verdicts name the same hypothesis,
that is the result. If they disagree (A then A, or a win then a draw), the pair is recorded
as a draw with `split: true`: the ranking could not tell them apart once position was taken
away. Only the completed pair moves ratings.
`pair` refuses with exit 1 when fewer than two hypotheses are `open`. It picks the
hypothesis with the fewest comparisons (ties: highest rating), then an opponent it has not
been drawn against, preferring one that shares opponents (so cycles can show), then the
highest rating. Use a fresh seed per call; the seed only shuffles which side is A.

`pair` always issues a waiting order 2 before choosing a new pair. A pair that has been
issued and not yet recorded counts as drawn, so the next `pair` picks a
different matchup where one exists and refuses with exit 1 where none does, naming the
outstanding pair id. That is what "one pair at a time" means in practice: judging the same
two hypotheses twice would feed one matchup into Elo twice. A matchup whose result is already
in `comparisons.jsonl` may be drawn again — that is a rematch, and both results count.

`record` refuses an unknown pair, a pair already recorded, an order-2 verdict before order 2
is issued, and an empty judgment, and writes nothing on refusal. Scores: win 1, draw 0.5, loss 0; K = 16.

The winner is read case-insensitively with surrounding punctuation ignored, so a Ranking reply
saying `a` or `Draw.` is recorded rather than discarded, and `comparisons.jsonl` always stores
`A`, `B` or `draw`. Anything that names none of the three is still refused with nothing written.

## Reading the result
```bash
python3 scripts/rank.py table  --run <run>    # ratings, highest first, with comparison counts,
                                              # then "flip rate: 1 of 4 pairs split (25%)"
python3 scripts/rank.py cycles --run <run>    # X > Y > Z > X triples; draws ignored
```
A high flip rate means the verdicts follow position more than evidence; say so before
leaning on the table. Pairs recorded before S-77 had one verdict and are not counted.
A cycle means the judgments disagree with each other; open a spark on the shared
measurement (S-8) rather than trusting the table. Two candidates within 16 points are a
tie for scheduling purposes (curiosity.md, S-8).

## Stopping a hypothesis
```bash
python3 scripts/rank.py stop --run <run> --hyp H1 --reason O-11
```
Run once per id in Meta-review's `stop: ...` list, reason = the objection id it cites.
Sets `status: stopped` and `stopped_reason`; refuses an unknown id, a hypothesis that is
not `open`, or an empty reason, and writes nothing on refusal. Only the Supervisor runs
it: no council role has Bash. `pair` never draws a stopped hypothesis; `table` shows it.
Ratings stay as they were.

## Never
- Never edit `elo` or `comparisons` by hand or in a prompt.
- Never let a rating decide what goes in FINDINGS.md; only evidence-backed claims do.
- Never show a Ranking spawn an id, a rating, a parent, an author, or `pairs.jsonl`.
