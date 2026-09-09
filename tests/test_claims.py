import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import claims  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402

SCRIPT = ROOT / "scripts" / "claims.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
EVIDENCE_MD = ROOT / "skills" / "research-council" / "references" / "evidence.md"
EV = {"source_type": "file", "source_uri": "logs/api.log", "title": "API log", "locator": "line 4",
      "excerpt": "status=500", "access_scope": "public"}


def claim(statement, evidence_ids):
    return {"statement": statement, "claim_type": "observed", "scope": "api.log",
            "evidence_ids": evidence_ids, "test_ids": [], "limitations": ""}


class SupersedeTests(unittest.TestCase):
    """S-18: a wrong claim is superseded, never edited or deleted (bug 6)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = goal.new(Path(self.tmp.name), json.loads(FIXTURE.read_text()))
        evidence.add(self.run, EV)
        claims.add(self.run, claim("37 requests failed", ["E-1"]))       # C-1
        claims.add(self.run, claim("41 requests failed", ["E-1"]))       # C-2
        claims.add(self.run, claim("the retry loop doubles load", []))   # C-3 unverified
        self.before = (self.run / claims.FILENAME).read_text(encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--run", str(self.run)],
                              capture_output=True, text=True)

    def file(self):
        return (self.run / claims.FILENAME).read_text(encoding="utf-8")

    def test_supersede_appends_one_record_and_rewrites_nothing(self):
        rec = claims.supersede(self.run, "C-1", "C-2", "C-2 counts the full day")
        self.assertEqual(rec, {"claim_id": "C-1", "superseded_by": "C-2", "reason": "C-2 counts the full day"})
        self.assertTrue(self.file().startswith(self.before))
        self.assertEqual(json.loads(self.file().splitlines()[-1]), rec)

    def test_read_carries_superseded_by_and_list_marks_it(self):
        claims.supersede(self.run, "C-1", "C-2", "C-2 counts the full day")
        by_id = {c["claim_id"]: c for c in claims.read(self.run)}
        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id["C-1"]["superseded_by"], "C-2")
        self.assertNotIn("superseded_by", by_id["C-2"])
        out = self.cli("list").stdout
        self.assertIn("C-1 observed [E-1] 37 requests failed [superseded by C-2]", out)
        self.assertIn("C-2 observed [E-1] 41 requests failed\n", out)

    def test_by_without_evidence_is_refused_and_nothing_written(self):
        with self.assertRaises(ValueError) as cm:
            claims.supersede(self.run, "C-1", "C-3", "any")
        self.assertIn("C-3 has no evidence", str(cm.exception))
        self.assertEqual(self.file(), self.before)

    def test_unknown_ids_are_refused(self):
        with self.assertRaises(ValueError) as cm:
            claims.supersede(self.run, "C-9", "C-8", "any")
        self.assertIn("unknown claim_id: C-9", str(cm.exception))
        self.assertIn("unknown claim_id: C-8", str(cm.exception))
        self.assertEqual(self.file(), self.before)

    def test_self_supersede_and_empty_reason_are_refused(self):
        with self.assertRaises(ValueError):
            claims.supersede(self.run, "C-1", "C-1", "any")
        with self.assertRaises(ValueError):
            claims.supersede(self.run, "C-1", "C-2", " ")
        self.assertEqual(self.file(), self.before)

    def test_a_claim_is_superseded_once(self):
        claims.supersede(self.run, "C-1", "C-2", "first")
        claims.add(self.run, claim("40 requests failed", ["E-1"]))  # C-4
        with self.assertRaises(ValueError) as cm:
            claims.supersede(self.run, "C-1", "C-4", "second")
        self.assertIn("already superseded by C-2", str(cm.exception))

    def test_next_claim_id_ignores_supersede_records(self):
        claims.supersede(self.run, "C-1", "C-2", "first")
        self.assertEqual(claims.add(self.run, claim("40 requests failed", ["E-1"]))["claim_id"], "C-4")

    def test_cli_exit_codes(self):
        ok = self.cli("supersede", "--claim", "C-1", "--by", "C-2", "--reason", "full day")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.strip(), "C-1 superseded by C-2")
        bad = self.cli("supersede", "--claim", "C-2", "--by", "C-3", "--reason", "x")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("C-3 has no evidence", bad.stderr)

    def test_evidence_md_documents_the_command(self):
        text = " ".join(EVIDENCE_MD.read_text(encoding="utf-8").split())
        self.assertIn("scripts/claims.py supersede --run AGI_Research/runs/<goal_id> --claim C-1 --by C-4", text)
        self.assertIn("the original line stays as written", text)


if __name__ == "__main__":
    unittest.main()
