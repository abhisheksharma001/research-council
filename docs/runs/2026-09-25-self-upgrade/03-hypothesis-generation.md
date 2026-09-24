# Hypothesis Generation, Novelty & Creativity in LLM Agents (2024-2026) — Research Notes

Scope: idea diversity measurement, LLM-vs-human idea studies (Si et al. + follow-ups on execution), tree/evolutionary idea search, analogical transfer, persona diversity, temperature/sampling, verbalized sampling, literature-grounded novelty checks, idea combination. All facts below were retrieved via Keenable web search/fetch this session (2026-09-25).

---

## (a) Key Findings

### 1. LLMs generate ideas judged MORE novel than expert humans — but this doesn't survive execution

- **Claim:** In a blinded, controlled study, 100+ NLP researchers wrote ideas and reviewed both human and LLM-agent ideas on the same topics; LLM ideas scored higher on novelty (5.64 vs 4.84) and excitement, slightly lower on feasibility (6.34 vs 6.61).
  URL: https://arxiv.org/pdf/2409.04109 (Si, Yang, Hashimoto, "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers"), published 2024-09-09.
  Quote: *"we find LLM-generated ideas are judged as more novel (p < 0.05) than human expert ideas while being judged slightly weaker on feasibility... they lack idea diversity when we scale up idea generation, and they cannot currently serve as reliable evaluators."*

- **Claim:** Scaling idea generation hits severe diminishing returns / duplication — from a pipeline generating 4,000 seed ideas at high temperature, only ~200 distinct concepts survived semantic deduplication (>0.8 cosine similarity threshold), and diversity plateaus after ~2,000 generations.
  URL: https://zeroshot.it.com/can-llms-really-out%E2%80%91innovate-us-a-deep%E2%80%91dive-review-of-can-llms-generate-novel-research-ideas (review of Si et al.), 2024-09-12.
  Quote: *"The process started with 4,000 generated ideas, but only ~200 distinct concepts survived deduplication... at this scale, the model is mostly producing redundant, low-entropy variations on a theme."*

- **Claim (the "ideation-execution gap"):** A follow-up RCT recruited 43 expert researchers to actually execute (100+ hours each) either an LLM-generated or human-generated idea from the prior study, then blind-reviewed the finished projects. LLM ideas' scores dropped far more from ideation to execution than human ideas did, on every metric (novelty, excitement, effectiveness, overall; p<0.05), **flipping the ranking** so humans win post-execution.
  URL: https://arxiv.org/abs/2506.20803 (Si, Hashimoto, Yang, "The Ideation-Execution Gap"), published 2025-06-27.
  Quote: *"the scores of the LLM-generated ideas decrease significantly more than expert-written ideas... When comparing the aggregated review scores from the execution study, we even observe that for many metrics there is a flip in rankings where human ideas score higher than LLM ideas."*
  Concrete failure mode found: 6 of 43 AI ideas had proposed human evaluations (e.g., recruiting native speakers) that executors quietly downgraded to "LLM-as-judge" for cost/time reasons — removing exactly the element that had driven the idea's excitement score.

- **Claim:** A 2026 follow-up building an automated executor found LLM-authored research ideas are frequently technically "convincing but ineffective" once actually run; separately, using RL to optimize an idea-generator against execution reward causes **diversity collapse** — the model converges on a few easy-to-implement ideas.
  URL: https://arxiv.org/abs/2601.14525 ("Towards Execution-Grounded Automated AI Research"), 2026-01-22.
  Quote: *"we reveal that RL causes the ideator model to converge on a few easy-to-implement ideas, resulting in a collapse in thinking length and idea diversity... RL from execution reward suffers from diversity collapse and does not improve the upper-bound."*

- **Claim:** A proxy-benchmark study found raw overgeneration + reranking of ideas produces **zero** research-strong, non-duplicate ideas; only targeted refinement of a selected subset works.
  URL: https://arxiv.org/html/2607.14118 ("Budgeted Subset Refinement for Execution-Aware LLM Research Ideation"), 2026-07-17.
  Quote: *"raw generation and reranking alone produce no research-strong nonduplicate ideas under the benchmark rubric, while refinement is necessary for strong proxy-rated portfolios."*

### 2. Mode collapse has a data-level cause, and a training-free fix exists: Verbalized Sampling

- **Claim:** Post-training alignment (RLHF/DPO) causes mode collapse because human preference annotators have a "typicality bias" — they favor familiar/fluent text — which mathematically sharpens the aligned policy toward the base model's single mode.
  URL: https://arxiv.org/pdf/2510.01171 (Zhang, Yu, Chong, Sicilia, Tomz, Manning, Shi — Stanford/Northeastern, "Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity"), 2025-10-13 (updated through 2026-07).
  Quote: *"we identify a fundamental, pervasive data-level driver: typicality bias in preference data... Even with a perfect reward model and optimization process, inherent bias within preference datasets may still drive mode collapse."*

- **Claim/Fix:** Instead of asking for one instance ("give me an idea"), prompting the model to **verbalize a probability distribution over responses** ("generate 5 responses with their probabilities, sampled from the tails <0.10") recovers much of the base model's diversity, without retraining.
  Same URL. Quote: *"VS increases diversity by 1.6-2.1x over direct prompting... improves human evaluation scores by 25.7%... recovers 66.8% of the base model's diversity... more capable models benefit more from VS."* Also: list-style prompts ("give me 5 ideas") only produce a "bestseller list" of the same top-k modes — they do NOT restore diversity the way distribution-style prompting does (Theorem C2 vs C3 in the paper).

- **Claim:** ARTS (an automated-ML-research tree-search system) explicitly adopted Verbalized Sampling as its idea-diversification mechanism inside tree search.
  URL: https://arxiv.org/html/2606.21891 ("Learning the ARTS of Search for Automated Discovery"), 2026-06-23.
  Quote: *"To improve hypothesis diversity, ARTS uses an adapted version of Verbalized Sampling."*

### 3. Diversity has two separable failure mechanisms — and separate fixes (fixation vs. knowledge partitioning)

