# Research log

One entry per open question, in the format of `~/.claude/skills/mystandard/SKILL.md` section 9.
An unknown is written down here, never guessed. A claim with no source stays low confidence, and
a low-confidence flag is reviewed by a stronger model, or by Abhishek when the question is his.

Mark the spot too, so a flag can be found from either end: `[RESEARCH R-<n>]` after the sentence
in a plan, spec or step, and `RESEARCH R-<n> (confidence: <level>): <question>` as a comment on
the line of code. `grep -rn "RESEARCH R-" .` finds them all. The marker is deleted by the PR that
acts on the answer.

### R-1 — Do TypeSafe's current terms allow sending public web excerpts and synthetic cases?

**Where:** jev seam, `docs/spec-jev.md` S-52 egress guard · the opt-in file .research-council/judge.json · field `terms_read`
**Find out:** whether the terms in force today permit (a) evaluation use and (b) later production
use of public excerpts and synthetic cases from this plugin, and whether retention is bounded
without an enterprise agreement. A "no" means the seam ships with the jev adapter permanently
disabled here and only the fake adapter is ever exercised; a "yes" means S-53 may run live.
**Confidence:** low — the only copy read so far (research run 65a47056, 2026-09-21) was indexed
in May 2026, before the 2026-09-15 launch, and granted access "solely for the purpose of
evaluating". Zero data retention was enterprise-only, hosting was US, and no SOC 2 attestation
was found. Whether any of that still holds is unverified.
**Review:** Abhishek reads the current terms himself. Not a model call: a person's name and the
date are what the opt-in file records.
**Status:** partly answered 2026-09-22 in S-53
**Answer:** yes for evaluation with public excerpts and synthetic cases; the opt-in stays unset. Read by Claude on 2026-09-22, not by Abhishek. The Terms of Use (last updated 2026-09-19) do not distinguish evaluation from production. They ask users not to submit anything they consider confidential or proprietary. The Privacy Policy (last updated 2025-11-19) says TypeSafe will not train or fine-tune on prompts or other Input, and will share Input only with its service providers. It sets no retention period for API inputs. Public web excerpts and invented cases fall inside that. Client or private records do not, and the egress guard already keeps those out. Abhishek gave the spend go the same day, which covered S-53's offline calibration. The workspace opt-in file records a person who read the terms, so it was not written, and the in-run judge stays off until he reads them.

### R-2 — What true-positive and true-negative rate does Jev reach on our own claim cases?

**Where:** `docs/spec-jev.md` S-53 · the claim battery in scripts/judge.py
**Find out:** TPR on unsupported claims and TNR on supported ones, on the held-out split, against
the bar written before the run (TPR >= 0.90 at TNR >= 0.85, eval n >= 20 per class). Below the
bar the seam stays in shadow mode for good and S-54 is dropped; at or above it, gate mode ships.
**Confidence:** low — the only numbers on file are the jev skill's own probe (n=27 textual:
supported 0.81-0.98, unsupported 0.01-0.04) and one independent 32-case test that called Jev
"less convincing" and found 3 of 4 mistakes held confidence above 0.8. Neither used our claims.
**Review:** none needed; the calibration run answers it and the note carries the numbers.
**Status:** answered 2026-09-22 in S-53 (direction only)
**Answer:** below the bar, on too few cases to settle it: TPR 0.85 on unsupported (11/13) at TNR 0.62 on supported (5/8), held-out split. Neither class reaches n >= 20, so `fitted` stays None and S-54 stays blocked; the full numbers are in the 2026-09-22 calibration note under docs/runs/.

### R-3 — Which claims had Reflection actually seen when it wrote its objections?

**Where:** `docs/spec-jev.md` S-53 · the case exporter in scripts/judge.py · positives selection
**Find out:** per run, the exact set of claim ids Reflection read. A claim added after Reflection
ran carries no objection because nobody looked, not because it was clean, so counting it as a
positive would teach the wrong lesson.
**Confidence:** medium — `skills/research-council/references/evidence.md` states a supersede
appends a record and "the original line stays as written", so claims.jsonl is append-only and the
sha256 in the run's fence/reflection.json should match a line-prefix of today's file. Two gaps are known:
run 622aeb79 has no fence folder at all, and the 2026-09-21 jev run's own meta-review records that
its Reflection pass saw only E-1 to E-10. Neither the prefix match nor the fallback (ids at or
below the highest objected id) has been run yet.
**Review:** none; the exporter prints the counts it used and the calibration note repeats them.
**Status:** answered 2026-09-22 in S-53
**Answer:** measured by the exporter. In four runs the fence snapshot's sha matched a line-prefix of claims.jsonl exactly: 80e03afb 25 claims, e322c3a5 21, 65a47056 87, 07faefbd 7. Run 622aeb79 fell back to ids at or below the highest objected id, which gave 18. Across the five runs, 33 claims were never read by Reflection and were left out of the positives.

