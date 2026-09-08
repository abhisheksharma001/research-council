# Fire protocol — curiosity strategy 1

The story: someone sees a spark, tries to make it happen again, changes one thing at a
time, learns where it works and where it does not, tries it with something else, and only
then gives it a name. Nothing is rewarded for being surprising. The only reward is a
prediction that got sharper.

A "spark" is one observation that contradicts what a hypothesis predicted. Each spark
moves through six states, always forward, tracked in `spark.json` by `scripts/spark.py`.
The script checks every requirement before it writes; a refusal changes nothing.

| State | Trigger | Action | Stop rule |
|---|---|---|---|
| SPARK | An observation contradicts a `predicted_result`, or two hypotheses tie in Elo within 16 points. | `spark.py new` with the observation and the prediction it broke. No reward. | Move to REPEAT at once. A spark left in SPARK is a spark nobody looked at. |
| REPEAT | Spark opened. | Reproduce under the same conditions, at least twice. Log each attempt as a `repeat` trial, ok or failed. | Two ok repeats: move to VARY. It did not repeat: mark NOISE and stop. Noise is a result, not a failure. |
| VARY | Two ok repeats. | Change one condition at a time. Log each attempt as a `vary` trial naming the condition; attach an evidence id when a record was made. | At least one variation fails: move to BOUNDARY. Nothing you change makes it fail: the boundary is unknown; keep varying or record that and stop. |
| BOUNDARY | Two ok repeats and one failed variation. | Write where it works and where it fails as one sentence: the old prediction plus its conditions. Pass it as `--prediction_after`. Record the same sentence as a claim with scope via `scripts/claims.py`. | `progress` is set by the script, only if the new sentence narrows the old one. Then move to COMBINE. |
| COMBINE | Boundary written. | Try composing with one existing library skill or one extra ingredient. Log the attempt as a `combine` trial. | One combine trial logged, ok or failed: move to NAME. |
| NAME | One combine trial. | Draft a skill candidate: what it applies to (the boundary) and where it fails (the failed variations). Hand it to the promotion gate; never promote it yourself. | Spark closed. |
| NOISE | A repeat failed while in REPEAT. | Nothing. It is written in `spark.json` and shows up under "what we tried that did not work". | Terminal. |

## What earns the reward

`progress` is true only when `prediction_after` still contains `prediction_before` and
adds a scope word (when, only, if, unless, under, between, above, below, after, before,
within, except, while, during, until, provided). That is the v1 string test for "the
scope narrowed". It is checked once, when the boundary is written.

Earns nothing:
- a new observation (novelty)
- more trials, more words, more evidence (volume)
- "definitely", "clearly", "certainly" (confidence text)
- a different prediction that does not contain the old one (that is a new hypothesis, not a narrower one)

## Why the order is fixed

REPEAT before VARY: a thing that happened once is not a thing yet. VARY before BOUNDARY:
you cannot say where it fails until you saw it fail. BOUNDARY before COMBINE: composing
an unbounded effect spreads the unknown. COMBINE before NAME: a skill that has never
been used with anything else has no known interface.
