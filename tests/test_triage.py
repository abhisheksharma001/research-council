import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import triage  # noqa: E402

SCRIPT = ROOT / "scripts" / "triage.py"


def ans(**kw):
    a = {"q1": False, "q2": False, "q3": False, "q4": False, "q5": False}
    a.update(kw)
    return a


class TriageTests(unittest.TestCase):
    def test_all_no_is_small_and_lists_failed_questions(self):
        r = triage.triage(ans())
        self.assertEqual(r["verdict"], "small")
        joined = " ".join(r["reasons"])
        for q in ("q1", "q2", "q3", "q5"):
            self.assertIn(f"{q}: no", joined)

    def test_explicit_ask_is_big(self):
        r = triage.triage(ans(q4=True))
        self.assertEqual(r["verdict"], "big")
        self.assertIn("q4", r["reasons"][0])

    def test_two_of_four_is_big(self):
        r = triage.triage(ans(q1=True, q5=True))
        self.assertEqual(r["verdict"], "big")
        self.assertEqual(len(r["reasons"]), 2)

    def test_one_of_four_is_small(self):
        r = triage.triage(ans(q2=True))
        self.assertEqual(r["verdict"], "small")
        self.assertIn("only 1 of 4", r["reasons"][0])

    def test_missing_answer_raises(self):
        with self.assertRaises(ValueError):
            triage.triage({"q1": True})

    def test_non_bool_raises(self):
        with self.assertRaises(ValueError):
            triage.triage(ans(q1="yes"))

    def test_cli_exit_codes(self):
        big = subprocess.run([sys.executable, str(SCRIPT), "--answers", "-"],
                             input=json.dumps(ans(q4=True)), capture_output=True, text=True)
        self.assertEqual(big.returncode, 0, big.stdout)
        self.assertEqual(json.loads(big.stdout)["verdict"], "big")
        small = subprocess.run([sys.executable, str(SCRIPT), "--answers", "-"],
                               input=json.dumps(ans()), capture_output=True, text=True)
        self.assertEqual(small.returncode, 3, small.stdout)
        bad = subprocess.run([sys.executable, str(SCRIPT), "--answers", "-"],
                             input="{not json", capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
