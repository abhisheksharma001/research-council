import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import coverage  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402
import report  # noqa: E402

SCRIPT = ROOT / "scripts" / "coverage.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
SKILL = ROOT / "skills" / "research-council"


def ev(uri="https://example.org/a", **over):
    body = {"source_type": "web", "source_uri": uri, "title": "t", "locator": "l",
            "excerpt": "x", "access_scope": "public"}
    body.update(over)
    return body


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = goal.new(Path(self.tmp.name), json.loads(FIXTURE.read_text(encoding="utf-8")))

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "check", "--run", str(self.run), *args],
                              capture_output=True, text=True)

    def test_a_source_is_a_distinct_uri_and_untagged_records_count_nowhere(self):
        evidence.add(self.run, ev("https://a.example/1", unknowns=[1]))
        evidence.add(self.run, ev("https://a.example/1", unknowns=[1, 2], excerpt="y"))
        evidence.add(self.run, ev("https://b.example/2", unknowns=[1]))
        evidence.add(self.run, ev("https://c.example/3"))
        rows = coverage.check(self.run, 2)
        self.assertEqual([(n, count) for n, count, _ in rows], [(1, 2), (2, 1)])

    def test_a_gap_exits_2_and_names_it_and_a_full_count_exits_0(self):
        evidence.add(self.run, ev("https://a.example/1", unknowns=[1, 2]))
        evidence.add(self.run, ev("https://b.example/2", unknowns=[1]))
        r = self.cli("--min", "2")
        self.assertEqual(r.returncode, 2, r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("U1 2/2 ok  Whether the assistant configuration"))
        self.assertTrue(lines[1].startswith("U2 1/2 gap Whether the upstream API"))
        self.assertEqual(lines[2], "coverage: 1 of 2 unknowns short")
        r = self.cli("--min", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[-1], "coverage: all 2 unknowns have 1 sources")

    def test_a_minimum_below_one_is_refused(self):
        r = self.cli("--min", "0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("at least 1", r.stderr)

    def test_evidence_refuses_a_bad_or_out_of_range_unknowns_field(self):
        for bad in ([], [0], ["1"], [True], [1, 1], 1, [1.0]):
            with self.assertRaisesRegex(ValueError, "invalid field: unknowns", msg=repr(bad)):
                evidence.add(self.run, ev(unknowns=bad))
        with self.assertRaisesRegex(ValueError, r"3 is above the goal's 2"):
            evidence.add(self.run, ev(unknowns=[1, 3]))
        self.assertEqual(evidence.read(self.run), [])
        task_run = Path(self.tmp.name) / "task-run"
        task_run.mkdir()
        (task_run / "task.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "only a goal run has unknowns"):
            evidence.add(task_run, ev(unknowns=[1]))

    def test_the_field_is_stored_only_when_given_and_exported(self):
        plain = evidence.add(self.run, ev())
        tagged = evidence.add(self.run, ev(unknowns=[2]))
        self.assertNotIn("unknowns", plain)
        self.assertEqual(tagged["unknowns"], [2])
        exported = report.structured_handoff(self.run)["evidence"]
        self.assertNotIn("unknowns", exported[0])
        self.assertEqual(exported[1]["unknowns"], [2])
        lines = (self.run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
        bad = json.loads(lines[1])
        bad["unknowns"] = [0]
        (self.run / "evidence.jsonl").write_text(lines[0] + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid field: unknowns"):
            report.structured_handoff(self.run)

    def test_the_procedure_runs_the_gate_before_the_report(self):
        skill = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
        step8 = skill.split("8. **Report.**")[1]
        self.assertLess(step8.index("scripts/coverage.py check"), step8.index("scripts/report.py"))
        council = (SKILL / "references" / "council.md").read_text(encoding="utf-8")
        self.assertIn("## Coverage gate", council)
        self.assertIn("| `unknowns` |", (SKILL / "references" / "evidence.md").read_text(encoding="utf-8"))