- **Claim:** LLM collective idea diversity is undermined by two distinct, separately-fixable mechanisms: (1) individual-level "fixation" (early tokens/ideas constrain later ones, like human design fixation), and (2) collective-level lack of "knowledge partitioning" (LLMs sample from one unified distribution rather than each drawing from a distinct idiosyncratic knowledge region, the way different humans do).
  URL: https://arxiv.org/pdf/2602.20408 ("Examining and Addressing Barriers to Diversity in LLM-Generated Ideas"), 2026-02-25.
  Quote: *"Chain-of-Thought (CoT) prompting reduces fixation by encouraging structured reasoning (only in LLMs, not humans), while ordinary personas (versus 'creative entrepreneurs' such as Steve Jobs) improve knowledge partitioning... Combining both approaches produces the highest idea diversity, outperforming humans."*
  Concrete recipe found effective: (1) generate short idea *titles* first, (2) explicitly instruct the model to revise the titles to be distinct/bolder, (3) then expand into full ideas — CoT-style. Separately: use *heterogeneous "ordinary" personas* ("Zumba-loving college student") rather than generic "famous creative genius" personas — ordinary personas act as better semantic sampling cues and produced *greater inter-instance dispersion*.
  Quote on temperature: *"a higher temperature brings only slight improvement in idea diversity while often producing nonsensical answers, which greatly reduces idea quality."* Hybrid prompting (mixing several prompt styles then pooling/selecting) was tested and found **not** more effective than CoT or personas alone.

- **Claim (persona mechanism, corroborating):** Prior review synthesized: persona modifiers improve diversity; CoT (generate-then-explicitly-diversify) yields the largest single-technique gains, "nearly reaching the levels of human group idea generation"; temperature adjustments give only slight diversity gains at the cost of quality; hybrid pooling of multiple prompt styles does not beat CoT/persona alone.
  Same source (arxiv 2602.20408), citing synthesis of prior prompting-diversity literature.

### 4. Persona / multi-agent diversity — mixed but generally positive picture

- **Claim:** Assigning each of several LLM agents a distinct, richly-specified persona and having them brainstorm, then pooling, measurably increases divergent output ("Spark Effect") over a non-persona baseline, across a 60+-persona catalogue.
  URL: https://arxiv.org/abs/2510.15568 ("The Spark Effect: On Engineering Creative Diversity in Multi-Agent AI Systems"), 2025-10-20.

- **Claim:** In design-concept generation, giving an LLM multiple professional personas via **parallel independent prompts** (or a sequential "generate-then-update" chain across personas) produced measurably more diverse design concepts than a single combined multi-persona prompt.
  URL: https://cambridge.org/.../enhancing-design-concept-diversity-multi-persona-prompting-strategies (Design Science Journal), 2025-12-08.

- **Counter-note within same literature:** Two cited prior studies (Hu & Collier 2024; Zheng et al. 2024) found persona prompts have *minimal* impact on NLP task performance, while a third (Luz de Araujo & Roth 2025) found personas *do* increase response variability — the effect is inconsistent across task types.

### 5. Analogical reasoning is one of the most effective mode-collapse fixes found this cycle

- **Claim:** LLMs asked directly for open-ended research solutions collapse into low-diversity, near-duplicate outputs. Explicitly prompting the model to first generate **cross-domain analogies** (shared relational structure to an unrelated domain), then search for solutions via those analogies, produced 90-173% higher diversity metrics and raised the novel-solution rate from as low as 1.6% (baseline direct prompting) to over 50%.
  URL: https://arxiv.org/html/2605.11258 ("Unlocking LLM Creativity in Science through Analogical Reasoning"), 2026-05-13.
  Quote: *"AR discovers significantly more diverse generations (improving solution diversity metrics by 90-173%), generates novel solutions over 50% of the time (compared to as little as 1.6% for baselines)... We confirm this result in a human study, where AR solutions were consistently scored as more novel than baseline solutions."*
  Validated on 4 real biomedical problems with quantitative downstream gains (e.g., ~13x improvement on a perturbation-prediction distributional metric).

- **Claim:** In materials science, prompting an LLM for explicit **cross-domain analogies** (e.g., "solar system : atom" style relational mapping) before generating candidate battery materials produced "far more" diverse, structurally bolder candidates than naive prompting, which yielded "minimal elemental ratio tweaking."
  URL: https://arxiv.org/abs/2510.22312 ("LacMaterial: LLMs as Analogical Chemists for Materials Discovery"), 2025-10-28.

- **Claim:** In a controlled study with 24 design students, an analogical-reasoning-based co-creative tool (ALIA) produced significantly higher-rated novel ideas than a baseline without structured analogy support.
  URL: https://cambridge.org/.../analogical_reasoning_with_large_language_models... (Design Science Journal), 2026-01-27.

### 6. Tree search / evolutionary search for hypotheses: score-based heuristics conflate idea quality with implementation quality

- **Claim:** Classic tree-search (AIDE, AIRA, AI Scientist v2) and evolutionary (FunSearch, AlphaEvolve, OpenEvolve) systems score nodes by final execution performance, which **conflates a good hypothesis with good execution** — "an untuned Transformer scores below an LSTM," so heuristic search prunes promising ideas that were just poorly implemented.
  URL: https://arxiv.org/html/2606.21891 ("Learning the ARTS of Search for Automated Discovery"), 2026-06-23.
  Fix proposed (ARTS): give a reasoning model an `INSPECT` tool to read full execution logs/code, not just the score, so it can attribute failure to bad-hypothesis vs. bad-implementation before deciding what to try next; result: 15.3% relative improvement over leading methods across 22 ML-research tasks (MLGym/MLEBench); a distilled Qwen3-4B "scientist" (via test-time training on the search tree) matched frontier closed models at ~5x lower inference cost.