### R-4 — Can a battery definition live in a JSON file under the skill folder?

**Where:** `docs/spec-jev.md` S-52 · layout of the claim and evidence batteries
**Find out:** whether the portable export carries a non-Markdown file under the skill folder.
**Confidence:** high — read in this checkout on 2026-09-21.
**Review:** none.
**Status:** answered 2026-09-21
**Answer:** No. `scripts/validate_skill.py` reads only SKILL.md (frontmatter, name, description,
body length), so an extra folder would validate; but `scripts/harness.py` builds the export from
SKILL.md, `references/*.md`, the scripts named in RUNTIME_SCRIPTS, the agent files, fire.md and
spec-v1.md. A judge/claim.json would be silently absent from a bundled runtime and no test
would catch it. The batteries are therefore module constants inside scripts/judge.py, with a
`questions` subcommand that prints the questions object for the calibration tool.

### R-5 — Are Jev's price, context limit and model id still what we recorded?

**Where:** `docs/spec-jev.md` S-52 adapter constants · USD_PER_M_INPUT, MODEL, the 64k limit
**Find out:** the current price per million input tokens, the per-request context limit, and
whether `jev-1.13.0` is still accepted, before any cost estimate or threshold is published.
**Confidence:** medium — $0.042 per 1M input tokens with free output, 64k per request (32k for
state plus the longest single question) and the dated model id all come from research run
65a47056 on 2026-09-21, which read the vendor's own pages. They were not re-read in this session,
and the vendor says limits "can change without notice".
**Review:** none; S-53 re-checks live with `GET /v1/models` and records the `model` field the API
returns, and the calibration note carries both with the date.
**Status:** partly answered 2026-09-22 in S-53
**Answer:** the model id holds. Every one of 218 responses reported `jev-1.13.0`, though `GET /v1/models` now lists only jev-latest and jev-preview, so the dated id is accepted without being advertised. The price was not re-read from the vendor page. $0.042/M is still the recorded figure; the tokens the API reported came to $0.0085 at that rate. The 64k limit was not exercised, because the largest state stayed far below it.

### R-6 — Is the key exported in the shell profile the same one pasted into chat?

**Where:** session setup for S-53 · TYPESAFE_API_KEY
**Find out:** whether one key or two exist, so that rotating the pasted one does not silently
break a working profile, or leave a second live key in a transcript.
**Confidence:** low — the two cannot be compared without printing a secret, which is not done.
What is known: `~/.zshrc` contains an `export TYPESAFE_API_KEY=` line, and a non-interactive tool
shell does not read `.zshrc`, so the variable was absent from every command in this session.
**Review:** Abhishek. The pasted key is rotated after S-53 either way, because a key that has
appeared in a transcript is treated as exposed.
**Status:** answered 2026-09-22 in S-53
**Answer:** one key. The key the shell profile exports appears in this session's own transcript, so it is the key pasted into chat. This was checked with a fixed-string search that printed only a match count, never the key, and the key is not in any commit on any branch. Rotating it therefore breaks the profile until the new key replaces that line.

### R-7 — Is a resolution's frozen diff sha intended, or a defect?

