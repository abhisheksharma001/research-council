import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evidence  # noqa: E402
import goal  # noqa: E402
import spark  # noqa: E402

SPARK_SCRIPT = ROOT / "scripts" / "spark.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
FIRE_MD = ROOT / "strategies" / "fire.md"
CURIOSITY_MD = ROOT / "skills" / "research-council" / "references" / "curiosity.md"

BEFORE = "Tool-call attempts continue at normal volume but carry error results."
NARROWER = "Tool-call attempts continue at normal volume but carry error results only when the config revision is r42."
EVIDENCE = {"source_type": "file", "source_uri": "export/calls.csv", "title": "call export",
            "locator": "rows 10-20", "excerpt": "status=error x11", "access_scope": "private"}


def run_cli(*args):
    return subprocess.run([sys.executable, str(SPARK_SCRIPT), *args], capture_output=True, text=True)


class SparkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = goal.new(Path(self.tmp.name), json.loads(FIXTURE.read_text(encoding="utf-8")))
        hyps = [{"id": "H1", "status": "open"}, {"id": "H2", "status": "open"}]
        (self.run / "hypotheses.json").write_text(json.dumps({"hypotheses": hyps, "investigations": []}),
                                                  encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def open_spark(self):
        return spark.new(self.run, "errors appeared with tool calls at normal volume", BEFORE, ["H1"])["id"]

    def repeat(self, sid, ok=True, times=1):
        for i in range(times):
            spark.trial(self.run, sid, "repeat", ok, f"repeat {i}")

    def to_vary(self, sid):
        spark.advance(self.run, sid, "REPEAT")
        self.repeat(sid, True, 2)
        spark.advance(self.run, sid, "VARY")

    def to_boundary(self, sid, after=None):
        self.to_vary(sid)
        spark.trial(self.run, sid, "vary", False, "no errors", condition="config revision r41")
        return spark.advance(self.run, sid, "BOUNDARY", after)

    def get(self, sid):
        return spark._find(spark.load(self.run), sid)

    # new
    def test_new_starts_in_spark_with_no_progress_and_no_trials(self):
        s = spark.new(self.run, "obs", BEFORE, ["H1", "H2"])
        self.assertEqual((s["id"], s["state"], s["progress"], s["trials"]), ("SP-1", "SPARK", False, []))
        self.assertIsNone(s["prediction_after"])
        self.assertEqual(spark.new(self.run, "obs 2", BEFORE, ["H2"])["id"], "SP-2")

    def test_new_refuses_unknown_hypothesis_and_missing_hypotheses_file(self):
        with self.assertRaises(ValueError):
            spark.new(self.run, "obs", BEFORE, ["H9"])
        with self.assertRaises(ValueError):
            spark.new(self.run, "obs", BEFORE, [])
        (self.run / "hypotheses.json").unlink()
        with self.assertRaises(ValueError):
            spark.new(self.run, "obs", BEFORE, ["H1"])
        self.assertFalse((self.run / spark.FILENAME).exists())

    # trials
    def test_trial_kind_must_match_state(self):
        sid = self.open_spark()
        with self.assertRaises(ValueError):
            spark.trial(self.run, sid, "repeat", True, "too early: still in SPARK")
        spark.advance(self.run, sid, "REPEAT")
        with self.assertRaises(ValueError):
            spark.trial(self.run, sid, "vary", True, "wrong kind", condition="x")
        spark.trial(self.run, sid, "repeat", True, "fine now")
        self.assertEqual(len(self.get(sid)["trials"]), 1)

    def test_vary_trial_needs_condition_and_evidence_id_must_exist(self):
        sid = self.open_spark()
        self.to_vary(sid)
        with self.assertRaises(ValueError):
            spark.trial(self.run, sid, "vary", True, "no condition named")
        with self.assertRaises(ValueError):
            spark.trial(self.run, sid, "vary", True, "bad evidence", condition="c", evidence_id="E-1")
        eid = evidence.add(self.run, EVIDENCE)["evidence_id"]
        rec = spark.trial(self.run, sid, "vary", True, "good", condition="c", evidence_id=eid)
        self.assertEqual(rec["evidence_id"], "E-1")

    # advance: acceptance
    def test_advance_to_boundary_with_one_repeat_says_need_2_repeats(self):
        sid = self.open_spark()
        spark.advance(self.run, sid, "REPEAT")
        self.repeat(sid, True, 1)
        r = run_cli("advance", "--run", str(self.run), "--spark", sid, "--to", "BOUNDARY")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("need 2 repeats", r.stderr)
        self.assertEqual(self.get(sid)["state"], "REPEAT")

    def test_advance_to_boundary_with_two_repeats_and_one_failed_variation(self):
        sid = self.open_spark()
        self.to_vary(sid)
        spark.trial(self.run, sid, "vary", False, "no errors", condition="config revision r41")
        r = run_cli("advance", "--run", str(self.run), "--spark", sid, "--to", "BOUNDARY")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.get(sid)["state"], "BOUNDARY")

    def test_advance_to_boundary_needs_a_failed_variation(self):
        sid = self.open_spark()
        self.to_vary(sid)
        spark.trial(self.run, sid, "vary", True, "still errors", condition="different caller")
        with self.assertRaisesRegex(ValueError, "failed variation"):
            spark.advance(self.run, sid, "BOUNDARY")
        self.assertEqual(self.get(sid)["state"], "VARY")

    def test_failed_repeats_do_not_count_as_repeats(self):
        sid = self.open_spark()
        spark.advance(self.run, sid, "REPEAT")
        self.repeat(sid, False, 3)
        with self.assertRaisesRegex(ValueError, "need 2 repeats"):
            spark.advance(self.run, sid, "VARY")

    def test_advance_only_forward_and_noise_only_from_repeat_with_failed_repeat(self):
        sid = self.open_spark()
        with self.assertRaises(ValueError):
            spark.advance(self.run, sid, "NOISE")
        spark.advance(self.run, sid, "REPEAT")
        with self.assertRaises(ValueError):
            spark.advance(self.run, sid, "SPARK")
        with self.assertRaises(ValueError):
            spark.advance(self.run, sid, "REPEAT")
        with self.assertRaisesRegex(ValueError, "failed repeat"):
            spark.advance(self.run, sid, "NOISE")
        self.repeat(sid, False, 1)
        self.assertEqual(spark.advance(self.run, sid, "NOISE")["state"], "NOISE")
        with self.assertRaises(ValueError):
            spark.advance(self.run, sid, "VARY")

    def test_combine_needs_prediction_after_and_name_needs_combine_trial(self):
        sid = self.open_spark()
        self.to_boundary(sid)
        with self.assertRaisesRegex(ValueError, "prediction_after"):
            spark.advance(self.run, sid, "COMBINE")
        sid2 = self.open_spark()
        self.to_boundary(sid2, NARROWER)
        spark.advance(self.run, sid2, "COMBINE")
        with self.assertRaisesRegex(ValueError, "combine trial"):
            spark.advance(self.run, sid2, "NAME")
        spark.trial(self.run, sid2, "combine", False, "with retry skill: no change")
        self.assertEqual(spark.advance(self.run, sid2, "NAME")["state"], "NAME")

    # progress (invariant 7)
    def test_progress_only_when_scope_narrowed(self):
        sid = self.open_spark()
        s = self.to_boundary(sid, NARROWER)
        self.assertTrue(s["progress"])
        self.assertEqual(s["prediction_after"], NARROWER)

    def test_progress_not_for_novelty_volume_or_confidence(self):
        cases = {"novelty": "The configuration was switched off at 04:00 UTC.",
                 "volume": BEFORE + " We saw this many, many times across hundreds of calls.",
                 "confidence": "Tool-call attempts definitely, certainly carry error results.",
                 "same": BEFORE}
        for name, after in cases.items():
            sid = self.open_spark()
            s = self.to_boundary(sid, after)
            self.assertFalse(s["progress"], name)

    def test_prediction_after_only_written_at_boundary(self):
        sid = self.open_spark()
        with self.assertRaises(ValueError):
            spark.advance(self.run, sid, "REPEAT", NARROWER)
        self.assertEqual(self.get(sid)["state"], "SPARK")
        self.assertIsNone(self.get(sid)["prediction_after"])

    def test_narrowed_is_a_pure_string_test(self):
        self.assertTrue(spark.narrowed("x fails", "X fails only when y is on."))
        self.assertTrue(spark.narrowed("x fails.", "When y is on, x fails"))
        self.assertFalse(spark.narrowed("x fails", "x fails"))
        self.assertFalse(spark.narrowed("x fails", "x fails a lot"))
        self.assertFalse(spark.narrowed("x fails", "y fails when z"))

    # isolation
    def test_spark_never_touches_hypotheses_or_claims(self):
        (self.run / "claims.jsonl").write_text('{"claim_id": "C-1"}\n', encoding="utf-8")
        before = {n: (self.run / n).read_bytes() for n in ("hypotheses.json", "claims.jsonl")}
        sid = self.open_spark()
        self.to_boundary(sid, NARROWER)
        for n, b in before.items():
            self.assertEqual((self.run / n).read_bytes(), b, n)

    # cli
    def test_cli_round_trip_and_status(self):
        r = run_cli("new", "--run", str(self.run), "--observation", "obs", "--prediction_before", BEFORE,
                    "--hypotheses", "H1,H2")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "SP-1 SPARK"), r.stderr)
        self.assertEqual(run_cli("advance", "--run", str(self.run), "--spark", "SP-1", "--to", "REPEAT").returncode, 0)
        r = run_cli("trial", "--run", str(self.run), "--spark", "SP-1", "--kind", "repeat", "--ok", "--detail", "d")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "SP-1 REPEAT repeat 1 ok/0 failed, vary 0 ok/0 failed, combine 0, progress no")
        r = run_cli("status", "--run", str(self.run), "--spark", "SP-1")
        self.assertEqual(json.loads(r.stdout)["hypothesis_ids"], ["H1", "H2"])
        r = run_cli("new", "--run", str(self.run), "--observation", "obs", "--prediction_before", BEFORE,
                    "--hypotheses", "H7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown hypothesis id: H7", r.stderr)

    # docs
    def test_fire_md_names_every_state_and_curiosity_md_names_the_triggers(self):
        fire = FIRE_MD.read_text(encoding="utf-8")
        for state in spark.STATES + (spark.NOISE,):
            self.assertIn(state, fire)
        cur = CURIOSITY_MD.read_text(encoding="utf-8")
        self.assertIn("predicted_result", cur)
        self.assertIn("16", cur)
        self.assertIn("scripts/spark.py", cur)


if __name__ == "__main__":
    unittest.main()