- **Claim:** AutoDiscovery uses Monte Carlo Tree Search with progressive widening, rewarding hypotheses by **Bayesian surprise** (the LLM's own prior-vs-posterior belief shift after seeing experimental results) rather than diversity heuristics or "interestingness" proxies — under a fixed budget it produced 5–29% more surprising discoveries than competitors, and ~2/3 of its discoveries surprised human domain experts too.
  URL: https://arxiv.org/pdf/2507.00310 ("AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise"), 2025-11-27.

- **Claim:** ERA (Google DeepMind-adjacent, published in Nature 2026) combines LLM-driven tree search with **injected external research ideas** (from papers/textbooks/search) as mutation guidance, and explicitly **recombines successful prior implementations** to create more powerful methods — beating best human-built methods on real leaderboards (bioinformatics single-cell analysis, COVID hospitalization forecasting vs. CDC ensemble).
  URL: https://nature.com/articles/s41586-026-10658-6, 2026-05-19.

- **Claim:** OR-Agent found that **naive parallel idea generation for tree-search children produces near-identical, structurally repetitive ideas** unless the idea-generation step is explicitly told to treat sibling ideas as "a coherent research plan" of jointly-distinct directions ("coordinated idea generation") — this measurably increased diversity of children generated per node.
  URL: https://arxiv.org/html/2602.13769 ("OR-Agent: Bridging Evolutionary Search and Structured Research"), 2026-02-17.
  Also documents a "population ruin" failure mode: without an explicit mechanism to preserve diversity in an evolutionary program database, one seemingly-good but brittle solution can dominate and wipe out the rest of the population.

- **Claim:** "Idea Search" decomposes known expert methods into an explicit, queryable **"Idea Bank"** of atomic recombinable design choices, samples from it to guide tree-search mutation proposals, and dynamically updates the bank with new high-scoring concepts discovered along the way — this broke through a performance plateau a pure tree-search baseline had hit (0.678 → 0.697 on a real bioinformatics benchmark).
  URL: https://arxiv.org/abs/2608.08958, 2026-08-11.

### 7. Combining/evolving ideas: Google's Co-Scientist (Nature, May 2026) is architecturally almost identical to research-council's council design

- **Claim:** Co-Scientist (Gottweis et al., Nature 2026) runs exactly six specialized agents — **Generation, Reflection, Ranking, Evolution, Proximity, Meta-review** — coordinated by a Supervisor, where hypotheses compete in an **Elo-based tournament**, and the Evolution agent explicitly does crossover ("combining the strongest parts of several [hypotheses]") and mutation ("forcing deliberately divergent out-of-the-box ideas") without ever editing a hypothesis in place — each offspring must re-earn its own Elo score. It was validated with real wet-lab experiments (AML drug repurposing/combination therapies).
  URL: https://nature.com/articles/s41586-026-10644-y (also alphaxiv.org/abs/2502.18864v2), published 2026-05-15 / initially shared Feb 2025.
  Quote: *"Evolution reproduces rather than overwrites. The Evolution agent builds new hypotheses from the top-ranked ones: combining the strongest parts of several (the crossover analog)... It never edits a hypothesis in place, so strong parents survive and every offspring has to earn its own Elo back in the tournament."*
  Note the explicit **Proximity** agent role (clusters/deduplicates ideas so the system explores widely instead of circling one answer) — this is a role research-council's current pipeline does not appear to name explicitly.

- **Claim:** ResearchAgent grounds idea generation in both a citation graph (papers linked to a seed paper) AND a separate **entity-centric knowledge store** built from concept co-occurrence across disciplines specifically to enable **cross-domain "cross-pollination"** — ideas generated this way outperformed a version using only the citation-graph-based related work, per human+model evaluation.
  URL: https://arxiv.org/html/2404.07738, 2024/2025.
  It also uses multiple LLM-powered "ReviewingAgents" whose evaluation criteria are elicited from real human researcher judgments (not generic prompts) — closes the loop with iterative refinement (saturates after ~3 iterations).

- **Claim:** Scideator supports human ideation via explicit **facet recombination**: extract (purpose, mechanism, evaluation) facets from a set of papers, let the user interactively recombine facets across papers to synthesize new ideas, paired with an automated Idea Novelty Checker. In a within-subjects study, 19 CS researchers found significantly more interesting ideas with Scideator than with a search-engine + LLM baseline.
  URL: https://tomhoper.github.io/research/boosting (describing Radensky et al., Scideator), referenced 2024.

### 8. Literature-grounded novelty checking outperforms similarity-score / LLM-as-judge novelty checks

- **Claim:** Automated novelty checks have evolved from lexical n-gram/TF-IDF, to semantic embeddings, to raw LLM 1-10 novelty scores or binary novel/not-novel judgments — but none of these **ground their rationale in retrieved prior work**, causing them to misclassify well-documented ideas as novel.
  URL: https://arxiv.org/abs/2506.22026 ("Literature-Grounded Novelty Assessment of Scientific Ideas"), 2025-06-30.
  Fix ("Idea Novelty Checker"): a retrieve-then-rerank RAG pipeline (broad keyword/snippet retrieval → embedding filter → facet-based LLM rerank) with expert-labeled examples for comparison, achieving **~13% higher agreement** with expert novelty judgments than existing approaches. The facet-based rerank step was shown by ablation to be important, not just the retrieval step.

- **Claim:** SciMON explicitly optimizes novelty by an iterative loop: generate idea → retrieve nearest prior-literature neighbors → if too similar, force the model to regenerate a version more distinct from that specific retrieved neighbor → repeat until sufficiently novel. Plain GPT-4 without this loop produced ideas judged low on both technical depth and novelty.
  URL: https://aclanthology.org/2024.acl-long.18, ACL 2024.

- **Claim:** HypER goes beyond surface-similarity literature grounding by training a small model to validate whether a candidate hypothesis's supporting reasoning-chain (paper A → paper B → hypothesis) is *logically valid* dependency, not just topically similar; this improved evidence-grounded hypothesis quality (0.327 vs. 0.305 for the base model) and expert-rated feasibility/impact.
  URL: https://arxiv.org/abs/2506.12937, 2025-08-25.

### 9. Diversity measurement: Vendi Score family is the closest thing to a standard, but has known caveats

- **Claim:** The Vendi Score (exponential of the von Neumann entropy of a similarity-kernel matrix over a sample set) is a reference-free, similarity-aware "effective number of distinct items" metric, extended into a tunable family (order q) with different sensitivity to rare vs. common items; VS of high order is best for **detecting duplication/near-duplicates** specifically (useful for a research-council check on whether Generation actually produced non-redundant hypotheses).
  URL: https://doi.org/10.48550/arxiv.2310.12952 ("Cousins of the Vendi Score"), 2024-05-07.

- **Caveat/Counter-evidence:** In a human-eval benchmark for image generation, the Vendi Score only reached ~65-80% agreement with human-perceived diversity judgments, and required careful choice of embedding/representation space to get there — it is not a drop-in ground truth for "is this actually diverse to a person."
  URL: https://doi.org/10.48550/arxiv.2511.10547 ("Benchmarking Diversity in Image Generation via Attribute-Conditional Human Evaluation"), 2025-11-14.

- **Claim:** Standard generative models (and by extension, aligned LLMs) show a **systematic downward diversity bias** relative to real/training data, partly for a boring statistical reason: entropy-based diversity estimates provably increase with sample size, so any model trained to match a *finite* empirical dataset inherits an underestimate of the true distribution's diversity.
  URL: https://arxiv.org/pdf/2602.14682, 2026-02-17.

- **Claim:** A recent CreativityPrism benchmark decomposes "creativity" into three orthogonal automatic-metric dimensions — **quality, novelty, and diversity** — across 8 tasks in 3 domains (divergent thinking, creative writing, logical reasoning), explicitly because prior benchmarks conflated these.
  URL: https://arxiv.org/html/2510.20091, 2025-10-24.

### 10. Sampling/temperature: temperature alone is a weak diversity lever compared to prompting strategy

- **Claim:** Increasing temperature gives only mild diversity gains for creative tasks and can hurt quality/coherence; **min-p sampling** (dynamically scaling the truncation threshold by the top token's confidence) gave a better quality-diversity Pareto frontier than temperature/top-p/top-k across model families, confirmed via human eval preferring min-p on both creativity and coherence.
  URL: https://arxiv.org/pdf/2407.01082 ("Turning Up the Heat: Min-p Sampling"), 2025-11-21 (dataset run), original paper 2024.

- **Claim:** Variance in LLM creative-idea-generation output is dominated by **prompt choice and model choice**, not raw sampling stochasticity: in one variance decomposition, for output *originality*, prompt accounted for 36.4%, model choice for 40.9%, and within-model (sampling) variance for only 10.6%.
  URL: https://arxiv.org/abs/2601.21339 ("Within-Model vs Between-Prompt Variability in Large Language Models for Creative Tasks"), 2026-01-30.
  Implication: for research-council, *how you prompt Generation* and *which model you use* matter far more for idea diversity than turning up temperature.

---

## (b) Counter-Evidence / Complications

1. **Novelty ≠ good research.** The single strongest counter-finding this cycle: LLM-generated ideas judged *more novel* at ideation time score *worse* after actual execution, with rankings flipping in humans' favor (arxiv 2506.20803). Any research-council metric that stops at "novelty score" or "LLM-judge score" without an execution/grounding check is measuring the wrong thing.

2. **LLM self-evaluation of novelty/quality is unreliable.** Si et al. (2409.04109) explicitly flag "failures of LLM self-evaluation" — LLM-as-judge correlated poorly with human expert judgment. This directly undercuts any council design that relies on an LLM Meta-review or Ranking step as ground truth without external grounding.

3. **Temperature is not a real fix for diversity** — multiple independent sources agree (2602.20408 "Barriers to Diversity"; 2601.21339 variance decomposition; Control-the-Temperature paper) that raising temperature gives weak diversity gains at real quality cost, and is dominated by prompting-strategy and model-choice effects.

4. **Persona effects are inconsistent across task types.** Not all persona literature agrees personas help — Hu & Collier 2024 and Zheng et al. 2024 (cited within the Design Science Journal paper) found persona prompts have minimal effect on standard NLP task performance; the *ideation-specific* diversity gains (Spark Effect, Barriers-to-Diversity, multi-persona design studies) may not generalize to grounded correctness tasks. Also: famous "creative genius" personas (Steve Jobs, Elon Musk) underperform "ordinary" heterogeneous personas for diversity specifically (2602.20408) — a widely-used pattern in practice may be counterproductive.

5. **Score-based tree/evolutionary search actively prunes good hypotheses with poor early execution** (ARTS paper) — a naive "rank hypotheses by result and keep exploring the best branch" council/search design will systematically discard good ideas that were simply implemented or evaluated badly, unless it can inspect *why* a branch scored low.

6. **Overgeneration + reranking alone doesn't produce a usable diverse portfolio.** The Budgeted Subset Refinement paper found zero research-strong nonduplicate ideas from raw generation+rerank; targeted refinement of a subset was required. This is a direct counter to "just generate lots more hypotheses" as a diversity strategy.

7. **Diversity metrics themselves are imperfect proxies for human-perceived diversity** (Vendi Score ~65-80% agreement with humans depending on embedding space) — an automated diversity gate in research-council should not be trusted blindly without spot-checking against human/qualitative judgment.

8. **RL-tuning an idea generator against execution reward causes diversity collapse**, not diversity gain (2601.14525) — if research-council or a similar system ever considers fine-tuning a generation agent against a downstream success signal, this is a known failure mode to design around explicitly (favor search/scaffolding over RL fine-tuning for the ideator).

---

## (c) Concrete Upgrade Ideas for research-council (evidence-tied)

**HIGH IMPACT**

1. **Add "Verbalized Sampling" as the Generation prompt format**, replacing "give me N hypotheses" with "verbalize a probability distribution over hypotheses, list ~7-10 with self-assigned probabilities, and explicitly sample some from the low-probability tail (<0.10)." Evidence: 1.6-2.1x diversity gain, 25.7% human-eval quality gain, recovers ~67% of base-model diversity, training-free (arxiv 2510.01171). Directly fixes the "lack of diversity when scaling generation" problem Si et al. documented in the exact ideation-agent pattern research-council's Generation role already resembles.

2. **Add a hard "no evidence-free novelty score" rule reinforcement: require any idea marked "novel" to survive a literature-grounded retrieve-then-rerank novelty check**, not a raw LLM 1-10 score. Evidence: Idea Novelty Checker gets ~13% higher agreement with expert novelty judgment than similarity-score/LLM-score baselines by retrieving prior work and reasoning against it explicitly (arxiv 2506.22026); SciMON's "iteratively compare to nearest retrieved neighbor, regenerate if too similar" loop is a cheap, implementable version of this today. This is exactly what research-council's "no evidence = unverified" rule already gestures at for claims — extend the same discipline to novelty *claims* about hypotheses, not just factual claims.

3. **Explicitly separate "hypothesis quality" from "evidence/execution quality" during Reflection/Ranking**, mirroring ARTS's INSPECT-based failure attribution. Evidence: score-conflation between a good idea and a good execution is a documented, named failure mode in tree-search-based discovery systems (arxiv 2606.21891), and is the root cause of the ideation-execution gap in the human study (2506.20803, 6/43 ideas silently downgraded during execution in ways that erased their strongest scoring driver). Concretely: when Reflection objects to a hypothesis, force it to tag the objection as "the idea is flawed" vs. "the idea is fine but would be hard/costly to verify" — these should not be conflated in a single score, and should not by default kill an idea in the latter category.

4. **Add an explicit "Proximity"-style dedup/cluster step distinct from Ranking**, matching Co-Scientist's architecture (Generation, Reflection, Ranking, Evolution, **Proximity**, Meta-review — Nature 2026). Evidence: OR-Agent independently found that without an explicit anti-redundancy/anti-domination mechanism, evolutionary hypothesis pools suffer "population ruin" where one plausible-but-brittle idea dominates and wipes out diversity (arxiv 2602.13769); Si et al. found overgenerated ideas collapse to ~200 distinct concepts out of 4,000 without explicit dedup. If research-council's council currently only has Generation/Reflection/Ranking/Meta-review, adding a named Proximity/dedup pass (embedding-cluster + LLM-confirm near-duplicates, à la AutoDiscovery's hierarchical agglomerative clustering step, arxiv 2507.00310) is a small, well-evidenced structural addition.

5. **Use "coordinated idea generation" for the Generation step, not independent parallel sampling.** Evidence: OR-Agent found independently-sampled sibling ideas were "nearly identical" and "structural[ly] repetitive," while explicitly prompting the model to produce a **set** of jointly-distinct ideas (treating the batch as one coherent research plan with a diversity requirement baked into the single prompt) substantially increased diversity (arxiv 2602.13769). Concretely: Generation's prompt should say "produce N hypotheses that are pairwise structurally distinct — no two should share the same core mechanism" rather than sampling N independent completions.

**MEDIUM IMPACT**

6. **Add an explicit analogical-reasoning sub-step before/within Generation** — prompt for a cross-domain analogy (shared relational structure, not surface similarity) to the research goal, then generate hypotheses via that analogy. Evidence: this specific technique produced the single largest diversity/novelty jump found this session — 90-173% diversity increase, novel-solution rate from 1.6% to >50% for open-ended science solution generation, validated with quantitative downstream gains on 4 real biomedical problems (arxiv 2605.11258). This maps naturally onto the curiosity protocol's "vary" step — vary by deliberately swapping in a structurally-analogous domain, not just paraphrasing.

7. **Combine Chain-of-Thought idea-refinement with "ordinary" (not celebrity) personas for the Generation role**, and treat this pairing as the default diversity lever instead of temperature. Evidence: this combination "produc[ed] the highest idea diversity, outperforming humans" in a controlled 4-study design, whereas temperature increases gave only "slight improvement... while often producing nonsensical answers" (arxiv 2602.20408). Concrete recipe from the paper: generate short idea titles → explicitly instruct revision to make titles distinct/bolder → expand into full hypotheses; and when using personas, prefer specific "ordinary person" personas over generic "brilliant creative genius" archetypes.

8. **Add a Bayesian-surprise-flavored curiosity signal to the "boundary" step of the spark protocol**: instead of (or alongside) an LLM-judged "interestingness" score, have the model state its prior belief about a hypothesis before evidence-gathering and its posterior belief after, and weight boundary-pushing by the magnitude of that shift. Evidence: AutoDiscovery's MCTS-with-Bayesian-surprise-reward beat diversity-heuristic and "interestingness"-proxy baselines by 5-29% more surprising discoveries, and ~2/3 of its "surprising" outputs surprised human domain experts too (arxiv 2507.00310) — this is a more principled operationalization of "boundary" than a generic novelty prompt.

9. **When forming a hypothesis "idea bank" or seeding cross-hypothesis recombination (the Elo/Evolution step), decompose top hypotheses into atomic reusable design components and let Evolution recombine components, not whole hypotheses.** Evidence: Google's Co-Scientist Evolution agent does exactly this ("combining the strongest parts of several [hypotheses]... never edits a hypothesis in place, so strong parents survive"), and "Idea Search" (arxiv 2608.08958) shows a dynamically-updated bank of atomic ideas breaks through plateaus a flat tree search hits. This is a natural extension of research-council's existing blinded-Elo council design, not a new architecture.

**LOWER IMPACT / NICE-TO-HAVE**

10. **Track a Vendi-Score-style diversity number (or at minimum a max-pairwise-cosine-similarity number) on each batch of Generation output as a cheap automated gate**, flagging batches with low effective diversity for a forced re-generation with Verbalized Sampling before they reach Reflection. Evidence: Vendi Score is the closest thing to a standard reference-free diversity metric and its high-order variant is specifically good at catching duplication (arxiv 2310.12952) — but given its only ~65-80% agreement with human judgment (arxiv 2511.10547), treat it as a cheap pre-filter/red-flag, not a pass/fail gate.

11. **Do not rely on raising temperature as a documented "diversity" lever in any of research-council's config/docs.** Evidence is now consistent and multi-source (Barriers-to-Diversity, min-p paper, variance-decomposition paper) that temperature gives weak diversity return for real quality cost, and that prompt design + model choice dominate the variance. If research-council currently exposes a "creativity = higher temperature" knob, its documentation/defaults should be corrected or at least caveated.

12. **If a curiosity/novelty score is ever used to auto-prioritize hypotheses for deeper research, avoid closing the loop with RL fine-tuning of the generator against that score** — this is a documented, named failure mode (RL against execution/novelty reward → diversity collapse, arxiv 2601.14525). Keep the loop as inference-time search/prompting (verbalized sampling, coordinated generation, analogical reasoning), not weight updates.

---

## Round 2 (continued research, same session, Keenable only)

### R2.1 — Co-Scientist (Nature 2026): exact Evolution + Proximity mechanics, and what was validated in wet lab

- **Evolution agent mechanics (confirmed across primary abstract + secondary write-ups of the same Nature paper):** Evolution never edits an existing hypothesis in place — it always spawns new offspring so tournament-tested parents survive and every offspring must re-earn its own Elo score. The Nature paper's own supplement lists six named strategies; independent write-ups agree on: **combine** (crossover — merge the strongest parts of several top-ranked hypotheses), **simplify** (make an idea more experimentally tractable), **feasibility/grounding** (re-ground a hypothesis in fresh literature or improve its practicality), **inspiration-from-existing** (spin off a variant inspired by one or more parents), and **out-of-the-box** (deliberately divergent mutation to force exploration away from the current best ideas).
  URL: https://benjaminhan.net/posts/20260606-co-scientist-scientific-discovery, 2026-06-06. Quote: *"The Evolution agent builds new hypotheses from the top-ranked ones: combining the strongest parts of several (the crossover analog), spinning off variants inspired by one or more parents, regrounding them in fresh literature, simplifying them, or forcing deliberately divergent 'out-of-the-box' ideas (the mutation analog). It never edits a hypothesis in place."*
  URL: https://alphaxiv.org/abs/2502.18864 (paraphrase of the Nature paper's own Evolution Agent description), 2026-06-29: *"Evolution Agent: This agent focuses on continuous improvement. It takes the top-ranked hypotheses and refines them by identifying weaknesses, drawing inspiration from other successful ideas, or simplifying complex protocols."*
  Caveat: a third-party open-source re-implementation (https://jrnlclub.com/post/15bc45f2-3d43-43f5-a13f-e2d3996aa670, 2026-05-28) states *"Four strategies (the paper lists six; we collapsed 'inspiration from existing' + 'enhancement through grounding' into our four since they share the same prompt scaffolding)"* — i.e. the exact count/naming of Evolution's strategies comes with a minor discrepancy between the primary Nature supplement (six) and secondary summaries; treat "six strategies, collapsible to four functional families (combine / simplify / feasibility / out-of-box)" as the safest characterization until the primary supplement text itself is read directly.

- **Proximity agent mechanics:** Proximity's stated job (primary paper language, confirmed via nature.com abstract) is "evaluates relatedness" — in practice, per the same secondary sources, it **embeds every hypothesis (a FAISS-style vector index in the re-implementation) and clusters/deduplicates them**, and this clustering serves two purposes: (1) preventing duplicate hypotheses from bloating the tournament, and (2) **feeding the Ranking agent's pairwise matchmaking so that structurally similar ("close rival") hypotheses are pitted against each other in debate**, rather than pairing random/unrelated hypotheses.
  URL: https://benjaminhan.net/posts/20260606-co-scientist-scientific-discovery, 2026-06-06: *"The Proximity agent clusters similar hypotheses so the debates pit close rivals against each other."*
  URL: https://alphaxiv.org/abs/2502.18864, 2026-06-29: *"The Proximity Agent ensures diversity by clustering similar ideas and de-duplicating the hypothesis space."*
  URL: https://nature.com/articles/s41586-026-10644-y, 2026-05-19 (primary): *"Proximity (which evaluates relatedness)... agents, to continuously generate, debate and evolve research hypotheses within a tournament framework."*

- **Wet-lab validation — exact numbers found (secondary sources synthesizing the Nature paper; treat compound-specific numbers as reported-by-secondary-source pending primary-supplement read):**
  URL: https://clinlabint.com/co-scientist-and-robin-ai-agents-deliver-validated-leukaemia-and-eye-disease-drug-candidates-in-nature-studies/, 2026-07-10: *"Co-Scientist generated repurposing hypotheses across a curated list of 2,300 approved drugs spanning 34 cancer types. After expert oncologists reviewed and ranked its predictions, five candidates were tested in vitro, and three (binimetinib, pacritinib, cerivastatin) inhibited acute myeloid leukemia (AML) cell viability. Binimetinib... reached a half-maximal inhibitory concentration (IC50)... as low as 2 nM in all AML lines but NOMO-1... With no prior preclinical evidence or human feedback, Co-Scientist proposed three wholly new picks: nanvuranlat, KIRA6, and leflunomide. KIRA6... had an 18-fold safety margin: it killed the stem-cell-like KG-1a leukemia cells at one-eighteenth the dose that affected healthy control cells (an IC50 of 10 nM against 180 nM)... Co-Scientist also proposed multi-drug regimens, and of seven it suggested, the two- and three-drug combinations were mostly synergistic in one leukemia line (MOLM-13)."*
  A separate secondary source reports a liver-fibrosis result not in the original round-1 notes: URL: https://trial.medpath.com/news/google-co-scientist-multi-agent-ai-system-validated-in-nature-preclinical-hypotheses-confirmed-in-aml-and-liver-fibrosis-public-registration-opens, 2026-05-30: *"identified Vorinostat as a liver fibrosis candidate, reducing TGFβ-induced chromatin changes by 91% in hepatic organoid tests."*
  Caution flag (found explicitly in one source): URL: https://thedailyscout.com/s/BbCoMw60OlU, 2026-09-01, notes: *"What is still missing in the public material reviewed here is a detailed, standalone paper or official repository spelling out the AML compounds, doses and assay results. One GitHub gist summarizing the paper refers to binimetinib and an in vitro IC50 around 7 nanomolar, but that is not a primary source and should be treated cautiously."* — i.e. secondary sources disagree slightly on the exact binimetinib IC50 (2nM vs. ~7nM reported elsewhere), so treat the specific potency numbers as approximate/secondary-sourced, not verbatim from the Nature paper itself (which this session did not fully render as clean text — the PDF fetch returned raw unparsed layout).

### R2.2 — Does idea diversity help for DEBUGGING / root-cause problems, not just science ideas?

**Yes — this is a separate, converging literature, and the mechanism (premature single-hypothesis anchoring) is even better evidenced here than in the "scientific creativity" literature.**

- **Claim:** In human software-debugging studies, developers unprompted form only ~2 hypotheses per defect, and *providing candidate hypotheses helped debugging roughly 6x more than providing candidate fault locations* — i.e. the bottleneck is hypothesis diversity/breadth, not localization precision.
  URL: https://programmer.ie/books/debugging-ai/47-chapter, 2026-09-06 (citing Alaboudi & LaToza, 2020). Quote: *"developers form only about two hypotheses per defect unprompted, and supplying candidate hypotheses helped roughly six times as much as supplying candidate fault locations."*

- **Claim:** The single most common cognitive error in real diagnostic (medical) error review is **"premature closure"** — stopping at the first plausible hypothesis instead of continuing to consider alternatives — more common than actual missing knowledge.
  Same URL, citing Graber, Franklin & Gordon (2005): *"failure to continue considering reasonable alternatives after an initial diagnosis was reached" [is] the single most common cognitive cause, while faulty knowledge was uncommon.* This source explicitly imports the finding to LLM-assisted debugging as the rationale for forcing structured, layer-ordered hypothesis enumeration instead of free-form "list likely causes" prompting, and separately warns that unstructured "list the possible causes" LLM prompts inherit documented **diversity collapse** (citing a 2026 LLM-hypothesis-generation paper referenced as "Wang et al., 2026" within that source — not independently verified in this session).

- **Claim:** In LLM multi-agent-system debugging specifically, a framework (DoVer) explicitly generates *multiple* competing failure hypotheses and validates/refutes each via intervention (edit the agent's message/plan and re-run), rather than trusting a single log-based attribution — because the paper found multiple genuinely distinct interventions can independently repair the same failed task, meaning single-cause attribution is often "ill-posed."
  URL: https://arxiv.org/pdf/2512.06749 ("DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems"), 2026-02-03. Quote: *"log-only debugging lacks validation, producing untested hypotheses, and... single-step or single-agent attribution is often ill-posed, as we find that multiple distinct interventions can independently repair the failed task."* Results: flips 18-28% of failed trials into successes and validates/refutes 30-60% of failure hypotheses.

- **Claim:** For microservice performance debugging, a system (AgentDebug) explicitly rejects "optimize for one best root cause" and instead maintains a **diverse, Pareto-optimal set of hypotheses** as a persistent "Reasoning Surface" — outperforming a single-answer baseline (DeLag) on several stress configurations (e.g. F1 0.776 vs 0.769, 0.827 vs 0.797).
  URL: https://threadslab.org/research-publications/papers/rethinking-performance-debugging-from-optimization-to-collaborative-reasoning, 2026-07-05. Quote: *"the paper argues that microservice performance debugging should preserve and empirically challenge multiple evidence-grounded explanations under uncertainty instead of optimizing for one opaque root-cause answer."*

- **Claim:** Bug-localization and hardware-verification debugging agents (CogniGent; FVDebug) both explicitly generate and retain *multiple* competing hypotheses with individual confidence scores rather than committing early, and FVDebug reports this design choice contributes measurably to hypothesis-quality metrics (ablation "FVDebug w/o Rover" — which explores fewer competing hypothesis narratives — drops Quality@Best from 0.713 to 0.300 on one benchmark).
  URL: https://arxiv.org/pdf/2601.12522 (CogniGent), 2026-01-21; URL: https://doi.org/10.48550/arxiv.2510.15906 (FVDebug), 2025-10-21.

- **Practical prompting pattern found (production-oriented, not academic):** an explicit "Hypothesis-Evidence-Verification" loop — force the agent to write a Mutually-Exclusive-Collectively-Exhaustive (MECE) hypothesis list *before* touching any tool, specify the exact evidence that would confirm/refute each one, and forbid confirming any hypothesis until at least two alternatives have been explicitly ruled out with data ("negative space exploration").
  URL: https://sudshekhar.com/blog/prompting-for-root-cause-analysis-getting-an-ai-agent-to-investigate-instead-of-guess, 2026-09-05.

**Implication for research-council:** the same "Generation → Reflection → Ranking" structure and the same "no evidence = unverified" discipline the council already applies to scientific hypotheses is independently reinvented, with harder outcome-based evidence, in the debugging/root-cause literature. If research-council is ever pointed at a debugging/RCA-style problem, this literature suggests it will need a MECE-style enumeration step (cover categories/layers, not just "generate N ideas") in addition to the curiosity protocol's repeat/vary/boundary framing, since free-form idea generation is specifically documented to under-enumerate the space and collapse to the same few "obvious" causes.

### R2.3 — The Ideation-Execution Gap paper: which idea features predicted execution success?

Direct fetch of the arXiv abstract page did not surface this (abstract-only); a detailed paper-note write-up did:

- **Quantitative gap by metric:** Human ideas showed almost no drop in novelty, excitement, or effectiveness from ideation to execution; AI ideas dropped by ~1.049 (novelty), ~1.760 (excitement), ~1.879 (effectiveness) points, and overall score dropped ~1.976 points; the gap for AI ideas was significantly larger than for human ideas (FDR-corrected p<0.05 across four shared metrics).
  URL: https://en.papernotes.org/ICLR2026/llm_evaluation/the_ideation-execution_gap_execution_outcomes_of_llm-generated_versus_human_rese, 2026-05-08.

- **Idea features that predicted a bad execution outcome, per manual categorization of reviewer free-text justifications into 10 factors** (novelty/motivation, impact, method flaws, experiment design, baseline comparison, ablation/analysis, feasibility/resource, empirical performance, generalizability/scope, **missing details/writing**): the two factors specifically called out as drivers of the AI-idea drop were:
  1. **Idea vagueness / missing implementation detail** — at least one project was terminated outright because "the original idea was too vague, requiring the implementer to invent the core method."
  2. **Silently downgraded human-evaluation plans** — ideas whose excitement score depended on a proposed human study (e.g., recruiting native speakers) had that study swapped for cheaper LLM-as-judge evaluation during execution, undermining the result; this affected 6 of 43 ideas, though an ablation excluding these 6 showed the AI-idea score drop still held even without them — meaning this factor contributes to, but does not fully explain, the gap.
  Same URL, 2026-05-08.
  **Implication:** the single most execution-robust idea property found in this analysis is *specificity of the implementation plan*, not novelty or excitement — a hypothesis with a vague method is exactly the kind of thing a "more novel, less feasible" LLM idea tends to produce, and is exactly the kind of thing a Reflection/Ranking step could check for directly (e.g., "does this hypothesis specify a concrete, executable test, or only a direction?").

### R2.4 — Keeping hypotheses falsifiable (each with a predicted observation)

Three independent, purpose-built frameworks converge on the same recipe: state the falsifying observation *before* running any experiment, and make failure structurally revise the hypothesis rather than being explained away.

- **POPPER** (explicitly named after Karl Popper's falsification principle): an Experiment Design Agent identifies a *measurable implication (sub-hypothesis)* of the main hypothesis with an explicit null/alternative, and an Experiment Execution Agent tests it, producing a p-value that is converted to an e-value so evidence can be validly accumulated across multiple, potentially dependent, sequential tests while controlling Type-I error.
  URL: https://arxiv.org/html/2502.09858 ("Automated Hypothesis Validation with Agentic Sequential Falsifications"), 2025-02-17. Quote: *"this sub-hypothesis needs to be falsifiable with clear null and alternative definitions... POPPER systematically challenges hypotheses by sequentially testing their measurable implications."* Self-refinement of each sub-hypothesis proposal is explicitly checked against three criteria: **novelty** (not redundant with prior sub-hypotheses tested), **implementability**, and **logical relevance** (does the sub-hypothesis actually follow from the main hypothesis).

- **EvoSCM**: forces the agent to commit to a concrete, quantitative predicted outcome for every hypothesis *before* an intervention is run ("Prediction... recorded prior to experimentation, ensuring that each hypothesis stakes a concrete, testable claim on the experimental outcome. This commitment is essential: it prevents post-hoc rationalization"), then mechanically traces any prediction-observation discrepancy back to a specific structural or parametric part of the hypothesis for targeted revision — maintaining a *population* of competing falsifiable hypotheses rather than one, specifically "to prevent the agent from becoming 'trapped' by a single incorrect idea early in the process."
  URL: https://arxiv.org/html/2609.01526, 2026-09-02. On DiscoverPhysics benchmark, this reduced forward-prediction MSE by two orders of magnitude vs. standard prompting on a GPT-5.5 base model.

- **FirstResearch**: proposes a "Research Question Certificate" required for every candidate hypothesis, which must include a **falsifiable hypothesis, a minimal decisive test, expected observations, and a failure update rule** — explicitly designed to catch the failure mode of "a weak research question [that] can be implemented and written up, yet still fail scientifically because it tests an underspecified gap, a vague improvement claim, or a metric without a clear falsifying observation."
  URL: https://arxiv.org/html/2607.05682, 2026-07-08. A "novelty-aware gate" repairs certificates that lack a clear rejecting observation before experiment design proceeds; worked example: a broad question ("when should an agent discover vs. compose skills?") is sharpened into a specific threshold claim ("critical overlap ratio above which composition underperforms discovery") with a concrete rejecting observation.

- **Convergent recipe for research-council's evidence template:** all three sources independently arrive at the same four required fields for a hypothesis to count as falsifiable: (1) the claim itself, (2) a specific test/intervention, (3) the specific observation that would count as support, and (4) the specific observation that would count as refutation/what to do if that observation occurs. None of the three treat "this seems plausible" or a bare LLM confidence score as sufficient — POPPER and EvoSCM both explicitly guard against exactly that (POPPER via statistically valid p/e-values instead of LLM judgment; EvoSCM via "this commitment is essential: it prevents post-hoc rationalization").

### R2.5 — arXiv ID verification (fetched every ID cited in this file)

All 22 distinct arXiv IDs cited in Round 1 and Round 2 of this file were fetched directly at `https://arxiv.org/abs/<id>` this session and confirmed to **resolve with a title matching the citation**: 2409.04109, 2506.20803, 2601.14525, 2607.14118, 2510.01171, 2606.21891, 2605.11258, 2510.22312, 2602.20408, 2510.15568, 2602.13769, 2608.08958, 2507.00310, 2506.22026, 2404.07738, 2506.12937, 2310.12952, 2511.10547, 2602.14682, 2601.21339, 2407.01082, 2502.18864.

**No broken or mismatched arXiv IDs found.** One minor discrepancy noted (not a resolution failure): 2602.13769's canonical arXiv title is *"OR-Agent: Bridging Evolutionary Search and Structured Research for **Automated Algorithm Discovery**"* — a subtitle variant ("...for Automated **Heuristic** Design") appeared in some secondary-source page titles/snippets during search but not on the arXiv abstract page itself; treat "Algorithm Discovery" as authoritative.
The Nature/Co-Scientist citation (nature.com/articles/s41586-026-10644-y, cross-checked against arxiv.org/abs/2502.18864) also resolved correctly, though the raw Nature PDF fetch returned unparsed layout text rather than clean prose, so any AML compound-specific numbers in R2.1 above are sourced from secondary summaries of that paper, not a direct clean read of the primary PDF — flagged accordingly above.

---

## Round 3 — Adversarial verification of the 3 most load-bearing claims (primary-source fetch)

### (a) Verbalized Sampling "1.6-2.1x diversity gain" — **VERIFIED**
Fetched primary source directly: https://arxiv.org/abs/2510.01171. Confirmed exact figure and scope: *"Diversity gain figure: 1.6-2.1x increase in diversity over direct prompting. Task/domain: Creative writing (specifically poems, stories, and jokes). Metric: Diversity."* Condition/caveat confirmed as originally stated: this figure is specific to the creative-writing tasks (poems/stories/jokes), not a claim about all task types in the paper (dialogue simulation, QA, and synthetic data generation are evaluated with different metrics/gains in the same paper, not this specific 1.6-2.1x number). Model-specific breakdown not given in the abstract-level fetch. **No discrepancy found** between what was cited in Round 1 and the primary source.

### (b) Analogical reasoning "1.6% → 50%+ novel-solution rate" (arXiv 2605.11258) — **VERIFIED**
Fetched primary source directly: https://arxiv.org/abs/2605.11258. Confirmed exact figure and scope: *"Novel-solution-rate figures: Generates novel solutions over 50% of the time for the analogical reasoning (AR) method, compared to as little as 1.6% for baselines. Task/dataset: Open-ended solution generation task in complex fields like biomedicine."* This is a direct baseline-vs-AR-method comparison on the paper's own open-ended-solution-generation benchmark, not an inferred/derived number. **No discrepancy found.**

### (c) Alaboudi & LaToza "potential hypotheses ~6x more helpful than fault locations" — **PARTIAL / caveat found**
Fetched the primary paper directly (found via search, then fetched in full): https://arxiv.org/html/2005.13652v1 ("Using Hypotheses as a Debugging Aid," Alaboudi & LaToza, VL/HCC 2020 — the arXiv version, not a secondary summary). The **"6x" figure is real and correctly sourced**, but the precise comparison group differs from how it was worded in Round 2:
- Primary paper's own statistic: *"We found that participants who received potential debugging hypotheses were six times more likely to fix the fault compared to the other groups (p = 0.0388)"* — odds ratio 6.24 (SE 0.88, p=0.03).
- **The "other groups" in that statistic pools BOTH the control condition AND the fault-locations condition together** — the paper does not report a separate, isolated odds ratio for "hypotheses vs. fault-locations alone." Separately, the paper states fault locations "did not significantly help developers to formulate a correct hypothesis nor enable the developer to debug any more successfully" (i.e., statistically indistinguishable from control) — which is why treating "6x vs. other groups" and "6x vs. fault-locations" as roughly interchangeable is a reasonable inference, but it is an **inference, not a number the primary paper states directly**.
- Additional nuance found: LaToza's own later teaching slide (https://people.cs.gmu.edu/~tlatoza/teaching/cs695f23/lecture13.pdf, 2023-11-30, citing this same paper) states *"Providing generalized debugging hypotheses > 16x more likely to successfully fix a fault"* and separately *">5x more likely to succeed"* for having a correct hypothesis early — i.e. there are at least two different multiplier figures (6x and >16x) attached to different specific conditions ("potential hypotheses" vs. "generalized hypotheses") in material connected to this same study, and Round 2's file text picked the 6x one without specifying it's a "vs. other groups pooled" comparison rather than a clean head-to-head "vs. fault-locations only" comparison.
- **Verdict: the underlying finding is real, correctly attributed, and the direction/magnitude (~6x) is accurate — but the Round 2 phrasing "helped roughly six times as much as supplying candidate fault locations" overstates precision by implying a direct pairwise comparison that the primary paper does not isolate.** Corrected phrasing: *developers given potential hypotheses were ~6x more likely to succeed than developers in the pooled control+fault-locations groups (odds ratio 6.24, p=0.03); fault locations alone showed no statistically significant benefit over control.*

---

## (d) Open Questions

1. Does the "ideation-execution gap" (Si et al. 2506.20803) generalize outside NLP research ideas to the kinds of harder, less code-executable problems research-council is likely used for (e.g., business, policy, scientific literature synthesis without a runnable experiment)? All the hard evidence on execution outcomes is NLP/ML-research specific.
2. Is there a validated technique for combining Verbalized Sampling *with* explicit dedup/Proximity clustering in one pipeline, or do they interact (e.g., does forcing tail-probability sampling just increase near-duplicate low-quality noise that Proximity then has to filter out more aggressively)? Not directly tested in any source found this session.
3. How much of the "ordinary personas > celebrity personas" and "CoT-diversify > temperature" findings (2602.20408) is specific to short creative/idea-title tasks vs. longer, more technical hypothesis statements of the kind research-council's Generation role produces? The paper's tasks were general ideation, not necessarily research-grade hypotheses with evidence requirements.
4. No evidence was found this session specifically measuring diversity/novelty trade-offs for a *blinded pairwise Elo* ranking step itself (as opposed to hypothesis generation) — Co-Scientist uses Elo but the retrieved sources don't isolate how much the Elo tournament design itself helps vs. hurts diversity of what survives to the final report.
5. The Vendi-Score human-agreement study (2511.10547) was done on image generation, not text/hypothesis diversity — its ~65-80% agreement number may not transfer directly to a Vendi Score computed over embedded research hypotheses; no text-hypothesis-specific human-agreement number was found this session.