**Where:** bug 25 · `scripts/done.py` `_valid_resolution` and `resolve` · `diff_sha`
**Find out:** whether rule 7 of the code-writer-council ("A blocking finding is closed by a fix
(new diff sha) or by the user's exact words") means the sha is a receipt of the moment the fix was
made, or a promise about the diff that is finally shipped. The answer decides whether S-50 adds a
staleness check or closes the bug as working as intended.
**Confidence:** medium that it is a defect: `done.py` checks the sha's shape and never compares it
with the diff it is about to call done, so an edit that undoes the fix still passes with the old
line in place.
**Review:** Abhishek decides; the rule is his.
**Status:** open
**Answer:**

### R-8 — What shape does a Jev noul answer arrive in?

**Where:** jev seam, `docs/spec-jev.md` S-52 · `scripts/judge.py` `probability` · `answers[<name>]`
**Find out:** whether `answers["supported"]` is the probability itself or an object carrying it
under `noul`. The two readers in the jev skill disagree:
`~/.claude/skills/jev/scripts/calibrate.py:147` uses `answers[c["id"]]["answers"][name]` as a
number, while `~/.claude/skills/jev/scripts/optimize_questions.py:69` reads
`answers[c["id"]]["answers"][name]["noul"]`. If the wrong one is assumed, a decision is made on
a dictionary compared as a number, or a probability is never found at all.
**Confidence:** low — no live response has been seen in this repository, and the only two
sources available contradict each other. `scripts/judge.py` therefore accepts both shapes and
raises on anything else, so an unexpected body prints `skipped: adapter ...` and the run
proceeds on today's path instead of on a wrong decision.
**Review:** answered by the first live call in S-53; the response body is pasted into this flag.
**Status:** answered 2026-09-22 in S-53
**Answer:** an object: `{"type": "noul", "noul": 0.97}`, taken from the first cached answer. `probability` in scripts/judge.py already reads the `noul` key, so no code change was needed. calibrate.py reads the same key, and the calibrate.py:147 reading in the question above was mistaken.

### R-9 — How often does the phone-number pattern stop an ordinary technical excerpt?

**Where:** jev seam, `docs/spec-jev.md` S-52 · `scripts/judge.py` `EGRESS` · pattern `phone`
**Find out:** the share of this repository's own claims whose assembled state matches
`\+?\d[\d\s().-]{8,}\d`. That pattern is deliberately broad, and a run of digits, spaces, dots
and dashes is also what a version list, a benchmark table or a date range looks like. A high
share means the guard is not protecting anything in practice, it is simply turning the judge
off, and the pattern should be narrowed to digit runs that are not separated by other words.
**Confidence:** medium that some false stops exist; none measured, because no cases file exists
yet. A false stop is safe in the egress direction: it prints `skipped` and the run proceeds.
**Review:** none. The `cases` exporter in S-53 prints how many records each guard excluded, so
the number is a by-product of the step that already has to run.
**Status:** answered 2026-09-22 in S-68 (PR #68)
**Answer:** 65%, and not one of them a phone number. The exporter was not needed: `build_claim_state`
and the two run folders under AGI_Research/runs/ were already enough to count it. Measured over all
57 claims on `main` 2a48552 — the pattern stopped 37, with 54 matches of 22 distinct spans. Twenty-
eight of those spans are the ISO date 2026-09-09, sixteen are arXiv ids of the shape 2601.15195, one
is the benchmark range 80.9--95.2, and none is a written telephone number. So the guard was not
protecting this repository's data, it was switching the judge off for two runs in three, which is
what this flag was opened to check for. Narrowed in S-68 to ten digits, the shortest dialable number
(a North American one without its country code; E.164 caps at fifteen), which leaves 1 of 57 claims
stopped and keeps all twelve written forms of a real number in `tests/test_judge.py`. The one
remaining stop is honest rather than fixed: the git log excerpt `8aaece4 2026-09-09 06:27:27 +0530`
runs a date, a time and a timezone offset together into eleven digits, and every rule measured that
cleared it also let `(555) 123 4567` through.

### R-10 — What shape does a Jev choice or score answer arrive in?

**Where:** jev seam, `docs/spec-jev.md` S-55 · `scripts/judge.py` `answer_value` · the evidence
battery's `strength` and `relevance` questions
**Find out:** what a live `POST /v1/systemone` puts in `answers` for a question of type `choice`
and for one of type `score`: the bare option string and the bare level, or an object keyed by the
type as R-8 saw for `noul`, or something else again, and whether a choice answer carries a
probability beside the chosen option. Only a real response settles it. If a choice answer does
carry a probability, `judge.jsonl` should record that too rather than the option alone, because a
`strength` of `vendor` at 0.34 is a different fact from one at 0.98.
**Confidence:** low. The `noul` shape was read from the jev skill's own scripts (R-8) and even
that disagrees with itself; no script in this repository or in that skill reads a choice or a
score answer at all, so this is a guess from the API's documented answer types.
**Review:** higher model, `scripts/judge.py` `answer_value`. Both shapes are accepted and an
option outside the battery's own list or a level outside its own scale raises, so an unknown body
is a `skipped: adapter ...` line and never a source strength written from a guess. The first live
evidence-battery call answers it, as it does R-8.
**Status:** open
**Answer:**
