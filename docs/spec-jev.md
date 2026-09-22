# jev decision seam — feature spec

Grilled 2026-09-21. Abhishek: "use it and see how you can implement it to get its max
potential, and making the current whole system much more better in every possible way, and use
the fallback (with the llm and baml) if needed", then "make it as per this" (the working
standard). Answers: only synthetic cases and public evidence records may leave the machine;
nothing from a client workspace, ever; a paid call is allowed only through one metered script
and only where the user's dollar cap allows it (D-16); the seam ships in shadow mode and gates
nothing until a committed calibration report says it may.

Jev is a decision model from TypeSafe AI. It answers typed questions about a piece of text and
returns a probability with each answer. It cannot write, count, compare dates, or reason in
steps, and it can be confidently wrong. The method used here is the `jev` skill installed at
`~/.claude/skills/jev`, whose evidence base is this plugin's own research run of 2026-09-21
(run 65a47056, 195 evidence records, in the jev skill's own checkout).

n8n analogy: one HTTP Request node behind a Switch, with the Switch's thresholds in a Set node,
and a third branch that does exactly what the workflow did before.

## Today
A research run's Supervisor writes a claim, names the evidence ids it rests on, and moves on.
`scripts/claims.py` checks that those ids exist; nothing checks that the excerpts behind them
say what the claim says. That check happens one council round later, when the Reflection role
reads the whole file and writes objections. Across the five readable runs on this machine,
Reflection raised 62 objections on 191 claims: 25 `provenance` (the excerpt does not state the
claim), 11 `scope` (the claim is wider than its evidence), 11 `type` (an inference labelled as
observed), 12 `counterexample`, 3 `stop`. Every one of those is a claim the Supervisor believed
when it wrote it.

Source strength has the same shape. Whether a page is the vendor's own, a partner's, or
independent is recorded as free text in a claim's `limitations` field. In the 2026-09-21 run the
meta-review named this the single most repeated weakness, listing six records whose strength was
recorded wrongly, plus one private probe recorded as public.

## Instead
One script, scripts/judge.py, asks a fixed set of literal yes/no questions about a claim and the
excerpts it cites, and about a page before it becomes an evidence record. It prints one line and
records one JSON line. In shadow mode, which is where it ships, nothing downstream changes: the
run proceeds exactly as it does today and the answers accumulate as data. Once a calibration on
our own labelled cases has met a bar written before the run, gate mode can refuse to let a claim
be recorded over a confident "no" — and only that direction. A "yes" verifies nothing, ever.

The roles never see any of it. Jev's answers stay out of every role packet and out of the fence
comparison, so Reflection, Ranking and Meta-review keep working on the same inputs they have
today, uninfluenced by a first opinion.

## Who runs this
Same as `## Who runs this` in `docs/spec-v1.md`: an AGI-class model in a tool-capable host. One
difference: the judge is not a role and not a model the Supervisor prompts. It is a script that
calls a fixed API with a fixed question set, so its answer cannot be argued with, only measured.

## Evidence this design rests on
| design rule | why |
|---|---|
| Four atomic questions, combined in code, never one broad question | One "is this phishing?" question scored 62.6% and 89.4% in two independent tests; the same judgement decomposed into five atomic questions weighted in code scored 95% |
| Questions mirror the Reflection rubric one to one | `agents/reflection.md` already defines provenance, type, scope and counterexample; sharing the definition is what makes the objections usable as labels |
| Numbers are checked in code before any call | Arithmetic, counting and numeric comparison are vendor-documented weak spots; the jev skill's own probe put numeric-inference claims at 0.26-0.36 while textual support scored 0.81-0.98 |
| No threshold is ever 0.5 by default | Answers jitter about 0.02 between identical runs, so 0.5 is a knife edge; thresholds come from calibration on our cases and are reported on a held-out split |
| Confidence is not correctness; the middle band goes to the fallback | One independent test found Jev right 64% of the time when it reported 80-95% |
| Shadow before gating; a "yes" never verifies | CLAUDE.md invariant 2: a claim without an evidence record is unverified. A probability is not an evidence record |
| Rules and deny-lists first, Jev for the remainder | The vendor documents that state is data and adversarial text can move an answer; the jev skill's deterministic fit check returns GO WITH GUARDS for both batteries and names rules-first as the first pattern |
| The model id is pinned | `jev-latest` and `jev-preview` both resolved to the dated id on 2026-09-21, but aliases move and a moved alias makes tuned thresholds silently stale |

## Acceptance
WHEN a research run records a claim in a workspace that has opted in, and a Jev key is present,
and the run's dollar cap allows it THEN scripts/judge.py SHALL print one line naming the claim
and one of yes, no, unsure or skipped with its reason, SHALL record the probabilities and the
measured cost as one `judge` journal line and one judge.jsonl line, and SHALL leave every other
file in the run folder byte-identical; and WHEN the workspace has not opted in, or no key is set,
or the dollar cap is zero THEN it SHALL print a skipped line, exit 0, write nothing, and the run
SHALL proceed exactly as it does today.

## Rules that never change (this seam)
1. A Jev answer is data. It never changes the goal, the budget, the evaluator, the library, or
   any recorded claim or evidence record. (CLAUDE.md invariant 3.)
2. A "yes" verifies nothing. Only a confident "no", and only in gate mode, changes what the
   Supervisor does, and what it does is fix the record or its evidence.
3. Nothing but public records and synthetic cases leaves the machine. A record whose
   `access_scope` is not `public` stops the call before any request body is built. No client
   workspace opts in.
4. Every call is metered: one journal line of kind `judge` carrying the measured cost, written
   before the judge record, so a call that happened is never unlogged. (CLAUDE.md invariant 4.)
5. Thresholds come from a calibration on labelled cases, reported on a held-out split with n.
   No script defines a threshold, and `fitted: None` means shadow mode whatever the flags say.
6. The roles never see judge output. It stays out of every council packet and out of the fence.
7. The seam is one file with one network call site; a second adapter is how the plugin leaves,
   not a rewrite.

## Deliberately not here
- Replacing the Reflection, Ranking or Meta-review roles. Pairwise judging of complex outputs is
  a measured bad fit, and a rating never verifies a claim (`skills/research-council/SKILL.md`).
- Any judgement that turns on arithmetic, counting or a date comparison. Those stay in code.
- Triage's five booleans. They fit, but five decisions per run is not worth a dependency.
- The code-writer-council batteries (finding severity, expected_small). Parked as S-56 until the
  dry run of `docs/spec-code-council.md` S-44 has produced review files to label.
- BAML as a dependency (D-13). Its one useful idea, repairing a loosely formatted reply against a
  declared schema, is reimplemented in the standard library as S-57 if a step needs it.
- Any second provider, any gateway, any client-facing use.

## Layout (planned)
```
scripts/judge.py                                  the seam: batteries, adapters, egress guard, decision
skills/research-council/references/judge.md       what the Supervisor runs and what each line means
.research-council/judge.json                      per-workspace opt-in: who enabled it, when, terms read
tests/test_judge.py, tests/fixtures/judge/        offline tests; the jev adapter is never called
```
Run output: `judge.jsonl` beside `journal.jsonl` in the run folder, one line per decision.

Shared, already present: `scripts/budget.py`, `scripts/journal.py`, `scripts/fence.py`,
`scripts/harness.py`, `scripts/claims.py`, `scripts/evidence.py`, `scripts/goal.py`.

## The batteries
Question names are not sent to the model, so every word the model needs is in the instructions
and the criteria. One judgement per question; they are combined in code.

### claim
| name | type | instructions | true means | false means |
|---|---|---|---|---|
| supported | noul | The `evidence` excerpts state what the `claim.statement` says. | At least one excerpt contains the same fact as the statement, in the same words or a paraphrase with the same meaning. | No excerpt contains the fact: the excerpts are about something else, or say less than the statement. |
| contradicted | noul | An `evidence` excerpt says the opposite of the `claim.statement`. | An excerpt asserts a fact that cannot be true at the same time as the statement. | No excerpt disagrees with the statement, including excerpts that are silent about it. |
| wider | noul | The `claim.statement` or `claim.scope` claims more than the excerpts show. | The statement generalises to more systems, people, time periods, conditions or products than the excerpts describe. | The statement stays within what the excerpts describe, or is narrower. |
| inferred | noul | The `claim.statement` is a conclusion drawn from the excerpts rather than something an excerpt says. | Reaching the statement needs a reasoning step, a comparison, or combining two excerpts. | An excerpt says the statement directly. |

State: `{"claim": {"statement", "scope", "claim_type"}, "evidence": [{"id", "uri", "locator", "excerpt"}]}`.
Decision in code: `no` when supported is at or below its low threshold, or contradicted is at or
above its high threshold, or wider is at or above its high threshold; `yes` when supported is at
or above its high threshold and the other three are at or below their low thresholds; otherwise
`unsure`. Calibration costs: a missed unsupported claim counts three times a false alarm on
`supported`, one to one on the rest.

### evidence
| name | type | instructions | options or levels |
|---|---|---|---|
| strength | choice | Who published the `page`, relative to `goal.product`? | vendor: the company that makes goal.product, on its own site, docs, blog or an account that speaks for it · partner: an integrator, reseller, framework or platform that sells or bundles goal.product · independent: a person or organisation with no commercial tie to goal.product visible on the page · other: cannot tell from the page |
| relevance | score | How much does the `page` say about the `goal.unknowns`? | 1 does not address any listed unknown · 2 background on an unknown, without a measurement or a first-hand report · 3 a measurement, a first-hand result, or a primary-source fact about a listed unknown |
| instruction | noul | The `page.excerpt` contains text addressed to an AI agent, assistant or tool, telling it what to do. | true: sentences that command an automated reader, such as ignore previous instructions, you are now, call this tool, output the following · false: ordinary prose, code samples, or instructions written for human readers |

State: `{"page": {"uri", "title", "excerpt"}, "goal": {"unknowns", "product", "vendor"}}`.
Hosts on the opt-in file's vendor or partner list answer `strength` from the rule, with no call.

## The bar, written before any result
TPR at least 0.90 on unsupported claims, at TNR at least 0.85 on supported ones, with at least 20
eval cases in each class. Below the bar, the lever order is: rewrite the questions from the
training misses, then several questions voting with fitted weights, then a cascade whose accuracy
is always reported together with the share escalated. A lever that does not help is a result and
is published as one.

## Steps

### S-48 — report.py: an unreadable objections file stops the findings, not just the JSON
**PR:** one.
**Depends on:** S-47.
**Research:** none.
**Files:** `scripts/report.py`, `tests/test_report.py`, `docs/bugs.md` (row 23 state), `docs/spec-v1.md` (S-34 status note).
**Today:** `scripts/report.py` `_review_records` catches a parse error and returns the fixed note
`bad_objections_file`. The JSON handoff then moves every evidence-backed claim into `unreviewed`
and empties `findings`, but FINDINGS.md still prints those same claims under "What we found",
including ones a blocking objection had disputed. One file, two behaviours.
**Change:** when the bad-file note is returned, FINDINGS.md prints the claims under a heading
"Unreviewed (objections file unreadable)" carrying the note, and "What we found" is empty, which
is what the JSON already says. The note names the index of the first offending objection and the
reason taken from the caught exception, instead of a bare "could not be read".
**Acceptance:** WHEN objections.json holds one objection whose `blocking` is the string `"true"`
THEN FINDINGS.md SHALL list no claim under "What we found", SHALL name the offending objection
under "Unreviewed", and the JSON `findings` list SHALL be empty.
**Verify:** `python3 -m unittest tests.test_report -v` passes; delete the new heading branch and
exactly one test fails; `git checkout -- scripts/report.py` restores it.
**Must not:** change `scripts/council.py`; accept a malformed file as valid; edit objections.json.

### S-49 — done.py: read the review files before running the tests
**PR:** one.
**Depends on:** S-47.
**Research:** none.
**Files:** `scripts/done.py`, `tests/test_done.py`, `skills/code-writer-council/references/done.md`, `docs/bugs.md` (row 24 state).
**Today:** `scripts/done.py` `check` runs the frozen test command, writes a `command` evidence
record and an `exec` journal line, and only then parses review-<n>.json, thinker.json and
resolutions.jsonl. A finding whose severity is anything but blocking or advisory raises there, so
the check exits 1 with no NOT DONE line after a full test run has been spent.
**Change:** call the three readers above the test run. A malformed file still exits 1 as bad
input, but before any test run, evidence record or journal line. The reasons table in
`skills/code-writer-council/references/done.md` gains one row saying so.
**Acceptance:** WHEN review-1.json holds a finding with severity `critical` THEN `done.py check`
SHALL exit 1 and evidence.jsonl SHALL hold no `command` record from that check.
**Verify:** `python3 -m unittest tests.test_done -v` passes; move the readers back below the test
run and exactly one test fails.
**Must not:** change what any exit code means; accept a severity outside blocking and advisory.

### S-50 — done.py: a fixed resolution must match the diff being called done
**PR:** one.
**Depends on:** S-47, and R-7 answered in `docs/research.md`.
**Research:** R-7.
**Files:** `scripts/done.py`, `tests/test_done.py`, `skills/code-writer-council/references/done.md`, `docs/bugs.md` (row 25 state).
**Today:** `scripts/done.py` checks that a `fixed` resolution's `diff_sha` is 64 hex characters
and never compares it with the diff it is about to call done, so an edit that undoes the fix
still passes with the old resolution line standing.
**Change:** in `check`, a finding resolution whose `how` is `fixed` and whose `diff_sha` differs
from the sha computed before the test run yields the reason
`stale resolution: <id> (diff changed since the fix; run done.py resolve --fixed again)`. Waived
lines are untouched. `skills/code-writer-council/references/done.md` says to resolve fixed
findings last, after the final edit.
**Acceptance:** WHEN a finding was resolved with `--fixed` and any tracked file changes afterwards
THEN `done.py check` SHALL print `NOT DONE` with `stale resolution: <id>` and exit 2.
**Verify:** `python3 -m unittest tests.test_done -v` passes; remove the comparison and exactly one
test fails.
**Must not:** compare waived lines; let the model type a sha.

### S-51 — shared plumbing: a judge kind, a fence skip, a harness entry
**PR:** one.
**Depends on:** S-47.
**Research:** none.
**Files:** `scripts/journal.py`, `scripts/fence.py`, `scripts/harness.py`, `skills/research-council/references/budget.md`, `tests/test_budget.py`, `tests/test_fence.py`, `tests/test_harness.py`.
**Today:** `journal.py add --kind judge` exits 1, so a Jev call cannot be metered. `fence.py`
skips only journal.jsonl when it compares the run folder before and after a spawn, so a judge
record written while a role is out would read as a violation — and `scripts/council.py` calls the
same comparison inside `accept`, so the reply would be refused too.
**Change:** add `"judge"` to `KINDS` in `scripts/journal.py` and to the usage line above it; add
`"judge.jsonl"` to `SKIP` in `scripts/fence.py` and to its docstring; add `"judge"` to
`RUNTIME_SCRIPTS` in `scripts/harness.py`; add the new kind to the table in
`skills/research-council/references/budget.md`. `scripts/budget.py` needs no change: it counts
actions from `journal.ACTION_KINDS`, which is derived from `KINDS`.
**Acceptance:** WHEN `journal.py add --run <run> --kind judge --cost_usd 0.00002 --detail x` runs
THEN it SHALL exit 0 and `budget.py check` SHALL report one more action and $0.00002 more spend,
and WHEN judge.jsonl is written between `fence.py snapshot` and `fence.py check --role reflection`
THEN the check SHALL exit 0.
**Verify:** `python3 -m unittest tests.test_budget tests.test_fence tests.test_harness -v` passes
(there is no tests/test_journal.py; the journal's own tests live in `tests/test_budget.py`);
remove judge.jsonl from `SKIP` and exactly one test fails. Because `harness.py` raises when a
listed script is missing, S-52 follows immediately.
**Must not:** change any cap or default; add a key to a council packet
(`tests/test_council_runtime.py` pins the ranking packet's keys).

### S-52 — judge.py: the seam, the claim battery, shadow mode
**PR:** one.
**Depends on:** S-51.
**Research:** R-4 answered; R-1 must be answered before the jev adapter is ever pointed at the
live API, which this step does not do.
**Files:** scripts/judge.py, skills/research-council/references/judge.md, `skills/research-council/SKILL.md`, .research-council/judge.json, tests/test_judge.py, tests/fixtures/judge/.
**Today:** nothing reads a claim against its excerpts between `claims.py add` and the Reflection
spawn.
**Change:** scripts/judge.py, standard library only, in this repository's script style: a usage
docstring like `scripts/scope.py`, sibling imports through `sys.path`, argparse subcommands, and
ValueError or OSError printed to stderr with exit 1.
Subcommands: `run --run <run> --battery claim --id C-n [--adapter jev|fake --fake-answers <path>]
[--mode shadow|gate]`, and `questions --battery claim` which prints the questions object for the
calibration tool. The battery definitions are module constants, not files (R-4).
Order inside `run`, each stop printing `judge: claim C-n skipped: <reason>` and exiting 0 without
writing anything: the run folder is not `<root>/AGI_Research/runs/<id>`; no
.research-council/judge.json in the workspace root carrying `enabled_by`, `date` and
`terms_read: true`; `budget.py` reports the run exceeded, or a zero dollar cap, or one more action
over the action cap; any record the state would carry has an `access_scope` other than `public`;
the assembled state matches an address, a run of digits long enough to be a phone number, a
key-shaped token or a home directory path; the state is longer than 60000 characters; no
`TYPESAFE_API_KEY` in the environment; the adapter raised. Before the adapter is called, every
number in the statement is looked for in the cited excerpts, and a missing one prints
`judge: claim C-n no (rule: number <n> not in any excerpt)` with no call, which is the rule
`agents/reflection.md` already gives the Reflection role.
On a call: write the journal line first, then append the judge record, inside one try, so a call
that happened is never unlogged. Print exactly one line. Exit 0 in shadow mode whatever the
decision; exit 1 for bad input, including `--mode gate` in this step, which is not wired until
S-54.
`skills/research-council/SKILL.md` gains two sentences in the claims stage: after `claims.py add`
prints its `C-n recorded` line, run the judge on that id; a skipped or unsure line changes
nothing; skip the judge entirely when the run's goal record forbids paid calls. judge.md explains
each printed line in plain English, with the n8n analogy and the outage behaviour.
**Acceptance:** WHEN `TYPESAFE_API_KEY` is unset THEN judge.py SHALL print
`judge: claim C-1 skipped: no key`, exit 0, and write no journal line and no judge record; and
WHEN a cited record has `access_scope: private` THEN it SHALL print `skipped: egress private E-n`,
exit 0, and build no request body; and WHEN the fake adapter answers supported 0.05 with no fitted
thresholds THEN the judge record SHALL carry `"decision": "unsure"` and the journal SHALL hold one
`judge` line with the adapter's cost; and WHEN a number in the statement appears in no excerpt
THEN it SHALL print a `no` line naming that number with no adapter call.
**Verify:** `python3 -m unittest tests.test_judge -v` passes;
`python3 scripts/validate_skill.py skills/research-council` prints OK; remove the egress check and
exactly one test fails; remove the no-key stop and exactly one test fails.
**Must not:** reach the network in any test (the jev adapter is exercised with a stubbed opener);
write into claims.jsonl, evidence.jsonl or goal.json; define any threshold; run without the
opt-in file; write the judge record before the journal line.

### S-53 — cases from our own runs, and the first calibration
**PR:** one.
**Depends on:** S-52, and R-1 answered.
**Research:** R-1, R-2, R-3, R-5.
**Files:** scripts/judge.py, tests/test_judge.py, tests/fixtures/judge/synthetic-claims.jsonl, docs/runs/<date>-jev-claim-calibration.md, `docs/research.md`.
**Today:** no labelled cases exist, so every decision is unsure and no threshold can be defended.
**Change:** a `cases --battery claim --runs <run>... --out <path>` subcommand writes one JSON
object per line, `{"id": "<first 8 of the run id>-C-n", "state": {...}, "labels": {...}}`, through
the same egress guard, printing how many records it excluded and why. A claim is a positive only
if Reflection demonstrably read it: the sha256 recorded in the run's fence/reflection.json must
match a line-prefix of claims.jsonl, and where the fence folder is missing the fallback is every
id at or below the highest id any objection in that run names. Claims carrying `superseded_by` are
excluded. Negatives come from the objections: `provenance` means supported 0, `scope` means wider
1, `type` means inferred 1, `counterexample` means contradicted 1. Thirty hand-written hard
negatives are appended from the fixture: a changed number, the right words about the wrong
entity, a paraphrase that flips the polarity, an instruction quoted inside an excerpt. Then,
outside the repository, the jev skill's calibration tool fits thresholds on the training split
and reports the held-out split; if the bar is missed, its own optimiser writes a packet of
training misses, one rewrite is made, and its compare command referees. The fitted thresholds and
a `fitted` block naming the eval n and the date are committed into scripts/judge.py, and the run
note records eval n per class, the share of eval cases from each run, the synthetic share, TPR and
TNR, the unsure share, the model id the API returned, who labelled the cases, and the spend.
**Acceptance:** WHEN the calibration note is read THEN it SHALL state eval n per class, TPR and
TNR on the held-out split, the unsure share and the model id the API returned; and WHEN fewer than
20 eval cases exist for any class THEN the committed `fitted` block SHALL stay empty and gate mode
SHALL stay refused.
**Verify:** `python3 -m unittest tests.test_judge -v` passes with the exporter run against fixture
runs; the case count printed by the exporter matches the lines in the output file.
**Must not:** tune on the held-out split; send any private or client record; store the key in any
file; spend more than $0.10 without asking again.

### S-54 — gate mode, in the demoting direction only
**PR:** one.
**Depends on:** S-53 with thresholds fitted.
**Research:** R-2 answered.
**Files:** scripts/judge.py, `skills/research-council/SKILL.md`, skills/research-council/references/judge.md, tests/test_judge.py.
**Today:** every decision is shadow; a confident no changes nothing.
**Change:** `--mode gate` exits 2 on a confident no, printing the probabilities that produced it,
and exits 1 when no thresholds are fitted or the adapter is the fake one.
`skills/research-council/SKILL.md`: on exit 2, fix the claim or its evidence and run it again;
never record a claim over a confident no; unsure proceeds and Reflection decides; after each run,
compare the judge records with objections.json and turn every disagreement into a new case.
**Acceptance:** WHEN no thresholds are fitted THEN `--mode gate` SHALL exit 1 naming the missing
calibration; and WHEN supported falls at or below its low threshold with fitted thresholds THEN it
SHALL exit 2 printing that probability.
**Verify:** `python3 -m unittest tests.test_judge -v` passes; remove the fitted check and exactly
one test fails.
**Must not:** let a yes verify anything; edit or delete a claim; show judge records to any role.

### S-55 — the evidence battery, shadow only
**PR:** one.
**Depends on:** S-52.
**Research:** none; labels accumulate in shadow.
**Files:** scripts/judge.py, `skills/research-council/SKILL.md`, skills/research-council/references/judge.md, tests/test_judge.py.
**Today:** source strength is prose in a claim's `limitations` field, and the 2026-09-21 run's
meta-review found six records whose strength was recorded wrongly.
**Change:** the evidence battery above, with the product name, the vendor name and the vendor and
partner host lists read from the opt-in file, filled in by the Supervisor at goal time.
`skills/research-council/SKILL.md` says to run the judge on each recorded evidence id; the
Supervisor still writes `limitations` itself, and compares afterwards.
**Acceptance:** WHEN the page's host is on the vendor list THEN the printed line SHALL be
`judge: evidence E-n vendor (rule: host)` with no adapter call; and WHEN the fake adapter returns
0.9 for instruction THEN the judge record SHALL carry it and the printed line SHALL end `unsure`.
**Verify:** `python3 -m unittest tests.test_judge -v` passes; the four skill validators print OK.
**Must not:** gate on any answer; drop or alter an evidence record.

### S-56 — parked: the code-writer-council battery
Opens when the dry run of `docs/spec-code-council.md` S-44 has produced review files to label.
A task record carries no access scope, so the workspace opt-in file is the only switch, and a
client repository never has one.

### S-57 — optional: repair.py, schema-aligned normalisation of a role's reply
The one useful BAML idea without the dependency (D-13). A lossless pass before `scripts/council.py`
and `scripts/done.py` validate a reply: strip code fences, parse with control characters allowed,
case-fold the enum values those scripts compare exactly, and coerce the strings "true" and "false"
to booleans. Every repair is journaled as a note; no field is ever invented; a reply that parses
cleanly is untouched. Fixes bug 28. Dropped if the queue stays on the seam.

### S-58 — done.py: a Thinker test counts only when it is defined in a verifier file

**PR:** one.
**Depends on:** S-47.
**Research:** none.
**Files:** `scripts/done.py`, `tests/test_done.py`,
`skills/code-writer-council/references/done.md`, `agents/code-thinker.md`, `docs/bugs.md` (row 26).
**Today:** `scripts/done.py` joins every added line of the diff and the whole text of every
untracked file into one string and asks whether the Thinker's declared name appears anywhere in
it. A comment holding the name, a docstring naming it, or an unrelated new file that mentions it
all satisfy the check, so a task can print DONE with the drafted test never written (bug 26).
**Change:** attribute added lines to the file they were added to (`+++ b/<path>` headers for the
patch, the path itself for an untracked file), keep only the files `scope.is_verifier` accepts for
this task's `test_command`, and count the test present when a non-comment added line in one of
them holds the name followed by `(` — a definition or a call of that exact name, not a mention.
`scope.is_comment` decides what a comment is, so the two scripts keep one definition. A waived
test stays closed as before, and the rule the Thinker and the Supervisor read is written into
`references/done.md` and `agents/code-thinker.md`.
**Acceptance:** WHEN `thinker.json` declares `T-1` named `test_big_verdict` and the only added
text holding that name is a comment in a source file or an untracked file that is not a verifier
THEN `done.py check` SHALL print `NOT DONE` with `missing test: T-1 test_big_verdict`, and WHEN
`def test_big_verdict(` is added to a verifier file THEN `done.py check` SHALL print `DONE <sha>`.
**Verify:** `python3 -m unittest tests.test_done -v` → pass; drop the verifier filter → the new
test fails; drop the `(` and match the bare name → the new test fails;
`python3 -m unittest discover -s tests` → OK.
**Must not:** change `thinker.json`'s schema or make `file` required; demand a particular test
framework; touch `scope.py`'s markers or comment prefixes (bug 27 is its own step); let a
`--waived` test start failing.

### S-59 — scope.py: a comment prefix is decided by the file's language

**PR:** one.
**Depends on:** S-47.
**Research:** none.
**Files:** `scripts/scope.py`, `scripts/done.py`, `tests/test_scope.py`, `tests/test_done.py`,
`skills/code-writer-council/references/tiers.md`, `docs/bugs.md` (row 27).
**Today:** `scripts/scope.py` holds one comment-prefix list for every file:
`("#", "//", "/*", "*", "--")`. A removed line is only a real removed line when it starts with
none of them, so in a shell or Python verifier a removed `--maxfail=1` continuation line and a
removed `*args,` line are both read as comments and the verifier-edit guard stays silent
(bug 27, first half). The same list is what `scripts/done.py` asks about an added line.
**Change:** replace the single tuple with a map from file extension to that language's comment
starts — `#` for Python, shell, YAML, TOML and the other hash languages, `//`, `/*` and `*` for
the C family and CSS, `--` for SQL, Lua and Haskell, `<!--` for HTML, XML and Markdown — plus a
small map for the extensionless names that appear in a `test_command` (`Makefile`, `Dockerfile`)
and the fallback `("#", "//")` for an extension the map does not know. `is_comment(line, path)`
and `verifier_reasons(added, removed, path)` take the path, and `scripts/done.py` passes the path
it already attributes each added line to. Nothing else about the guard changes: blank lines are
still never real lines, and the weakening markers are untouched (they are S-60).
**Acceptance:** WHEN a removed line of a shell verifier file starts with `--` THEN
`scope.py check` SHALL print `verifier-edit: <path>: removed line: <line>` and exit 2, and WHEN a
removed line of a `.sql` verifier file starts with `--` THEN it SHALL print no violation for that
line.
**Verify:** `python3 -m unittest tests.test_scope tests.test_done -v` → pass; put the old single
tuple back → the new test fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** change `WEAKENING_MARKERS` or how a marker is matched (bug 27's second half is
S-60); change what `is_verifier` accepts; make a blank line a real line; add a language whose
prefixes were not read from that language's own syntax.

### S-60 — scope.py: a weakening marker is matched as a token, not a substring

**PR:** one.
**Depends on:** S-59.
**Research:** none.
**Files:** `scripts/scope.py`, `tests/test_scope.py`,
`skills/code-writer-council/references/tiers.md`, `docs/bugs.md` (row 27).
**Today:** `verifier_reasons` lowercases an added line and asks `m in low` for each of
`WEAKENING_MARKERS`, so `skip` matches `skipped`, `skipping`, `skip_list` and any identifier that
contains it: an added line `results = [r for r in rows if not r.skipped]` is reported as a
weakening marker (bug 27, second half). The same substring test also fires on the leading edge of
a call-shaped marker: an added `sys.exit(1)` contains `xit(` and is reported as a marker
(confirmed by running `verifier_reasons` on that line, 2026-09-22).
**Change:** match every marker as a whole token, by putting a word boundary on each edge of the
marker whose own character there is a word character and on no other edge. That gives `\bskip\b`,
`\bxfail\b`, `\bexpectedfailure\b`, `\bxit\(`, `\bxdescribe\(`, `\.only\(`, `@ignore\b` and
`@disabled\b`: the word-shaped markers stop matching inside a longer identifier, and the
call-shaped ones stop matching the tail of one (`sys.exit(`). An earlier draft of this step kept
the call-shaped markers unchanged "since their trailing `(` already ends them", which is true of
the trailing edge only and left `sys.exit(` broken; the one rule covers both edges. The printed
reason keeps its wording, so `references/tiers.md` gains only the sentence that a marker is
matched as a whole token.
**Acceptance:** WHEN an added line of a verifier file contains `skipped` inside a longer word and
no marker of its own THEN `scope.py check` SHALL print no `verifier-edit` line for it, and WHEN an
added line is `sys.exit(1)` THEN it SHALL print no `verifier-edit` line for it, and WHEN the added
line contains `@unittest.skip(` THEN it SHALL still print `added 'skip' marker: <line>`.
**Verify:** `python3 -m unittest tests.test_scope -v` → pass; put the substring test back → the
new test fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** drop or add a marker; change the printed reason's wording; touch the comment
prefixes (S-59 owns them).

### S-61 — the docs name the run folder that runs actually use

**PR:** one (docs only).
**Depends on:** nothing.
**Research:** none.
**Files:** `CLAUDE.md`, `docs/runs/2026-09-09-self-run.md`, `docs/bugs.md` (row 29).
**Today:** `CLAUDE.md` ends its pointer list with `Research folder: ~/AGI_Research/`, but no run has
ever been written there: every run on this machine lives at `AGI_Research/runs/<goal_id>/` inside the
workspace, and `~/AGI_Research/` is an unrelated bibliography corpus (it holds papers/,
bibliography.csv and arxiv_meta.json). A reader sent to the wrong folder finds a corpus that
looks plausible and concludes the runs are missing. Separately, the "What was run" table in
`docs/runs/2026-09-09-self-run.md` gives a per-step count in several rows (`21 records` at
05:45-05:46, `14 claims` at 05:46, then `6 records, 4 claims`, `9 new records` and `4 records,
3 claims` in later rows), with no total anywhere, so the first two read as the run's totals. They are
not: the run folder `622aeb79-ba7a-4334-b15c-012a283c48c7` holds 40 evidence records and 27 claims,
which is what those five rows sum to. The 2026-09-10 follow-up section is a different run
(`a9963323-9ff7-4a5e-9b63-549bc88626ab`) whose folder is no longer on disk, so its `12 evidence
records, 9 claim records` cannot be re-checked here and is left as written, marked unverifiable.
**Change:** `CLAUDE.md` names the run folder as `AGI_Research/runs/<goal_id>/` inside the workspace
and says the folder is gitignored, dropping the home-directory path. The self-run note gains one
line under its table saying each row counts that step only and naming the close totals read from the
run folder, and one clause in the follow-up section marking its counts as that separate run's own,
no longer checkable.
**Acceptance:** WHEN `CLAUDE.md` is read THEN it SHALL name `AGI_Research/runs/<goal_id>/` as the run
folder and SHALL NOT name a research folder under the home directory, and WHEN the "What was run"
table of `docs/runs/2026-09-09-self-run.md` is read THEN a line beneath it SHALL state the run's
close totals of 40 evidence records and 27 claims and SHALL say the rows count one step each.
**Verify:** `python3 -m unittest discover -s tests` → OK; `python3 scripts/validate_skill.py
skills/research-council` and `skills/code-writer-council` → OK; every backticked path in the two
changed files exists on disk.
**Must not:** change any script, test or skill file; restate a count that cannot be read from a run
folder on this machine; delete a row of the self-run table.

### S-62 — rank.py: an issued pair counts as drawn until it is recorded

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `scripts/rank.py`, `tests/test_rank.py`,
`skills/research-council/references/rank.md`, `docs/bugs.md` (row 16).
**Today:** `_opponents` builds its id-to-opponents map from `comparisons.jsonl` only, so a pair that
has been issued into `pairs.jsonl` and not yet judged is invisible to `choose`. Running
`rank.py pair --seed 1` and then `rank.py pair --seed 2` before recording the first draws the same
two hypotheses twice, as P-1 and P-2. Judging both would feed one matchup into Elo twice, which is
what the rating is supposed to be protected from; in the 2026-09-17 run P-2 was left unjudged and
journaled instead (bug 16). `record` already refuses a pair it has recorded before, but nothing
refuses issuing one.
**Change:** an issued pair counts as drawn until it is recorded. `_opponents` reads `pairs.jsonl`
as well as `comparisons.jsonl`, both of which carry `a` and `b`, so `choose` prefers an opponent the
hypothesis has not been drawn against rather than one it has not been judged against. Where the
tournament has no other matchup left — two open hypotheses and one outstanding pair — `choose` still
returns that matchup, so `pair` refuses it: it looks the chosen matchup up among the issued pairs
that have no comparison line, and raises `pair <P-n> is already issued for <H-a> vs <H-b> and not
recorded; record it or judge it first` before writing anything. A matchup whose result is recorded
can still be drawn again, which is a rematch and not a double count. `references/rank.md` states
the rule under its existing one-pair-at-a-time heading.
**Acceptance:** WHEN `pair` is run twice without recording the first result and only two hypotheses
are open THEN the second call SHALL exit 1 naming the outstanding pair id and `pairs.jsonl` SHALL
hold one line, and WHEN a third hypothesis is open THEN the second call SHALL draw a matchup that
is not the outstanding one.
**Verify:** `python3 -m unittest tests.test_rank -v` → pass; drop `pairs.jsonl` from `_opponents`
→ the new selection test fails; drop the refusal → the new refusal test fails;
`python3 -m unittest discover -s tests` → OK.
**Must not:** change the Elo arithmetic, the blinding, or any exit-code meaning; refuse a rematch of
a matchup that has a recorded result; write to `pairs.jsonl` on a refusal; give `record` a new rule.

### S-63 — fence.py: the tournament files are the Supervisor's, and council.md says when not to write

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `scripts/fence.py`, `tests/test_fence.py`,
`skills/research-council/references/council.md`, `docs/bugs.md` (row 17).
**Today:** `fence.py` compares every file in the run folder against the snapshot except
`journal.jsonl`, `judge.jsonl` and the `fence/` folder. `pairs.jsonl` and `comparisons.jsonl` are
written by `scripts/rank.py` and by nothing else — no council role has Bash, and neither file is any
role's declared output — but they are compared, so a `rank.py pair` run by the Supervisor between
the snapshot and the check is reported as `violation: ranking wrote pairs.jsonl` (bug 17, seen in
the 2026-09-17 run). The reader of that line is told the Ranking role wrote a file it has no path
to write. Nothing in `references/council.md` says not to run a run-folder-writing script while a
role is out, either, so the Supervisor had no rule to follow.
**Change:** `SKIP` gains `pairs.jsonl` and `comparisons.jsonl`, which makes it the set of files only
the Supervisor's own scripts write, and `fence.py`'s docstring says that is what it is. The
"After every spawn" paragraph of `references/council.md` names the four excluded files instead of
one, and the "Every spawn" block gains the ordering rule: draw the pair before taking the snapshot,
and run no run-folder-writing script between the snapshot and the check.
**Acceptance:** WHEN `pairs.jsonl` or `comparisons.jsonl` changes between `fence.py snapshot --role
ranking` and `fence.py check --role ranking` THEN the check SHALL print `ok` and exit 0, and WHEN
`hypotheses.json` changes in the same window THEN it SHALL still print a violation and exit 2.
**Verify:** `python3 -m unittest tests.test_fence -v` → pass; drop the two names from `SKIP` → the
new test fails; `python3 -m unittest discover -s tests` → OK; `python3 scripts/validate_skill.py
skills/research-council` → OK.
**Must not:** exempt `hypotheses.json`, `objections.json`, `meta.md`, `evidence.jsonl` or
`claims.jsonl` from the comparison; change what any role is allowed to write; let `fence.py` delete
or restore a file.

### S-64 — budget.py: say where the wall-clock minutes went

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `scripts/budget.py`, `tests/test_budget.py`,
`skills/research-council/references/budget.md`, `skills/research-council/SKILL.md`,
`docs/bugs.md` (row 18).
**Today:** `status` computes `minutes` as wall-clock minutes since `created_at`, which is the
user's rule and stays the user's rule. Nothing says so on the output, though, so the 2026-09-17 run
printed `313/90 min` at report time after about 25 minutes of Supervisor work: the run had waited
288 minutes between two interactive turns. The reader of that line has no way to tell a run that
overspent from a run that was left open overnight, and the same line makes the next `check` exit 2.
`references/budget.md` states the wall-clock rule only in a table cell, and `SKILL.md` never warns
that a pause spends the cap.
**Change:** the minutes stay exactly as they are — the cap is the user's and no script may soften
it (CLAUDE.md invariant 4) — and `budget.py` prints one extra line saying where they went, computed
from the timestamps already in `journal.jsonl`: the longest gap between two consecutive journal
lines (the gap from `created_at` to the first line counts as one), in minutes, with the time it
ended. No threshold is invented and no minute is excused: the line reports a measured gap, and the
reader decides whether it was work or waiting. It is printed whenever the journal holds at least
one line, after the `spent:` line, and the existing `line(st)` is untouched so the `spent:` format
does not move. `references/budget.md` states the wall-clock rule in its own sentence above the
table, and `SKILL.md` tells the Supervisor to finish a run in one sitting and to report the pause
in the run note when it cannot.
**Acceptance:** WHEN a run's journal holds two lines 288 minutes apart THEN `budget.py check` SHALL
print a second line naming 288 minutes as the longest gap and the time it ended, and WHEN the
minutes cap is exceeded THEN the exit code SHALL still be 2 and the reported minutes SHALL still be
the wall-clock minutes since `created_at`.
**Verify:** `python3 -m unittest tests.test_budget -v` → pass; make the gap ignore `created_at` →
the new test fails; drop the pause line → the new test fails; `python3 -m unittest discover -s
tests` → OK; `python3 scripts/validate_skill.py skills/research-council` → OK.
**Must not:** change `minutes`, any cap, any exit code, or what counts as an action; subtract a gap
from the spent minutes; invent an idle threshold; change the `spent:` line's format.

### S-65 — council.py: a role's reply is not refused for its formatting

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `scripts/council.py`, `tests/test_council_runtime.py`,
`skills/research-council/references/council.md`, `docs/bugs.md` (rows 19 and 28).
**Today:** three places in `scripts/council.py` refuse a whole reply over presentation rather than
content. `main` parses stdin with `json.loads(raw)`, which rejects a raw control character inside a
string, so Reflection's 15 KB reply in the 2026-09-17 run could not be ingested until it was parsed
by hand with `strict=False` (bug 19), and a reply wrapped in a Markdown code fence — which is how a
model returns JSON unless told otherwise — is not JSON at all. `_meta` counts each heading as the
exact string `## <name>\n`, so `## **Recommendation**`, a trailing space, a CRLF line ending or the
same heading named twice in a summary line refuses the reply. `_meta` then reads the first
whitespace token of the recommendation against the lower-case literals `continue` and `stop`, so
`Continue` and `Stop.` refuse it (bug 28, council half). A refused reply costs the reserved spawn,
which is not refunded, and the content was never the problem.
**Change:** read the reply tolerantly; do not rewrite it. `main` strips one leading and trailing
Markdown code fence before parsing and parses with `strict=False`, so a control character inside a
string is read rather than refused. `_meta` counts a heading with a regex anchored at the start of
a line that allows leading spaces, optional `*` or `_` emphasis around the name, and trailing
spaces before the newline; the recommendation's first token is compared case-folded with its
surrounding punctuation stripped. The stored text is exactly the text the role sent: nothing is
normalised on the way to `meta.md`, so nothing can be lost. The `MAX_REPLY` size limit, the
`_keys` field check, every schema rule and every exit code stay as they are.
**Acceptance:** WHEN a meta-review reply writes its heading as `## **Recommendation**` and begins
the recommendation `Continue —` THEN `council.py accept` SHALL store `meta.md` byte-for-byte as
sent and exit 0, and WHEN a reply arrives fenced in ```json with a raw control character inside a
string THEN the CLI SHALL parse it and exit 0, and WHEN the reply has no Recommendation section at
all THEN it SHALL still be refused.
**Verify:** `python3 -m unittest tests.test_council_runtime -v` → pass; put the exact heading count
back → the new heading test fails; drop `strict=False` → the new control-character test fails;
drop the fence strip → the new fence test fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** change what is stored in `meta.md`; accept a reply missing a required section, field
or id; relax `MAX_REPLY`, the goal or input fingerprint checks, or the fence check; case-fold
anything other than the recommendation token; touch `scripts/rank.py` (S-66 owns it).

### S-66 — rank.py: the winner is one of three values however it is capitalised

**PR:** one.
**Depends on:** S-65.
**Research:** none.
**Files:** `scripts/rank.py`, `tests/test_rank.py`,
`skills/research-council/references/rank.md`, `docs/bugs.md` (row 28).
**Today:** `record` tests `winner not in SCORE`, whose keys are `A`, `B` and `draw`, so `a`, `Draw`
and `draw.` are refused (bug 28, rank half). The CLI is reached through
`--winner ... choices=sorted(SCORE)` and refuses the same values at argparse, but the path that
matters is `scripts/council.py` `accept`, which passes a Ranking role's `reply["winner"]` straight
into `record`: a reply worth a whole spawn is discarded for a capital letter, and the reservation
is not refunded. S-65 made the meta-review reply tolerant of its own formatting; this is the same
defect in the one enum a Ranking reply carries.
**Change:** `record` resolves the winner to the `SCORE` key it names, comparing case-folded with
surrounding punctuation stripped, and raises the same message as today for anything that resolves
to none of the three. The canonical key is what goes into `comparisons.jsonl`, unlike S-65's
verbatim text: a three-member enum has a correct spelling and every later reader — `SCORE[winner]`,
`winner_id`, `cycles` and the report — indexes it by that spelling, so storing `a` would move the
defect downstream instead of fixing it. The CLI takes the same resolver as its argument `type`, so
`--winner a` reaches argparse's `choices` already canonical. `references/rank.md` says the winner is
read case-insensitively and stored canonically.
**Acceptance:** WHEN a Ranking reply gives `"winner": "a"` THEN `council.py accept` SHALL record the
comparison with `winner` `A` and exit 0, and WHEN it gives `"winner": "Draw."` THEN the stored
winner SHALL be `draw` with `winner_id` null, and WHEN it gives `"winner": "maybe"` THEN `record`
SHALL still raise and write no comparison line.
**Verify:** `python3 -m unittest tests.test_rank tests.test_council_runtime -v` → pass; compare the
winner exactly again → the new test fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** add a fourth winner value; change the Elo arithmetic or `winner_id`; accept a winner
that resolves to none of the three; change any exit code; store a spelling that is not a `SCORE`
key.

### S-67 — a backticked path in a tracked Markdown file is a path that exists

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `tests/test_doc_paths.py` (new), `CLAUDE.md`, `docs/spec-v1.md`, `docs/spec-jev.md`,
`docs/runs/2026-09-09-self-run.md`, `skills/self-improve/SKILL.md`,
`skills/code-writer-council/references/tiers.md`,
`skills/research-council/references/judge.md`,
`skills/research-council/references/library.md`.
**Today:** `CLAUDE.md` says "Paths in docs with backticks exist. Planned names are written plain",
and nothing reads a Markdown file to check it. `tests/test_ci.py` reads the workflow and
`scripts/validate_skill.py` reads a skill's frontmatter and body limits; neither looks at prose.
S-47's own Status row records that the convention was checked by hand and caught five planned names
written with backticks, and S-61 caught two more the same way. Twelve survive on main, every one a
name absent from a checkout: the run folder AGI_Research/runs/ twice and
AGI_Research/runs/622aeb79-.../ once, the opt-in file .research-council/judge.json three times that
S-52 deliberately did not write, the planned library file references/validation.json twice, the
placeholder docs/runs/2026-xx-first-run.md, the example scripts/lib/util.py, the command shorthand
new/advance/status, and references/retrieve.md inside a Status row whose own sentence says it never
existed.
**Change:** `tests/test_doc_paths.py` reads every tracked `.md` file and fails naming each
offending `file:line` and span. A backticked span is read as a path claim only when a separator
stands between two of its segments and it holds no whitespace, no `://`, no leading `~` or `/`, and
none of `< > * { } ? | " ' $` — so a command, a URL, a glob, a placeholder and a path outside the
checkout are all left alone. One segment is a name rather than a path whether or not it ends in a
slash: goal.json and AGI_Research/ both name something that lives in a run folder, and
AGI_Research/ is also the literal line `references/goal.md` tells the Supervisor to add to a
.gitignore, where backticks are right and `tests/test_goal.py` pins them. A trailing `:<n>` or
`:<n>-<n>` is stripped, then the span must resolve against the document's own directory or the
repository root; failing both it must match the tail of exactly one tracked path. The tail rule is
what lets a skill's own reference file say `references/tiers.md` for its sibling and prose in
`docs/` name a skill's reference file without spelling the whole path, while still failing
references/retrieve.md, which matches nothing; a tail matching two paths is not resolved, so an
ambiguous name has to be spelled out in full. What resolves is read from `git ls-files` and never
from the filesystem, because a gitignored run folder sitting in the working copy would make a
sentence about it true on the machine that wrote it and false in CI. The twelve violations are
fixed by removing their backticks, which is what `CLAUDE.md` already asks for; no path is
corrected, because every one is correct prose about a name that is not in a checkout. `CLAUDE.md`
names the test beside the rule and adds deleted and run-folder names to the planned ones it already
tells a writer to write plain.
**Acceptance:** WHEN `python3 -m unittest tests.test_doc_paths` runs on a checkout THEN it SHALL
pass, and WHEN a tracked Markdown file gains a backticked docs/no-such-file.md THEN that run SHALL
fail naming that file, its line number and the span, and WHEN a file exists in the working copy but
is untracked THEN a backticked span naming it SHALL NOT resolve.
**Verify:** `python3 -m unittest tests.test_doc_paths -v` → pass; restore the backticks on any one
of the twelve → exactly one test fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** add a script, a CI workflow line or a dependency — the suite is already what CI runs;
read an untracked or ignored file; correct any path rather than un-backticking a planned name;
change the convention in `CLAUDE.md` beyond naming where it is enforced and which names go plain;
skip a file to make the suite green.

### S-68 — the phone guard stops a phone number, not a date

**PR:** one.
**Depends on:** S-52.
**Research:** R-9 answered here, by measurement on this repository's own runs.
**Files:** `scripts/judge.py`, `tests/test_judge.py`, `docs/research.md`, `docs/spec-jev.md`.
**Today:** `scripts/judge.py` `EGRESS` holds `("phone", re.compile(r"\+?\d[\d\s().-]{8,}\d"))`,
which needs eight digits or separators between a first and a last digit, so eight digits in total
are enough to stop a state. R-9 was opened at the time the pattern was written and left for S-53's
exporter to count; the count needs no exporter and no call, because `build_claim_state` and the two
run folders on disk are enough. Measured on all 57 claims in AGI_Research/runs/: the pattern stops
37 of them, 65%, over 54 matches of 22 distinct spans, and not one span is a phone number. Twenty-
eight are the ISO date 2026-09-09, sixteen are arXiv ids of the shape 2601.15195, one is the
benchmark range 80.9--95.2. The guard is not protecting anything on this repository's data; it is
turning the judge off, which is what R-9 said to check for.
**Change:** the phone pattern requires ten digits, not eight characters:
`re.compile(r"\+?\d(?:[\s().-]*\d){9,}")`. Ten is the length of a number that can be dialled —
a North American number without its country code — and E.164 allows fifteen, so a shorter run of
digits is not a phone number whatever its punctuation. The separator class no longer holds `\d`,
which is what keeps the rule linear: the optional separators and the digit that follows them can
never match the same character, so there is no nested quantifier to back off through on a 60000-
character state. Measured the same way as the count above: all thirteen written forms of a real
number in the test still stop (`+1 (555) 123-4567`, `(555) 123 4567`, `5551234567`,
`+44 20 7946 0958` and the rest), the nine non-phone forms stop none, and the 57 real claims fall
from 37 stopped to 1. The one that stays is a git log excerpt, `8aaece4 2026-09-09 06:27:27 +0530`,
where a date, a time and a timezone offset run together into eleven digits; it is left stopped,
because every narrowing that clears it — a single separator between digits, a cap on the span —
was measured to let a real `(555) 123 4567` through, and a guard that fails open is the one failure
this direction cannot take. The `RESEARCH R-9` comment above the pattern goes, and R-9 is answered
with the numbers and the residual.
**Acceptance:** WHEN the assembled state carries `2026-09-09`, an arXiv id or any run of fewer than
ten digits and nothing else THEN `egress_check` SHALL return None, and WHEN it carries a written
phone number in any of the forms `+1 (555) 123-4567`, `(555) 123 4567`, `555-123-4567`,
`+44 20 7946 0958` or `5551234567` THEN `egress_check` SHALL return `egress phone`.
**Verify:** `python3 -m unittest tests.test_judge -v` → pass; restore the eight-character pattern →
exactly the new date test fails; widen the rule to nine digits → the new ten-digit boundary test
fails; `python3 -m unittest discover -s tests` → OK.
**Must not:** relax any other `EGRESS` pattern or the order the guards run in; let a written phone
number through to make the date pass; add a denylist of date or identifier shapes; make the private-
record check run later than it does; call the network.

### S-69 — a bug row says where its fix landed

**PR:** one.
**Depends on:** nothing.
**Research:** none.
**Files:** `docs/bugs.md`, `tests/test_bug_log.py` (new), `docs/spec-jev.md`.
**Today:** `docs/bugs.md` is the record of what is fixed and what is not, and nine of its thirty
rows do not say. Row 24 reads `fixed 2026-09-21 in S-49 (PR pending)` although S-49 merged as
PR #51 the same day; rows 11, 12, 13, 14, 15, 20 and 21 read `fixed locally`, written before
S-32, S-33, S-34 and S-35 were merged as PR #36, #38, #41 and #37; row 5's cell is the bare step
id `S-17`, merged as PR #26. All nine fixes were read off the current code before this step was
written — `scripts/report.py` opens `objections.json`, `scripts/harness.py` resolves the runtime
root, `scripts/council.py` accepts a reply through `accept` and writes it through a temporary file
it then replaces, `scripts/goal.py` and `scripts/journal.py` call `math.isfinite`,
`scripts/council.py` includes `journal.FILENAME` in its path checks, `scripts/report.py` refuses a
`blocking` value that is not `bool`, and `scripts/done.py` calls `findings`, `resolutions` and
`thinker_tests` at lines 222-224 above `run_tests` at line 226 — so every row understates work
that is on main rather than claiming work that is not. This is bug 22 again, one file along:
a register that claims less than what is true is one a reader cannot use either.
**Change:** each of the nine state cells names the PR that carried the fix, keeping the sentence
it already has. A row whose fix has not landed keeps saying so: row 25 stays `fix queued as S-50`
and row 30 stays `open`. Then `tests/test_bug_log.py` enforces the convention the corrections
follow — every data row of every table in `docs/bugs.md` ends in a state cell that either names a
merge as `PR #<number>` or says `open`, `queued`, `parked` or `blocked`. The two tables have
different column counts, six and four, so the test reads the last cell of each row rather than a
fixed index, and skips the header and separator rows by the same shape test.
**Acceptance:** WHEN `python3 -m unittest tests.test_bug_log` runs THEN it SHALL pass, and WHEN
any state cell in `docs/bugs.md` claims a fix without naming `PR #<number>` THEN that test SHALL
fail naming the row's id.
**Verify:** `python3 -m unittest tests.test_bug_log -v` → pass; restore row 24's `(PR pending)` →
exactly that test fails naming row 24; `python3 -m unittest discover -s tests` → OK.
**Must not:** change any row's evidence, reproduction or correction text; mark a row fixed whose
fix was not read off the current code; invent a PR number; touch `docs/spec-v1.md` or any script.

## Status
| step | state | learned |
|---|---|---|
| S-47 | done 2026-09-21 (PR #49) | The step numbering had to start at S-48, not S-46: `docs/spec-v1.md` already registers S-45 and S-46, and a register is per body of work, not per file touched, so the three bug fixes live here beside the seam steps even though two of them are code-council files (the precedent is S-37, registered in `docs/spec-code-council.md` while changing `scripts/budget.py` and `scripts/journal.py`). Two claims in the plan were wrong against the code and were corrected before they reached this file: `scripts/budget.py` needs no change for a new journal kind, because it counts actions from `journal.ACTION_KINDS`, which is derived from `KINDS`; and `skills/research-council/SKILL.md` has no "any paid API call" sentence to reword, so D-16 names where the prohibition actually lives. The working standard says CI enforces that a backticked path exists, and in this repository nothing does: the check was run by hand here and caught five planned names written with backticks. A test for it is worth a step. |
| S-48 | done 2026-09-21 (PR #50) | The fix is smaller than the bug: `structured_handoff` already computed the right answer, so the Markdown was made to repeat it rather than to decide it again. Naming the offending objection needed the try/except split in two — one around reading the file, one around each objection — because a single wrapper cannot say which item it was on. Two existing tests pinned the bug (`assertIn("**C-2**", sec["What we found"])` in the malformed case) and had to be inverted; a test can pin a defect as firmly as a feature. The test fixture already holds one valid objection, so an appended bad one lands at index 1, not 0. Proof-by-breaking gave 5, 2 and 4 failures for the three guards, not one each, because several tests assert the same behaviour from different sides. Found on the way: bug 30, the same Markdown/JSON split for a *missing* objections file, where both behaviours are deliberately test-pinned and so need a decision, not a fix. |
| S-49 | done 2026-09-21 (PR #51) | Four lines moved, and the whole step was in placing them: above the guard block would have turned an exceeded budget or a scope violation into exit 1 instead of the NOT DONE it prints today, so the readers sit after the early return and before `before = diff_sha(...)`, which is the first line that costs anything. The step said the reasons table in `skills/code-writer-council/references/done.md` gains a row, but that table lists exit-2 NOT DONE reasons only: the row was written as an explicit exit-1 line and the numbered order list above it, which still described the old order, was the edit that actually mattered. Proof-by-breaking failed 2 tests, the new one and one added assertion, which is this repository's pattern rather than the standard's exactly one. The cheapest test here was `assertEqual(evidence.read(run), [])` appended to the existing malformed-files test: it covers the thinker and resolutions readers with no new fixture. Audited on the way: row 23 of `docs/bugs.md` still said "PR pending" after S-48 merged. |
| S-51 | done 2026-09-21 (PR #52) | The step asked for four edits and only three could ship. `harness.resources()` raises on a listed script that is not on disk, so adding `"judge"` to `RUNTIME_SCRIPTS` before scripts/judge.py exists fails 10 tests in `tests/test_harness.py` with `missing or outside runtime resource`; the step's own note ("S-52 follows immediately") assumed a red suite could sit on main between two PRs, which rule 3 does not allow. That line moves to S-52, where the script and its `harness.TOOLS` test arrive together. Measured before deciding, not reasoned about: the entry was added, the module run, and the file restored. Proof-by-breaking gave exactly one failure per guard this time, because the two guards live in different modules and neither test touches the other's. `skills/code-writer-council/references/task.md` carries the same caps table and still lists the old kinds; it stays true while the code battery is parked at S-56, so it is queued there rather than fixed as a drive-by. |
| S-52 | done 2026-09-21 (PR #53) | The step listed .research-council/judge.json among its files and it was not written. That file asserts that a named person read TypeSafe's current terms, which is R-1 and is unanswered, so filling it in would have been a fabricated attestation about a third party's legal terms rather than a missing line of code; its absence is the flag-off state this spec's own Acceptance describes, and it lands with S-53, which already depends on R-1. The `"judge"` entry in `scripts/harness.py` that S-51 could not carry arrived here, as planned, in the commit that created the script. Proof-by-breaking does not give one failure per guard when a guard has two independent halves: removing the whole egress check failed 3 tests, the private-record loop alone 1, the pattern loop alone 2. That pass also found a real hole the committed suite could never show, because the guard in front of it always returned first: with the no-key stop deleted, the CLI test for it opened a socket to the vendor. The fix is in the test helper, not the script, which is the honest place for it: `TYPESAFE_BASE_URL` points at the discard port, so a guard removed by hand is refused locally. Writing the adapter raised R-8, a low-confidence flag with no way to resolve it offline: the jev skill's own `calibrate.py` and `optimize_questions.py` read the same answer field as two different shapes, so `probability` accepts both and raises on anything else, turning an unknown body into a skipped line instead of a wrong decision. No retry loop was written; an error is already a skipped line onto today's path, and untested retry code under a "never reach the network" Must-not would be dead weight, so it belongs with the step that first meets the live API. |
| S-55 | done 2026-09-21 (PR #54) | Shipped out of register order, and the order turned out to be a default rather than a constraint: S-53 and S-54 both wait on R-1, S-55 depends only on S-52, which is already merged, so it was the one step that could be done today. `strength` is a choice and `relevance` a score, the first questions in this repository that are not noul, and `probability` from S-52 reads a number only; `answer_value` had to be written and it opened R-10 at low confidence, because no script here and none in the jev skill reads a choice or a score answer at all. The answer was to validate against the battery's own four options and own three levels, so a shape nobody has seen is a skipped line rather than a source strength written from a guess. `decide` was claim-shaped: it indexes `answers["supported"]` directly, so passing it the battery name was the smallest change that keeps the evidence battery from ever gating, and that is now pinned by a test instead of by a comment. The step text names no `no product` stop, but all three questions are phrased relative to `goal.product`, `goal.json` carries no product field at all, and an empty one would have the model answer a different question confidently; adding the stop is the honest reading of "read from the opt-in file, filled in by the Supervisor at goal time". Proof-by-breaking gave 2, 1, 1, 1 and 1: the host rule fails two tests because vendor and partner are separate, and a third test that also uses a vendor host survives the rule's removal for an honest reason, since `evidence.jsonl` stays untouched down the skip path too. The shared `setUp` in `tests/test_judge.py` became a `Case` mixin rather than a base class, because subclassing `JudgeTests` would have re-run all 28 claim tests under the evidence class. |
| S-58 | done 2026-09-22 (PR #58) | The step is two narrowings, and only both together close the hole: `added_text` joined every added line and every untracked file into one string, so the name had to be attributed to a file before a filter could mean anything. Attributing it needs the patch's own `+++ b/<path>` headers, which is why the old helper could not simply be filtered. `scope.is_verifier` and `scope.is_comment` were already written for the scope guard and are reused here, so the two scripts cannot drift on what a test file or a comment is. The first draft of the new test put the decoy in `notes/`, and the scope guard refused the whole diff before the thinker check ran (`outside: notes/test_big_verdict.md`): a decoy has to live inside `allowed_paths` or it tests the wrong guard. The lookbehind `(?<![\w.])` is what makes `helper_test_big_verdict(` not count. What this does not close: a docstring line in a verifier file holding the name with parentheses still counts, because `is_comment` reads line starts only, and `.github/**` is a verifier by `is_verifier`. Both are deliberate forgeries rather than accidents, and the tighter rule — the name defined in the file `thinker.json` itself names — needs `file` to become a required field, which is a schema change and its own step. Suite 492 → 493. |
| S-59 | done 2026-09-22 (PR #59) | Bug 27 is two independent defects in one file, so it is two steps: this one is the half that fails open. The single prefix list was not merely imprecise, it was unsound in both directions — `--` and `*` hid real removed lines in shell and Python verifiers, and dropping them outright would have made a genuine SQL or C comment a removed line instead. Only a per-language map fixes both, which is why the constant became a dict and `is_comment` took a path. `scripts/done.py` had to change in the same PR because `defines` calls `scope.is_comment`: the signature is the coupling, and S-58 had already attributed every added line to its file, so the path was there to pass. The fallback for an unknown extension is `("#", "//")` rather than the old union, because a verifier-edit line is a warning the user can silence with `allow_verifier_edits` while a missed one is silent, so the guard leans to over-reporting. Free consequences of reading the language: `#include` in a `.c` verifier and `#` headings in a `.md` one are now real lines, and `.gitignore` falls to the fallback where `#` is right anyway. The fixture change is the test: `run_tests.sh` gained a `--failfast` continuation line, which the old code read as a comment. Suite 493 → 494. |
| S-60 | done 2026-09-22 (PR #60) | Bug 27's second half, and the half that fails closed: the substring test never let a weakening through, it invented ones. Writing the step from the `skip`/`skipped` case alone produced a rule for the word-shaped markers only; running `verifier_reasons` on real lines before touching the code found `sys.exit(1)` reported as an `xit(` marker, the same defect on a call-shaped marker's leading edge, so the step block was corrected first and the fix became one rule: a word boundary on each edge of the marker whose own character there is a word character, and on no other edge. That is why `.only(` and `xdescribe(` keep working (`.` and `(` are not word characters, so they get no boundary) while `@ignore` gets one only on its right. The boundary lives in a compiled pattern per marker built at import, so `WEAKENING_MARKERS` stays the single list a reader edits and the printed reason still names the marker string, not the regex. The test asserts both directions in one new file — `r.skipped`, `skip_list` and `sys.exit(1)` silent, `@unittest.skip(` still reported — because a marker fix that only proves the negative would pass with the matcher deleted. Suite 494 -> 495; bug 27 now closed in full. |
| S-61 | done 2026-09-22 (PR #61) | A docs bug, and the only kind of step here with no guard to break: nothing in code enforces either sentence, so the proof is that both claims were read off the system rather than off the bug row. Both were. `~/AGI_Research/` really is a bibliography corpus, and the run folder for goal id 622aeb79 really holds 40 evidence records and 27 claims — the same numbers the table's five per-step rows sum to, which is two independent confirmations of one count and the reason the totals could be written down at all. The third part of bug 29 could not be closed the same way: the 2026-09-10 section belongs to a different run whose folder is gone, so its `9 claim records` was left exactly as written and marked unverifiable instead of being corrected to the 11 the bug row claims. Correcting it from the bug row would have been restating an unchecked number as a fact, which is the failure this step exists to fix. AGI_Research/runs/622aeb79-.../ was written plain in the end: a run folder is gitignored, so backticking it would break the convention that a backticked path exists in a checkout. |
| S-62 | done 2026-09-22 (PR #62) | The fix is one rule with two effects, and both are needed because `choose` is a preference, not a filter: reading `pairs.jsonl` into `_opponents` only moves an outstanding matchup to the back of the queue, so with two open hypotheses and one pair outstanding it is still returned and has to be refused outright. The refusal could not be the whole fix either — refusing on *any* outstanding pair would strand a run whose Ranking spawn never replied, with no cancel path in the script — so it refuses the specific matchup and only when nothing else is drawable. Two existing tests turned out to pin the defect while testing something else entirely: both reissued the same matchup, one to prove a seed gives a deterministic A/B order and one to loop six draws over the last open matchup. Neither needed the reissue: the first only needed `pairs.jsonl` cleared between draws, and the second reads better recording each pair first, which incidentally proves the rematch case this step's Must-not protects. `pair` does not bump `comparisons` — only `record` does — which is why a second draw with four open hypotheses still starts from the same first hypothesis and simply takes the next opponent. Suite 495 -> 497. |
| S-63 | done 2026-09-22 (PR #63) | The fence change is safe for a reason worth writing down rather than assumed: `elo` and `comparisons` live in `hypotheses.json`, not in `comparisons.jsonl`, so excluding the two tournament files costs the detector nothing a forged rating would need, and the new test asserts a `hypotheses.json` write in the same window is still a violation. Adding the two names also turned `SKIP` from a list into a definition — the files only the Supervisor's own scripts write — which is what made the second prose test possible: it iterates `fence.SKIP` and requires each name in council.md, so the next addition to SKIP cannot go undocumented. The ordering half could not be tested at all until that test was written; a prose rule with no test is how bug 17's other half survived two runs. The pair is drawn above the snapshot rather than merely 'not after it', because the blinded JSON has to be in the prompt anyway: the correct order was already forced by the data flow and nobody had written it down. Suite 497 -> 500. |
| S-64 | done 2026-09-22 (PR #64) | The bug row asked for an "active-time line", and that is the one thing this step deliberately did not build: active time needs a number for what counts as idle, nobody has one, and a softened-looking minutes figure beside a hard cap is how invariant 4 gets argued away at runtime. A measured gap gives the reader the same fact with nothing invented, so the correction was narrowed before any code was written rather than implemented as logged. Counting `created_at` as a mark was not obvious until the test was written: a run can be left open before its first action, and without it the first pause is invisible. The CLI assertion had to be rewritten mid-step for an honest reason worth keeping — `budget.status` takes an injected `now` and the CLI does not, so the subprocess sees real wall clock and exits 0 where the in-process status exits 2; the quiet stretch is identical in both because it depends only on the journal and `created_at`, which is what the test now asserts. Break 3 fails two tests rather than one because both new tests assert the maximum from different sides. Suite 500 -> 503. |
| S-65 | done 2026-09-22 (PR #65) | S-57 asked for a `repair.py` doing a lossless normalisation pass with every repair journaled, and the step that replaced it is smaller because normalisation is the expensive half: rewriting a role's text before storing it makes "lossless" a claim to argue, while a tolerant *reader* leaves nothing to argue about — the test compares the stored bytes with what was sent. No new module, no journal plumbing, one import each of `re` and `string`. Bug 19 turned out to be still open despite its row reading "queued under S-33": S-33 shipped the shape validation and never the lenient parsing, so `json.loads(raw)` was still strict at `main`. A bug row that names a step as its fix is not evidence the fix landed, which is worth checking on every row that points at a merged step. Two guards had to be proved not to loosen: a duplicated section and a missing one are still refusals, and break 5 exists only to show the duplicate check survived. Break 1 fails two tests because filtering back to the exact heading also hides a decorated duplicate from the counter. `strict=False` adds no reach — the same bytes as `\\u` escapes were always accepted — which is the reason it is safe rather than merely convenient. Suite 503 -> 507. |
| S-66 | done 2026-09-22 (PR #66) | Two steps one after another made the opposite call about the same kind of leniency, and the difference is the whole lesson: S-65 stored a role's prose exactly as sent because prose has no correct form, while a three-member enum does, and `SCORE[winner]`, `winner_id`, `cycles` and the report all index it by that spelling — so here the canonical key is stored and tolerance stops at the door. Storing what the role typed would have moved the defect downstream. The CLI was never the path worth fixing: argparse already refuses `--winner a` at parse time and a human can retype it, while `council.accept` hands `reply["winner"]` straight to `record` and a refusal there burns the reservation, which is why the council round-trip test matters more than the rank one and why break 1 fails both. A permissive resolver is the obvious way this goes wrong, so the refusal test asserts `maybe`, the empty string, `A B`, `None` and `1` directly rather than trusting the loop. Suite 507 -> 510; bug 28 now closed in full. |
| S-67 | done 2026-09-22 (PR #67) | The rule had to be narrowed twice, and both times by a case the repository already held rather than by reasoning. First: `resolves` asked the filesystem, so the eleven sentences naming AGI_Research/ passed here and would have failed in CI, because that folder is gitignored and exists only on the machine that wrote them — what a fresh checkout holds is what `git ls-files` says, and nothing else. Second: `skills/research-council/SKILL.md` says to add the line `AGI_Research/` to a workspace .gitignore, `tests/test_goal.py` pins that sentence with its backticks, and un-backticking it failed that test. The backticks are right there: the span is a literal to type, not a path to open. That is the same category as the bare filename the first draft already excluded, so the rule became one rule — a claim needs a separator between two segments — which reverted sixteen edits and dropped the count from twenty-eight to twelve. Proof-by-breaking found two dead code paths the way it is supposed to: a SKILL.md-ancestor resolution whose every case the unique-tail rule already covered, and a `rstrip` that `normpath` already did; both were deleted rather than given a test, because the alternative was a fixture invented to justify code nothing needed. The restore in break 1 then ate an uncommitted improvement — `git checkout --` brings back the committed file, which is the S-1 hazard this standard names, and it bites on an amend-in-progress exactly as it does on an unstaged step. Left in place and written into the PR rather than engineered away: references/manifest.json resolves by tail to a test fixture, which is a real example library unit, so the promise holds while the tail rule cannot tell it from the unit the prose means. Suite 510 -> 515. |
| S-68 | done 2026-09-22 (PR #68) | The flag said the number was a by-product of S-53's exporter, and it was not: `build_claim_state` and the two run folders under AGI_Research/runs/ already held the answer, so a research flag parked behind a blocked step was answerable today for nothing. That is the reusable part — before accepting that a flag waits on a step, check whether the step's *output* is what the flag needs or only its *occasion*. Measuring first also changed the shape of the fix. The count came out at 37 of 57 claims stopped, 65%, over 54 matches of 22 distinct spans with not one a phone number, which is not "some false stops exist" as the flag guessed at medium confidence but a guard that was switching the judge off for two runs in three. Reading the 22 spans rather than the count is what gave the rule: 28 ISO dates and 16 arXiv ids are all shorter than ten digits, and ten is a fact about telephone numbering rather than a shape drawn from this data, which is why it is a rule and not a denylist. Two narrower candidates were measured and both fail open — requiring a single separator between digits, or no doubled separator, each lets `(555) 123 4567` through, because `) ` is two separators — so the first rule that passed all thirteen written forms was kept even though it leaves one residual, the git log excerpt `8aaece4 2026-09-09 06:27:27 +0530` where a date, a time and an offset run into eleven digits. Leaving that stopped is the whole direction of this guard: a false stop costs a skipped line on today's path, a false pass sends a phone number to a vendor. The separator class dropping `\d` is not cosmetic either — it is what makes the repeated group unambiguous against the digit after it, so the scan stays linear on a 60000-character state rather than becoming a nested quantifier a crafted excerpt could stall. Break 1 and break 2 each fail two tests because the boundary test asserts both sides of the same rule. Audited on the way: row 24 of `docs/bugs.md` still reads "PR pending" although S-49 merged as PR #51, the same staleness S-49 itself found on row 23. Suite 515 -> 519. |
