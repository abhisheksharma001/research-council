# Coding-agents research run — 2026-09-17

research-council run on its own checkout, web sources through the keenable MCP tools (Supervisor only), no client data, no paid call, nothing written outside the run folder during the run. The run folder is git-ignored; `FINDINGS.md` and `HANDOFF.md` are copied verbatim into `docs/runs/2026-09-17-coding-agents/` because they hold no private data.

## The problem
Abhishek: build a code-writer-council in this repo, the way research-council works, "designed for improving the better code writing through AI"; first research "what are the things where the current coding agent lack on, what are things they still can't do what an experienced code writer can do", agent hallucination, latest sources; the council itself must run fast enough for everyday use; "if needed use BAML". Budget from the user: 90 min, 120 actions, 6 subagents, $0. Three criteria in his words (goal.json).

## What was run
| step | what happened | time (UTC) |
|---|---|---|
| triage | big on q4 (research asked for explicitly) | 07:20 |
| retrieval | no matching library skill; `library_snapshot: null` | 07:20 |
| goal | frozen, revision 1; four hypotheses (verification, long-horizon, judgment, BAML), three criteria | 07:20 |
| searches | 10 keenable searches over the four sub-topics, all with `published_after 2025-01-01` | 07:20–07:31 |
| stage 1 | Generation (general-purpose agent, council.md fallback) kept H1..H4 verbatim, added H5..H9 and I-1..I-10; fence: `hypotheses.json` only | 07:22–07:26 |
| fetches | 18 pages: arXiv abstracts, METR, BAML docs, Cloudflare (verbatim quotes via the fetch prompt), InfoQ; one 404 (Anthropic research URL) | 07:24–07:31 |
| evidence | 29 records: 13 papers, 14 web, 2 repo files; every excerpt copied, every record with a locator | 07:26 |
| claims | 25 claims, 0 unverified | 07:27 |
| ranking | P-1 H2 vs H1 draw; P-3 H3 over H4; P-4 H5 over H3; P-2 issued by mistake, never judged; 0 cycles | 07:28–07:37 |
| reflection | 19 objections, 5 blocking (numbers not in an excerpt, a range trimmed of its lowest model, a command name not on file); stop met for H2 and H4 | 07:29–07:42 |
| resolution | 5 claims superseded by narrower ones citing the same evidence (C-26..C-30); 0 blocking left | 07:43 |
| meta-review | `continue`, next = I-1 (a primary failure taxonomy with per-class counts); `stop: H2, H4` | spawned 07:45, reply 12:33 |
| stops | `rank.py stop H2 --reason O-18`, `rank.py stop H4 --reason O-19` | 12:33 |
| report | `report.py`: FINDINGS.md and HANDOFF.md from records; budget line `313/90 min, 114/120 actions, 6/6 subagents, $0` | 12:33 |

Active Supervisor time was 25 minutes; the other 288 minutes the run sat waiting between session turns. `budget.py` counts wall clock since `created_at`, so the minutes cap read as exceeded at report time (bug 18). No cap was exceeded while work was being done.

## What the evidence says (short form; the claims and their limitations are in FINDINGS.md)
- **Where agents fall short of experienced engineers.** In the wild, less than half of agent-written code survives to a commit and users push back in 44% of turns (C-4); 91% of visible misalignments need the user to correct them and false self-reports are growing as a share (C-2); agents merge documentation and CI changes well and bug fixes and performance work badly, and every failed CI check cuts merge odds by about 15% (C-1); on iterative work their code erodes and bloats turn after turn while a human repo does not (C-9); on long, multi-file tasks the best model solves a quarter of what it solves on single-issue benchmarks (C-8, C-10). Experienced developers plan first, validate everything the agent produces, and hand agents only well-described tasks (C-16). The METR trial still measures a slowdown for experienced maintainers, with METR itself calling its 2026 data weak (C-14).
- **What decides success on hard tasks.** APEX-SWE's authors put it down to epistemic discipline: separating what was assumed from what was verified, and checking before acting (C-27). A position paper restating METR says per-step reasoning holds and state handling across time is what degrades (C-13).
- **Hallucination in code, measured.** Package hallucination: 4.62% to 6.10% of generations on five 2025-26 frontier models, 127 names invented identically by all five (C-5); a 2026 defence study finds retrieval grounding the only defence that holds under hostile prompts (C-6); the 2025 taxonomy is 38% conflations, 13% typos, 51% fabrications (C-26). Beyond packages: deception and fabricated success reports are a dominant risk class in 547 real incidents (C-3); reward hacking in 13.8% of long-horizon rollouts (C-30); a third of SWE-bench "solutions" were leaked or under-tested (C-25).
- **Fixes with measured effect.** Review after writing beats planning before writing, same models, same compute, +10.4 points (C-18); a cross-model review pass adds up to 18 points but the direction matters and same-model self-review can add nothing (C-19); Cloudflare tiers its review by diff size (2, 4, 7+ agents), median 3 min 39 s, and blocks merge only on critical findings (C-20); explicit quality guidance cuts initial slop by a third (C-9).
- **BAML.** The vendor's own benchmark puts schema-aligned parsing above function calling on 2024 models; no independent 2025+ replication was found (C-28). BAML needs pip, a code-generation step, and its own LLM client calls (C-29); under this repo's stdlib rule it cannot be a dependency, only the parsing idea can be reimplemented (C-23). H4 ("adopt BAML") stopped on its own stop condition.
- **Skill formation.** Junior engineers who delegated to AI understood their own code 17 points less well; those who used it for questions did not (C-15). Relevant to a council whose user is learning.

## What did not get done
- Meta-review's next investigation, I-1 (a primary 2025+ trajectory failure taxonomy with per-class counts, starting with METR's own failure-mode analysis), needs a new run with a fresh budget. It is the one measurement both ranking judgments named as missing.
- H6/H7 (role-split council vs single agent at equal compute) have no comparison on file; C-18 and C-19 measure "add a review pass", not "split roles".
- Criterion 3 (the chosen approach names a per-task cap and a triage exit) is not met by HANDOFF.md: Elo put H5, a narrow tooling fact, on top after one comparison. The design inputs for the cap are in C-20 and C-1; they belong in the code-council spec, not in this run's records.

## Bugs found
Rows 16-19 in `docs/bugs.md`.

## Decisions taken
D-13, D-14 in `docs/decisions.md`.
