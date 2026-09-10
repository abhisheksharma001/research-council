# research-council

<img src="assets/mascot/pup.gif" width="256" height="192" alt="Pixel dog sniffs the ground, digs, finds a bone and drops it on a findings page" align="right">

A research workflow for tool-capable agent apps. Give it a hard problem; get competing
explanations, evidence-linked findings, honest unknowns, and a practical next-step brief.
It can also investigate its own weaknesses before proposing changes.

## Install

Python 3.11+, standard library only. No pip installs or provider API key required by the scripts.
The host supplies the model and research tools; its usage may still be billed.

```sh
git clone https://github.com/abhisheksharma001/research-council
claude --plugin-dir ./research-council
```

**Claude Code:** run `/research-council <your problem>` after loading the plugin.

**Devin:** the two loaders in `.devin/skills/` delegate research-council and self-improve
to the canonical files under `skills/`. Their format and paths are tested. This active session
did not discover newly written loaders; use a fresh session or load the canonical skill by
its absolute path. Automatic discovery is a separate host check.

**Other Agent Skills hosts:** export a self-contained research skill. From this checkout,
replace the example parent with an existing skill directory; the final research-council
folder must not already exist:

```sh
python3 scripts/harness.py export --destination /existing/skill-directory/research-council
```

The export contains the procedure, references, roles, and Python helpers. It does not copy
research runs, retained-library state, private data, tests, or host configuration. It can
move without depending on the original clone. Self-improvement and library promotion stay
in the full checkout. The promotion module is included only as a retrieval dependency;
the portable launcher does not expose the promotion command.

Loading a SKILL.md is not the same as verifying a host integration. Codex and other skill
loaders can consume this format, but must supply the required tools and permissions and be
checked with a real run before being called supported deployments.

## Start with a real problem

For example:

> Investigate why our webhook sometimes processes the same order twice. Compare plausible
> explanations, show the evidence and unknowns, and give the builder a testable next step.
> Ask me for the run limits and success criteria before starting.

The skill asks for four limits: minutes, actions, subagent launches, and estimated dollars.
It also asks how the user will know the result is useful. A budget from an earlier run is
never reused as fresh approval. One-command questions and simple edits skip the council.

To check paths without starting a run or inventing a budget:

```sh
python3 scripts/harness.py context --workspace /absolute/target-project
```

The JSON distinguishes the runtime checkout from the target project. It verifies Python
and local resources only; it explicitly leaves model availability, source access, worker
permissions, provider billing, and sandbox availability unverified. Helpers can be called
by absolute path or through `scripts/harness.py run`; their stdin and exit codes are preserved.

## Built for frontier models

The workflow is intended for an AGI-class model, but capability must be checked in the host.
A model label does not grant browsing, shell access, independent workers, or a sandbox.
The scripts check record structure and lifecycle rules; the host enforces tool permissions
and actual provider spending. File hashes detect changes after the fact, not prevent them.

For **GPT-6 Astra**, use that model in a host that offers it. The procedure follows the useful
parts of [OpenAI's model guidance](https://developers.openai.com/api/docs/guides/latest-model)
and the [guide supplied for this upgrade](https://promptessor.com/blog/gpt-6-astra-prompting-guide):
clear outcomes, bounded autonomy, explicit source authority, selective context, purposeful
delegation, meaningful verification, and stop conditions.

If building an API adapter later, OpenAI documents the model id as `gpt-6-astra`; tool calling
requires the Responses API, and reasoning effort belongs in host/API configuration. No API
runner or paid model evaluation is included here. A ChatGPT conversation without the required
execution tools can use the method as guidance, but cannot claim these script checks ran.

## How it works

1. Triage the problem and freeze the user's goal, success criteria, and budget.
2. Retrieve applicable retained procedures when a library is available.
3. Investigate competing explanations and record exact source excerpts and locators.
4. Use separate council roles to generate, challenge, compare, and review the evidence.
5. Stop within the limits and render the reports from records, not a fresh invented summary.

Outputs live under `AGI_Research/runs/<goal_id>/` in the target project:

- FINDINGS.md: evidence-backed claims, disputed and unverified items, limitations and spend.
- HANDOFF.md: the goal, next hypothesis to investigate, acceptance criteria and must-not list.

A comparison rating schedules investigation; it does not establish truth or authorize a build.
Downloaded code is never executed without a declared sandbox. Only `scripts/promote.py` can
commit a library version, after all retained task contracts pass; self-runs and exported skills
have no automatic promotion authority.

## Paperclip and other task systems

The intended boundary is a reusable research procedure and traceable handoff, not a second
agent-management platform. Paperclip-specific wiring is deferred until its runtime and task
contract are selected. No live Paperclip connection, task write, or end-to-end compatibility
is claimed. The S-34 structured handoff is the next local integration step.

## Self-improvement and verification

Run `/self-improve` in the full checkout, supply a fresh budget and success criterion, and
review its proposed steps. It never expands the scope, spends on external APIs, promotes,
or merges without the existing typed confirmation. A better-looking prompt is not proof of
better research: changes need failures that can be reproduced and meaningful regression tests.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate_skill.py skills/research-council   # OK
python3 scripts/validate_skill.py skills/self-improve
python3 scripts/validate_skill.py .devin/skills/research-council
python3 scripts/validate_skill.py .devin/skills/self-improve
```

Status: S-1..S-31 are the merged baseline. S-32..S-34 are the local portability upgrade,
tracked in `docs/spec-v1.md`; they are not a release or a live provider benchmark.
The initial runs and the 2026-09-10 adapted self-assessment are recorded in
`docs/runs/2026-09-09-first-run.md` and `docs/runs/2026-09-09-self-run.md`.

Format: [Agent Skills specification](https://agentskills.io/specification).
Licence: MIT (`LICENSE`). Mascot: `assets/mascot/` (original pixel design, drawn from code).
