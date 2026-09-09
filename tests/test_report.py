import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import budget  # noqa: E402
import claims  # noqa: E402
import evidence  # noqa: E402
import report  # noqa: E402

REPORT_SCRIPT = ROOT / "scripts" / "report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "run_min"
REPORT_MD = ROOT / "skills" / "research-council" / "references" / "report.md"
UNVERIFIED_STATEMENT = "The upstream API also had an outage that morning."


def sections(text):
    """{'heading': body} for every '## ' section."""
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:]
            out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return out


def run_cli(*args):
    return subprocess.run([sys.executable, str(REPORT_SCRIPT), *args], capture_output=True, text=True)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        shutil.copytree(FIXTURE, self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def jsonl(self, name):
        return [json.loads(l) for l in (self.run / name).read_text(encoding="utf-8").splitlines() if l.strip()]

    # acceptance 1
    def test_claim_without_evidence_appears_only_under_unverified(self):
        sec = sections(report.findings(self.run))
        self.assertIn(UNVERIFIED_STATEMENT, sec["Unverified"])
        for name, body in sec.items():
            if name != "Unverified":
                self.assertNotIn(UNVERIFIED_STATEMENT, body, name)
                self.assertNotIn("C-3", body, name)

    # acceptance 2
    def test_handoff_has_an_ears_line(self):
        lines = [l for l in report.handoff(self.run).splitlines() if l.startswith("WHEN ") and " SHALL " in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("THEN", lines[0])
        self.assertNotIn(". is measured", lines[0])

    def test_verified_claims_link_evidence_id_to_locator(self):
        body = sections(report.findings(self.run))["What we found"]
        self.assertIn("**C-1**", body)
        self.assertIn("[E-1] call export, rows 4,410-4,460", body)
        self.assertIn("[E-2] assistant config history, revision r42, 03:58 UTC", body)

    def test_how_sure_lists_type_and_limitations_for_verified_claims_only(self):
        body = sections(report.findings(self.run))["How sure"]
        self.assertIn("C-1: observed. Limitations: One hour window checked, not the full day.", body)
        self.assertIn("C-2: inferred. Limitations: none stated", body)
        self.assertNotIn("C-3", body)

    def test_refuted_hypotheses_and_noise_sparks_under_did_not_work(self):
        sec = sections(report.findings(self.run))
        body = sec["What we tried that did not work"]
        self.assertIn("H3 Callers were routed to a different assistant that has no lookup tool. (refuted)", body)
        self.assertIn("SP-1 Fifteen calls at 04:20 still reached the lookup tool. (did not repeat)", body)
        self.assertNotIn("SP-2", body)
        self.assertIn("SP-2 Partial status lookups quadrupled on the outage day. (spark in VARY)",
                      sec["What is still unknown"])

    def test_handoff_chosen_is_top_rated_open_and_beat_is_next(self):
        body = sections(report.handoff(self.run))["Chosen approach"]
        self.assertIn("Chosen: H2 The tool was switched off", body)
        self.assertIn("Beat: H1 The upstream repair-order API was failing", body)
        self.assertIn("H2       1208    1 open", body)

    def test_files_come_only_from_file_evidence(self):
        evidence.add(self.run, {"source_type": "web", "source_uri": "https://example.test/status", "title": "status page",
                                "locator": "section 2", "excerpt": "all systems normal", "access_scope": "public"})
        body = sections(report.handoff(self.run))["Files likely touched"]
        self.assertIn("- config/assistant_history.json\n- export/calls_2026-08-12.csv", body)
        self.assertNotIn("example.test", body)

    def test_must_not_is_prohibited_actions_verbatim(self):
        g = json.loads((self.run / "goal.json").read_text(encoding="utf-8"))
        body = sections(report.handoff(self.run))["Must not"]
        for action in g["prohibited_actions"]:
            self.assertIn(f"- {action}", body)

    def test_spend_line_comes_from_budget(self):
        body = sections(report.findings(self.run))["Spend"]
        self.assertIn(budget.line(budget.status(self.run)), body)
        self.assertIn("3/200 actions, 1/4 subagents, ~$0.40/$5 (unmetered: 1)", body)

    # must not: every line traceable to a record or to fixed text in report.py
    def test_every_line_traceable_to_records_or_fixed_text(self):
        g = json.loads((self.run / "goal.json").read_text(encoding="utf-8"))
        hyps = json.loads((self.run / "hypotheses.json").read_text(encoding="utf-8"))["hypotheses"]
        sparks = json.loads((self.run / "spark.json").read_text(encoding="utf-8"))["sparks"]
        sources = [g["request_text"], g["desired_outcome"], g["scope"], g["goal_id"], *g["unknowns"],
                   *g["prohibited_actions"]]
        sources += [c[k].rstrip(".") for c in g["success_criteria"] for k in c]
        sources += [c["statement"] for c in self.jsonl("claims.jsonl")]
        sources += [c["limitations"] for c in self.jsonl("claims.jsonl") if c["limitations"]]
        objs = json.loads((self.run / "objections.json").read_text(encoding="utf-8"))["objections"]
        sources += [o["resolve_with"] for o in objs]
        sources += [r[k] for r in self.jsonl("evidence.jsonl") for k in ("title", "locator", "source_uri")]
        sources += [h["statement"][:40] for h in hyps]
        sources += [s["observation"] for s in sparks]
        sources += [budget.line(budget.status(self.run))]
        sources = [s for s in sources if len(s) >= 8]
        fixed = list(report.FIXED.values())
        for text in (report.findings(self.run), report.handoff(self.run)):
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line == "```":
                    continue
                ok = any(s in line for s in sources) or any(f in line for f in fixed)
                self.assertTrue(ok, f"untraceable line: {line!r}")

    def test_no_claim_statement_is_reworded(self):
        text = report.findings(self.run)
        for c in self.jsonl("claims.jsonl"):
            self.assertEqual(text.count(c["statement"]), 1, c["claim_id"])

    # S-18 acceptance: a superseded claim shows only under Superseded, its replacement under What we found
    def test_superseded_claim_appears_only_under_superseded(self):
        claims.supersede(self.run, "C-1", "C-2", "C-2 explains the gap; C-1 counted one hour")
        sec = sections(report.findings(self.run))
        self.assertIn("- C-1 No repair-order lookup calls were attempted between 04:00 and 05:00 UTC "
                      "on the outage day. Superseded by C-2: C-2 explains the gap; C-1 counted one hour",
                      sec["Superseded"])
        self.assertIn("**C-2**", sec["What we found"])
        for name, body in sec.items():
            if name != "Superseded":
                self.assertNotIn("C-1", body, name)

    def test_superseded_lines_stay_traceable(self):
        claims.supersede(self.run, "C-1", "C-2", "C-2 explains the gap")
        fixed = list(report.FIXED.values())
        for line in sections(report.findings(self.run))["Superseded"].splitlines():
            if line.strip():
                self.assertTrue(any(f in line for f in fixed), line)

    # S-17 acceptance: a claim under a blocking objection shows only under Disputed
    def block(self, claim_id, blocking=True):
        p = self.run / "objections.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["objections"].append({"id": "O-2", "claim_ids": [claim_id], "hypothesis_id": "H1",
                                "kind": "provenance", "blocking": blocking,
                                "text": "count not in excerpt",
                                "resolve_with": "evidence: the rows themselves, locator = row numbers"})
        p.write_text(json.dumps(d), encoding="utf-8")

    def test_blocking_objection_moves_claim_to_disputed(self):
        self.block("C-2")
        sec = sections(report.findings(self.run))
        self.assertIn("- C-2 The lookup tool was disabled in configuration revision r42 two minutes "
                      "before the outage began. Objection O-2: evidence: the rows themselves, "
                      "locator = row numbers", sec["Disputed"])
        self.assertIn("**C-1**", sec["What we found"])
        for name, body in sec.items():
            if name != "Disputed":
                self.assertNotIn("C-2", body, name)

    def test_non_blocking_objection_changes_nothing(self):
        sec = sections(report.findings(self.run))
        self.assertIn(report.NONE, sec["Disputed"])
        self.assertIn("**C-2**", sec["What we found"])
        self.assertNotIn("O-1", report.findings(self.run))

    def test_blocked_unverified_claim_stays_under_unverified(self):
        self.block("C-3")
        sec = sections(report.findings(self.run))
        self.assertIn("C-3", sec["Unverified"])
        self.assertNotIn("C-3", sec["Disputed"])

    def test_blocked_superseded_claim_stays_under_superseded(self):
        self.block("C-1")
        claims.supersede(self.run, "C-1", "C-2", "C-2 explains the gap")
        sec = sections(report.findings(self.run))
        self.assertIn("C-1", sec["Superseded"])
        self.assertNotIn("C-1", sec["Disputed"])

    def test_missing_objections_file_is_one_fixed_line(self):
        (self.run / "objections.json").unlink()
        sec = sections(report.findings(self.run))
        self.assertIn(report.FIXED["no_objections_file"], sec["Disputed"])
        self.assertIn("**C-2**", sec["What we found"])

    def test_malformed_objections_file_is_one_fixed_line_and_ignored(self):
        (self.run / "objections.json").write_text('{"objections": [{"id": "O-9"}]}', encoding="utf-8")
        sec = sections(report.findings(self.run))
        self.assertIn(report.FIXED["bad_objections_file"], sec["Disputed"])
        self.assertIn("**C-2**", sec["What we found"])
        (self.run / "objections.json").write_text("not json", encoding="utf-8")
        self.assertIn(report.FIXED["bad_objections_file"], sections(report.findings(self.run))["Disputed"])

    def test_blocking_must_be_json_true_not_a_truthy_string(self):
        self.block("C-2", blocking="true")
        sec = sections(report.findings(self.run))
        self.assertIn(report.FIXED["bad_objections_file"], sec["Disputed"])
        self.assertIn("**C-2**", sec["What we found"])

    def test_disputed_lines_stay_traceable_and_claims_file_untouched(self):
        before = (self.run / "claims.jsonl").read_bytes()
        self.block("C-2")
        fixed = list(report.FIXED.values())
        for line in sections(report.findings(self.run))["Disputed"].splitlines():
            if line.strip():
                self.assertTrue(any(f in line for f in fixed), line)
        self.assertEqual((self.run / "claims.jsonl").read_bytes(), before)

    # robustness
    def test_missing_hypotheses_and_sparks_render_none_recorded(self):
        (self.run / "hypotheses.json").unlink()
        (self.run / "spark.json").unlink()
        f, h = report.findings(self.run), report.handoff(self.run)
        self.assertIn("- Whether the upstream API has its own error log for that window.", f)
        self.assertIn(report.NONE, sections(h)["Chosen approach"])
        self.assertNotIn("```", h)

    def test_tampered_goal_is_refused_and_nothing_written(self):
        p = self.run / "goal.json"
        g = json.loads(p.read_text(encoding="utf-8"))
        g["budget"]["usd_estimate_cap"] = 500
        p.write_text(json.dumps(g), encoding="utf-8")
        r = run_cli("--run", str(self.run))
        self.assertEqual(r.returncode, 1)
        self.assertIn("frozen_sha256", r.stderr)
        self.assertFalse((self.run / report.FINDINGS).exists())
        self.assertFalse((self.run / report.HANDOFF).exists())

    def test_cli_writes_exactly_the_two_files(self):
        before = {p.name for p in self.run.iterdir()}
        r = run_cli("--run", str(self.run))
        self.assertEqual(r.returncode, 0, r.stderr)
        after = {p.name for p in self.run.iterdir()}
        self.assertEqual(after - before, {report.FINDINGS, report.HANDOFF})
        self.assertEqual(r.stdout.strip().splitlines(), [str(self.run / report.FINDINGS), str(self.run / report.HANDOFF)])
        for name in before:
            self.assertEqual((self.run / name).read_bytes(), (FIXTURE / name).read_bytes(), name)

    def test_report_md_names_every_section(self):
        doc = REPORT_MD.read_text(encoding="utf-8")
        for h in ("What you asked", "What we found", "Unverified", "Superseded", "How sure", "What we tried that did not work",
                  "What is still unknown", "What to build now", "Spend", "Chosen approach", "Acceptance",
                  "Files likely touched", "Must not"):
            self.assertIn(h, doc)
        self.assertIn("scripts/report.py", doc)


if __name__ == "__main__":
    unittest.main()
