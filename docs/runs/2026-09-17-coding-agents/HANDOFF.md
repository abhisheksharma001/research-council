# Handoff for goal 80e03afb-e569-4dac-86fa-3096945331ac (revision 1)

## Goal

A FINDINGS.md that lists, with dated public sources, where current coding agents fall short of experienced engineers, what they still cannot do, how and how often they hallucinate in code, and which fixes have measured effect; and a HANDOFF.md that a coding agent can build a code-writer-council skill from, in this repo, that runs fast enough for everyday code writing.

Scope: Public web pages, papers and repositories reachable through the keenable MCP tools, dated 2025-01-01 or later where possible; this repository's own files. No client data, no private workspaces, no live systems.

## Chosen approach

Elo is a rating moved only by head-to-head comparisons; it orders what to investigate, it does not verify anything.

Chosen: H5 BAML's runtime cannot be used from this stdlib-only, no-pip plugin because its parser ships only as a compiled native extension via pip or npm, so a code-writer-council can adopt only the schema-aligned-parsing idea, reimplemented in the Python standard library.

Beat: H3 The largest remaining gap is judgment that no tool loop fixes: scoping the task, asking when ambiguous, knowing when to stop, and design taste; agents produce more code of lower review quality than experienced engineers.

```
id        elo  cmp status   statement
H5       1208    1 open     BAML's runtime cannot be used from this stdlib-only, no-pip plugin bec
H1       1200    1 open     Coding agents fall short of experienced engineers mainly because they 
H2       1200    1 stopped  Coding agents fall short mainly on long-horizon and repo-wide work: th
H6       1200    0 open     A role-separated plan/write/review loop (separate planner, writer, and
H7       1200    0 open     At fixed cost, a single strong agent with a test-execution loop matche
H8       1200    0 open     Coding-agent success on everyday tasks plateaus within a bounded numbe
H9       1200    0 open     Package hallucination is a measured, recurring code-hallucination clas
H3       1200    2 open     The largest remaining gap is judgment that no tool loop fixes: scoping
H4       1192    1 stopped  Structured-output tooling such as BAML's schema-aligned parsing materi
```

## Acceptance

One sentence per success criterion, in the form WHEN ... THEN ... SHALL.

WHEN Number of evidence-backed claims per sub-topic (where agents lack, what they still cannot do that an experienced code writer can, hallucination, fixes including BAML), each citing a public source dated 2025 or later is measured by scripts/claims.py list against evidence.jsonl source dates in the run folder, read-only THEN the result SHALL satisfy: Every sub-topic has at least three evidence-backed claims from sources dated 2025 or later, and FINDINGS.md reports zero unverified claims as findings ('detailed and in depth research on each thing, as per the latest sources').

WHEN Hallucination coverage: named hallucination classes in code with a measured rate or count and the source that measured it is measured by scripts/claims.py list filtered to claims whose scope names hallucination in the run folder, read-only THEN the result SHALL satisfy: At least one class of code hallucination is named with a measured rate and its source ('agent hallucination thing also should cover with it').

WHEN Whether the chosen approach in HANDOFF.md bounds a single code-writing run in time and actions, separate from this research run's budget is measured by Abhishek reading HANDOFF.md in the run folder THEN the result SHALL satisfy: The chosen approach names a per-task cap and a triage exit for small edits ('every one can rely on at the same point of time, it shouldn't be the in depth research timing').

## Files likely touched

- CLAUDE.md
- README.md

## Must not

- Any paid API call or pip install.
- Editing skills/, scripts/, agents/, docs/ or tests/ during the run; building the code-writer-council is a later step, not this run.
- Reading or writing any client workspace or client data.
- Editing FINDINGS.md or HANDOFF.md by hand.
