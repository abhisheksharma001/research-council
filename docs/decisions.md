# Decisions

| id | date | decision | why |
|---|---|---|---|
| D-01 | 2026-09-09 | Portable plugin; v1 targets Claude Code only; SKILL.md per Agent Skills spec so Codex/Cursor/Gemini adapters need no rewrite | Abhishek: "people should be able to run it on Claude, Cursor, Codex, any of it"; smallest version first |
| D-02 | 2026-09-09 | Any problem accepted; triage refuses small ones with a reason | "for smaller ones we don't want to use it" |
| D-03 | 2026-09-09 | Budget = per-run block set by user (minutes, actions, subagents, usd_estimate); journal shows running spend | "spending should be dynamic, expose it to people" |
| D-04 | 2026-09-09 | Output folder `AGI_Research/runs/<goal_id>/` with FINDINGS.md (plain English) and HANDOFF.md (coding-agent brief) | "create a folder called AGI research, findings properly explained, hand over to coding agent" |
| D-05 | 2026-09-09 | Curiosity ships in v1 as explicit strategy files; first = fire protocol (SPARK, REPEAT, VARY, BOUNDARY, COMBINE, NAME); reward only on improved prediction | Abhishek's fire story; Schmidhuber App. A.5; 2604.17609 shows LLMs lack this drive natively |
| D-06 | 2026-09-09 | Gate-first build order: library + gate before council before curiosity math | Lenny's 2026-04-14 (deterministic for auditability first); Beel 42% failures; verification-gap survey 2608.05179 |
| D-07 | 2026-09-09 | Evaluator changes are reviewed changes with their own regression suite, not frozen forever | Red Queen Gödel Machine 2606.26294 argues frozen evaluators get overfit |
| D-08 | 2026-09-09 | Standard-library Python only in scripts | Must run inside any harness without install step |
| D-09 | 2026-09-09 | Self-improvement is a second skill in this repo that runs the council on the repo itself and ends in proposed register steps; it never merges without the typed line `merge S-<n> confirmed`, never edits the invariants, never spends, never reads outside the checkout | Abhishek: "run it on yourself, with a self-improving skill so I can ask any updated AGI model"; grill 2026-09-09 (scope = plugin only, form = second skill, merge only behind typed confirmation); Sakana self-relaunch is the failure to avoid |
