import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import claims  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402

EVIDENCE_SCRIPT = ROOT / "scripts" / "evidence.py"
CLAIMS_SCRIPT = ROOT / "scripts" / "claims.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"


def ev(**over):
    body = {"source_type": "command", "source_uri": "grep -c 'status=500' api.log",
            "title": "API log", "locator": "lines 1-4120", "excerpt": "37",
            "access_scope": "private"}
    body.update(over)
    return body


def cl(**over):
    body = {"statement": "37 of 4120 requests returned 500", "claim_type": "observed",
            "scope": "api.log only", "evidence_ids": ["E-1"], "test_ids": [],
            "limitations": "one day of logs"}
    body.update(over)
    return body


def run_cli(script, *args, stdin=None):
    return subprocess.run([sys.executable, str(script), *args], input=stdin,
                          capture_output=True, text=True)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = goal.new(self.root, json.loads(FIXTURE.read_text(encoding="utf-8")))

    def tearDown(self):
        self.tmp.cleanup()

    # evidence.py
    def test_evidence_add_writes_record_with_id_time_and_sha(self):
        rec = evidence.add(self.run, ev())
        self.assertEqual(rec["evidence_id"], "E-1")
        self.assertEqual(rec["sha256"], hashlib.sha256(b"37").hexdigest())
        datetime.fromisoformat(rec["retrieved_at"])
        self.assertEqual(evidence.read(self.run), [rec])

    def test_evidence_ids_increment_from_highest(self):
        evidence.add(self.run, ev())
        evidence.add(self.run, ev(title="second"))
        self.assertEqual([r["evidence_id"] for r in evidence.read(self.run)], ["E-1", "E-2"])
        self.assertEqual(evidence.next_id(["E-7", "E-2"], "E-"), "E-8")
        self.assertEqual(evidence.next_id([], "E-"), "E-1")

    def test_evidence_requires_locator(self):
        for bad in (ev(locator=""), ev(locator="   ")):
            with self.assertRaisesRegex(ValueError, "locator"):
                evidence.add(self.run, bad)
        body = ev()
        del body["locator"]
        with self.assertRaisesRegex(ValueError, "missing field: locator"):
            evidence.add(self.run, body)
        self.assertEqual(evidence.read(self.run), [])

    def test_evidence_excerpt_limit_is_2000(self):
        evidence.add(self.run, ev(excerpt="x" * 2000))
        with self.assertRaisesRegex(ValueError, "excerpt \\(2001 chars, max 2000\\)"):
            evidence.add(self.run, ev(excerpt="x" * 2001))
        with self.assertRaisesRegex(ValueError, "excerpt"):
            evidence.add(self.run, ev(excerpt=""))
        self.assertEqual(len(evidence.read(self.run)), 1)

    def test_evidence_rejects_bad_enum_and_unknown_and_script_fields(self):
        errors = evidence.validate(ev(source_type="rumour", access_scope="secret"))
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("source_type" in e for e in errors))
        self.assertTrue(any("access_scope" in e for e in errors))
        self.assertEqual(evidence.validate(ev(evidence_id="E-9")), ["unknown field: evidence_id"])
        self.assertEqual(evidence.validate(ev(sha256="abc")), ["unknown field: sha256"])

    def test_evidence_requires_goal(self):
        with self.assertRaisesRegex(ValueError, "no goal.json"):
            evidence.add(self.root / "nowhere", ev())

    # claims.py
    def test_claim_add_links_existing_evidence(self):
        evidence.add(self.run, ev())
        c = claims.add(self.run, cl())
        self.assertEqual(c["claim_id"], "C-1")
        self.assertEqual(c["evidence_ids"], ["E-1"])
        self.assertEqual(claims.read(self.run), [c])

    def test_claim_with_unknown_evidence_exits_1_and_writes_nothing(self):
        evidence.add(self.run, ev())
        with self.assertRaisesRegex(ValueError, "unknown evidence_id: E-2"):
            claims.add(self.run, cl(evidence_ids=["E-1", "E-2"]))
        self.assertEqual(claims.read(self.run), [])
        self.assertFalse((self.run / "claims.jsonl").exists())

    def test_claim_without_evidence_is_stored_as_unverified(self):
        c = claims.add(self.run, cl(claim_type="inferred", evidence_ids=[]))
        self.assertEqual(claims.unverified(claims.read(self.run)), [c])
        self.assertEqual(claims.line(c), "C-1 inferred [unverified] 37 of 4120 requests returned 500")

    def test_list_unverified_prints_only_claims_without_evidence(self):
        evidence.add(self.run, ev())
        claims.add(self.run, cl())
        claims.add(self.run, cl(statement="retry loop doubles load", claim_type="inferred",
                                evidence_ids=[]))
        all_ = claims.read(self.run)
        self.assertEqual([c["claim_id"] for c in all_], ["C-1", "C-2"])
        self.assertEqual([c["claim_id"] for c in claims.unverified(all_)], ["C-2"])
        self.assertEqual(claims.line(all_[0]), "C-1 observed [E-1] 37 of 4120 requests returned 500")

    def test_claim_rejects_bad_type_duplicates_and_unknown_fields(self):
        evidence.add(self.run, ev())
        known = {"E-1"}
        self.assertEqual(claims.validate(cl(claim_type="guessed"), known),
                         ["invalid field: claim_type (one of observed, inferred, predicted)"])
        self.assertEqual(claims.validate(cl(evidence_ids=["E-1", "E-1"]), known),
                         ["invalid field: evidence_ids (duplicates)"])
        self.assertEqual(claims.validate(cl(claim_id="C-9"), known), ["unknown field: claim_id"])
        self.assertEqual(claims.validate(cl(limitations=None), known),
                         ["invalid field: limitations (must be a string)"])
        self.assertEqual(claims.read(self.run), [])

    def test_claim_requires_goal(self):
        with self.assertRaisesRegex(ValueError, "no goal.json"):
            claims.add(self.root / "nowhere", cl(evidence_ids=[]))

    # CLI
    def test_cli_exit_codes(self):
        run = str(self.run)
        ok = run_cli(EVIDENCE_SCRIPT, "add", "--run", run, "--from", "-", stdin=json.dumps(ev()))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.strip(), "E-1 recorded (command: API log)")

        no_loc = run_cli(EVIDENCE_SCRIPT, "add", "--run", run, "--from", "-",
                         stdin=json.dumps(ev(locator="")))
        self.assertEqual(no_loc.returncode, 1)
        self.assertIn("locator", no_loc.stderr)

        good = run_cli(CLAIMS_SCRIPT, "add", "--run", run, "--from", "-", stdin=json.dumps(cl()))
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(good.stdout.strip(), "C-1 recorded (1 evidence)")

        bad = run_cli(CLAIMS_SCRIPT, "add", "--run", run, "--from", "-",
                      stdin=json.dumps(cl(evidence_ids=["E-9"])))
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(bad.stderr.strip(), "unknown evidence_id: E-9")

        unv = run_cli(CLAIMS_SCRIPT, "add", "--run", run, "--from", "-",
                      stdin=json.dumps(cl(statement="retry loop doubles load",
                                          claim_type="inferred", evidence_ids=[])))
        self.assertEqual(unv.returncode, 0, unv.stderr)

        listed = run_cli(CLAIMS_SCRIPT, "list", "--run", run, "--unverified")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(listed.stdout.strip(), "C-2 inferred [unverified] retry loop doubles load")
        self.assertEqual(len(claims.read(self.run)), 2)


if __name__ == "__main__":
    unittest.main()
