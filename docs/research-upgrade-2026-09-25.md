# Self-upgrade research, 2026-09-25

The council was pointed at itself: what should change so it finds real answers to real problems
more often, and learns from people? Nine Sonnet workers each took one direction, used live web
search only (Keenable, no pretrained facts), and ran two or three rounds between 05:00 and 05:17
IST. Rounds two and three re-fetched every arXiv id they cited and adversarially checked the most
surprising numbers. Raw notes with URL, date and exact quote per fact are in
`docs/runs/2026-09-25-self-upgrade/`; this file is the merged reading. Numbers below were checked
against the primary page unless marked PARTIAL.

This was a guided research session, not a script-backed run: no goal.json, no journal, no
budget.py. Treat it as a literature review that feeds the steps in `docs/spec-v2-upgrade.md`.

## What a prompt cannot do

No wording "unlocks AGI". A 25,000-run audit found agents ignore evidence in 68% of cases, the
base model explains 41% of the variance and the scaffold 1.5%, and only near-complete correct
reasoning traces moved the rate (arXiv 2604.18805; file 02). So every upgrade below is enforced
by a script, the way the evidence rule already is. Prose asking the model to "be rigorous" is
not an upgrade.

## Findings, grouped by the step they change

### 1. Hypotheses must say what would prove them wrong
- Three independent frameworks (POPPER, EvoSCM, FirstResearch) converge on: claim, test,
  confirming observation, refuting observation, all written before the test runs (file 03).
- The ideation-execution gap study: ideas rated more novel by LLMs lost after execution; the
  predictor of failure was vagueness, not low novelty (arXiv 2506.20803; file 03).
- Premature closure is the most common diagnostic-error cause in medicine; developers form about
  two hypotheses per defect unprompted. Being handed candidate hypotheses gave odds ratio 6.24 of
  a fix against the pooled other groups (PARTIAL: not hypotheses-vs-fault-locations alone;
  arXiv 2005.13652; file 03).

### 2. Look for disconfirming evidence on purpose
- "Failing to Falsify": explicit opposite-seeking prompts raised discovery from 42% to 56%,
  aggregated across models (arXiv 2604.02485; file 04).
- Retrieval with negated claims gave +2 to 10 points accuracy (arXiv 2602.18693; file 04).
- Dense retrieval misses contradictions: MRR 0.023 against 0.750 for lexical search on the same
  set (arXiv 2603.17580; file 04). A negation query must be a keyword query.
- Planted false sources raise false-conclusion adoption from 0% to 54.7%, up to 85% when injected
  right before synthesis (MisKnow-Agent, arXiv 2607.20891; file 08).

### 3. Pairwise ranking is noisy; judge each pair both ways
- Repeated LLM-judge trials: 13.6% mean flip rate, position bias up to 72% (file 01).
- Position-swap plus abstain-on-disagreement is the cheap fix; kappa not raw agreement; judge
  should not share the generator's model family (arXiv 2606.19544, 541K judgments; file 04).
- Sequential Elo is K-factor and order dependent; one Bradley-Terry fit over all pairs is stable,
  and with 3-6 hypotheses a full round robin is 3-15 pairs (arXiv 2411.14483; file 05). No study
  validates calibration at this small N; that part is inference.

### 4. A council is not free; it must beat one agent at equal cost
- Majority voting explains most debate gains (Debate or Vote, NeurIPS 2025); several
  compute-matched studies find single agent plus self-consistency equal or better (file 05).
- Google's 260-configuration study: multi-agent lost 39-70% on sequential planning and gained
  81% on parallel tasks (file 05). Evidence gathering is parallel; the final judgement is not.
- Co-Scientist (Nature 2026) is one model family and spends most compute verifying, not
  generating (files 01, 03, 05).
- Same-model devil's advocates are weaker than authentic dissent (Nemeth; file 01). A correct
  minority survives to the final answer only 46-51% of the time without protection
  (arXiv 2609.13261; file 05).

### 5. Report: separate what was read from what was inferred
- Kosmos's own numbers: interpretation statements 57.9% accurate against about 82-85% for direct
  data and literature statements (file 06). Our claims already carry `claim_type`
  observed/inferred/predicted; the report does not yet separate them.
- A resolving link is not support. Tow Center: over 60% citation-attribution error across eight
  AI search engines, best 37% (file 04). A local NLI cross-encoder agrees with humans about 90% on
  "supported" but catches only about 71% of contradictions (file 04), so it confirms, it does not
  clear.
- Attribute claim to one exact source, not to a pool: pooled checks pass wrong-source citations
  (ProvenanceGuard, arXiv 2606.18037; file 04).

### 6. Learn from people, carefully
- The pattern that repeats across four case studies: turn a human correction into one specific
  rule in a version-controlled file, and a human merges it. The best numbers are PARTIAL (a
  vendor's own blog; a 74-exposure study its authors call too small; file 07).
- Curated skills +16.2 points; self-generated skills -1.3 points (SkillsBench, arXiv 2602.12670;
  the "+0.0" figure seen elsewhere is a paraphrase; file 07). This backs the existing rule that
  the model never promotes.
- Failures and successes need separate lesson extractors; mixing them hurts (ReasoningBank,
  arXiv 2509.25140; file 07).
- Skill gains often vanish once the token budget is matched (arXiv 2606.15017; file 07).
- Lessons derived from fetched content need lineage, not just a source tag, or poisoned content
  gets laundered into "our own" memory (arXiv 2605.14421; file 07).

### 7. Measure it, or do not claim it
- DRACO: 100 tasks, 5 judge runs per task, rubric items already at 90% dropped; orchestration beat
  the bare model by 10.7 points (arXiv 2602.11685; file 08).
- LLM judges are near chance on long reports (LongJudgeBench, about 56%; file 08). Use binary
  rubric items and deterministic checks first.
- A belief-revision eval needs a case where the agent SHOULD change its mind, or stubbornness
  scores as rigour (arXiv 2603.03330, 2603.23848; file 08).

### 8. Experiments close the loop, and sandboxes leak
- Real validated results came from propose, run, measure, update loops, and even then needed
  weeks of human correction (AlphaEvolve, A-Lab; file 06). Independent checks of Kosmos claims
  fell to about 58-60% for the novel cross-domain ones (file 01).
- Anthropic's own disclosure: a misconfigured evaluation environment had live internet; across
  141,006 reviewed runs the model reached real systems of three organisations
  (anthropic.com/news/investigating-incidents-cybersecurity-evals, fetched and read 2026-09-25).
  Invariant 8 stays; any sandbox adapter is designed as hostile-facing from day one.

### 9. Subagents stop early
- Observed in this session: all nine workers told "research 15 minutes" stopped at 4-6 minutes and
  had to be sent back. Models have no sense of elapsed time; a duration reads as "enough", not a
  floor. The fix that has a published example is a coverage gate that blocks synthesis and
  re-dispatches into any gap (file 09).

## Where the evidence was weak
- The "cognitive trap", "time floor" and "short prompt" designs are syntheses of adjacent sources,
  not benchmarked on research tasks (files 08, 09).
- No study compares an evidence-linked council like this one against free debate (file 05).
- Several vendor blogs were excluded as low credibility (listed at the end of file 05).
