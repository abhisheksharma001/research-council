import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import claims  # noqa: E402
import evidence  # noqa: E402
import goal  # noqa: E402
import harness  # noqa: E402
import journal  # noqa: E402
import judge  # noqa: E402

SCRIPT = ROOT / "scripts" / "judge.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
FAKES = ROOT / "tests" / "fixtures" / "judge"
SKILL_MD = ROOT / "skills" / "research-council" / "SKILL.md"
STATEMENT = "The booking service returns a confirmation code when a slot is held."
EXCERPT = ("Every held slot is answered with a confirmation code; the booking service returns "
           "that code to the caller before the hold expires.")


class _Response:
    """The object urlopen hands back, with only the two methods the adapter uses."""

    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def explode(*args, **kwargs):
    raise AssertionError("the adapter was called")


class JudgeTests(unittest.TestCase):
    """S-52: the seam, the claim battery and shadow mode."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = goal.new(self.root, self.body())
        self.opt_in(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def body(self, **budget):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["budget"].update(budget)
        return data

    def opt_in(self, root):
        path = root / judge.OPT_IN
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"enabled_by": "A Reviewer", "date": "2026-09-21",
                                    "terms_read": True}), encoding="utf-8")

    def claim(self, statement=STATEMENT, excerpt=EXCERPT, scope="public", uri="https://example.org/docs"):
        evidence.add(self.run, {"source_type": "web", "source_uri": uri, "title": "Booking docs",
                                "locator": "Holds, paragraph two", "excerpt": excerpt,
                                "access_scope": scope})
        record = claims.add(self.run, {"statement": statement, "claim_type": "observed",
                                       "scope": "the booking service", "evidence_ids": ["E-1"],
                                       "test_ids": [], "limitations": ""})
        return record["claim_id"]

    def cli(self, *args, key=None):
        env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if key is not None:
            env["TYPESAFE_API_KEY"] = key
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, env=env)

    def with_key(self):
        """A key in the environment, so a test can reach the stop that follows the no-key one."""
        return mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "not-a-real-key"})

    def records(self):
        path = self.run / judge.FILENAME
        return [] if not path.is_file() else [json.loads(x) for x in
                                              path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def judged(self):
        return [e for e in journal.read(self.run) if e["kind"] == "judge"]

    def listing(self):
        return {str(p.relative_to(self.run)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.run.rglob("*")) if p.is_file()}

    # --- the stops, in the order judge.py takes them -------------------------------------

    def test_a_run_folder_outside_the_run_root_is_not_enabled(self):
        elsewhere = self.root / "scratch"
        elsewhere.mkdir()
        (elsewhere / "goal.json").write_text((self.run / "goal.json").read_text(encoding="utf-8"),
                                             encoding="utf-8")
        line, record = judge.run_battery(elsewhere, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: not enabled")
        self.assertIsNone(record)

    def test_without_the_opt_in_file_the_run_folder_stays_byte_identical(self):
        self.claim()
        (self.root / judge.OPT_IN).unlink()
        before = self.listing()
        result = self.cli("run", "--run", self.run, "--battery", "claim", "--id", "C-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "judge: claim C-1 skipped: not enabled")
        self.assertEqual(self.listing(), before)

    def test_a_zero_dollar_cap_skips_before_the_adapter(self):
        self.run = goal.new(self.root, self.body(usd_estimate_cap=0))
        self.claim()
        line, record = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: budget")
        self.assertIsNone(record)
        self.assertEqual(self.judged(), [])

    def test_an_action_cap_with_no_room_left_skips(self):
        self.run = goal.new(self.root, self.body(max_actions=1))
        self.claim()
        journal.add(self.run, "fetch", None, "one action already spent")
        line, _ = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: budget")

    def test_a_private_record_skips_before_any_request_is_built(self):
        self.claim(scope="private")
        line, record = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: egress private E-1")
        self.assertIsNone(record)
        self.assertFalse((self.run / judge.FILENAME).exists())

    def test_a_home_path_in_the_state_is_an_egress_skip(self):
        self.claim(uri="file:///Users/someone/notes/booking.md")
        line, _ = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: egress home path")

    def test_an_address_in_an_excerpt_is_an_egress_skip(self):
        self.claim(excerpt=EXCERPT + " Ask support@example.org for the code format.")
        line, _ = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 skipped: egress address")

    def test_no_key_skips_and_writes_nothing(self):
        self.claim()
        result = self.cli("run", "--run", self.run, "--battery", "claim", "--id", "C-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "judge: claim C-1 skipped: no key")
        self.assertEqual(self.records(), [])
        self.assertEqual(self.judged(), [])

    def test_an_adapter_error_is_a_skipped_line_not_a_crash(self):
        self.claim()

        def broken(request, timeout=None):
            raise OSError("connection reset by peer")

        with self.with_key():
            line, record = judge.run_battery(self.run, "claim", "C-1", opener=broken)
        self.assertEqual(line, "judge: claim C-1 skipped: adapter connection reset by peer")
        self.assertIsNone(record)
        self.assertEqual(self.judged(), [])

    def test_an_answer_short_of_a_question_is_a_skipped_line(self):
        self.claim()
        line, _ = judge.run_battery(self.run, "claim", "C-1", adapter="fake",
                                    fake_answers=FAKES / "incomplete.json")
        self.assertEqual(line,
                         "judge: claim C-1 skipped: adapter no answer for contradicted, wider, inferred")

    # --- the rule that needs no call ------------------------------------------------------

    def test_a_number_in_no_excerpt_is_a_no_decided_in_code(self):
        self.claim(statement="The booking service holds a slot for 15 minutes.",
                   excerpt="The booking service holds a slot for 10 minutes.")
        line, record = judge.run_battery(self.run, "claim", "C-1", opener=explode)
        self.assertEqual(line, "judge: claim C-1 no (rule: number 15 not in any excerpt)")
        self.assertEqual(record["decision"], "no")
        self.assertEqual(record["adapter"], "rule")
        self.assertEqual(record["cost_usd"], 0.0)
        self.assertEqual(len(self.judged()), 1)

    def test_a_number_the_excerpt_carries_reaches_the_adapter(self):
        self.claim(statement="The booking service holds a slot for 10 minutes.",
                   excerpt="The booking service holds a slot for 10 minutes before releasing it.")
        line, _ = judge.run_battery(self.run, "claim", "C-1", adapter="fake",
                                    fake_answers=FAKES / "unsupported.json")
        self.assertEqual(line, "judge: claim C-1 unsure")

    def test_numbers_missing_ignores_thousands_commas(self):
        self.assertEqual(judge.numbers_missing("1,200 requests", ["up to 1200 requests"]), [])
        self.assertEqual(judge.numbers_missing("1,200 requests", ["up to 900 requests"]), ["1200"])

    # --- a recorded decision --------------------------------------------------------------

    def test_the_fake_adapter_records_unsure_and_one_metered_judge_line(self):
        self.claim()
        line, record = judge.run_battery(self.run, "claim", "C-1", adapter="fake",
                                         fake_answers=FAKES / "unsupported.json")
        self.assertEqual(line, "judge: claim C-1 unsure")
        self.assertEqual(record["decision"], "unsure")
        self.assertEqual(record["answers"]["supported"], 0.05)
        self.assertEqual(record["mode"], "shadow")
        self.assertEqual(self.records(), [record])
        entries = self.judged()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["cost_usd"], 0.0000257)
        self.assertIn("judge claim C-1 unsure model=jev-1.13.0", entries[0]["detail"])

    def test_a_call_that_happened_is_metered_even_when_the_record_cannot_be_written(self):
        self.claim()
        (self.run / judge.FILENAME).mkdir()  # appending to a folder fails, so the record write does
        with self.assertRaisesRegex(ValueError, "could not be recorded"):
            judge.run_battery(self.run, "claim", "C-1", adapter="fake",
                              fake_answers=FAKES / "unsupported.json")
        self.assertEqual(len(self.judged()), 1)

    def test_a_noul_shaped_answer_is_read_as_a_probability(self):
        self.claim()
        _, record = judge.run_battery(self.run, "claim", "C-1", adapter="fake",
                                      fake_answers=FAKES / "noul-shape.json")
        self.assertEqual(record["answers"]["supported"], 0.93)

    def test_the_jev_adapter_pins_the_model_and_measures_the_cost(self):
        self.claim()
        sent = {}

        def opener(request, timeout=None):
            sent["url"] = request.full_url
            sent["body"] = json.loads(request.data.decode("utf-8"))
            sent["auth"] = request.get_header("Authorization")
            return _Response({"model": "jev-1.13.0",
                              "answers": {"supported": 0.91, "contradicted": 0.02,
                                          "wider": 0.05, "inferred": 0.07},
                              "usage": {"input_tokens": 1000}})

        with self.with_key():
            line, record = judge.run_battery(self.run, "claim", "C-1", opener=opener)
        self.assertEqual(line, "judge: claim C-1 unsure")
        self.assertEqual(sent["url"], judge.BASE_URL + "/v1/systemone")
        self.assertEqual(sent["body"]["model"], "jev-1.13.0")
        self.assertEqual(sorted(sent["body"]["questions"]),
                         ["contradicted", "inferred", "supported", "wider"])
        self.assertEqual(sent["body"]["state"]["claim"]["statement"], STATEMENT)
        self.assertEqual(sent["auth"], "Bearer not-a-real-key")
        self.assertEqual(record["input_tokens"], 1000)
        self.assertAlmostEqual(record["cost_usd"], 0.042 / 1000)

    def test_the_state_carries_only_the_claim_and_its_excerpts(self):
        self.claim()
        state, cited = judge.build_claim_state(self.run, "C-1")
        self.assertEqual(sorted(state), ["claim", "evidence"])
        self.assertEqual(sorted(state["claim"]), ["claim_type", "scope", "statement"])
        self.assertEqual(sorted(state["evidence"][0]), ["excerpt", "id", "locator", "uri"])
        self.assertEqual([r["evidence_id"] for r in cited], ["E-1"])

    # --- decisions and thresholds ---------------------------------------------------------

    def test_without_fitted_thresholds_every_answered_decision_is_unsure(self):
        self.assertIsNone(judge.BATTERIES["claim"]["fitted"])
        self.assertIsNone(judge.BATTERIES["claim"]["thresholds"])
        self.assertEqual(judge.decide({"supported": 0.99, "contradicted": 0.0,
                                       "wider": 0.0, "inferred": 0.0}, None), "unsure")

    def test_decide_reads_the_four_answers_the_way_the_spec_writes_it(self):
        bands = {name: {"low": 0.2, "high": 0.8}
                 for name in ("supported", "contradicted", "wider", "inferred")}
        clean = {"supported": 0.9, "contradicted": 0.05, "wider": 0.1, "inferred": 0.1}
        self.assertEqual(judge.decide(clean, bands), "yes")
        self.assertEqual(judge.decide({**clean, "supported": 0.15}, bands), "no")
        self.assertEqual(judge.decide({**clean, "contradicted": 0.85}, bands), "no")
        self.assertEqual(judge.decide({**clean, "wider": 0.85}, bands), "no")
        self.assertEqual(judge.decide({**clean, "inferred": 0.5}, bands), "unsure")

    # --- bad input ------------------------------------------------------------------------

    def test_an_unknown_claim_id_exits_1(self):
        self.claim()
        result = self.cli("run", "--run", self.run, "--battery", "claim", "--id", "C-9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown claim_id: C-9", result.stderr)

    def test_an_unknown_battery_exits_1(self):
        result = self.cli("questions", "--battery", "severity")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown battery: severity", result.stderr)

    def test_a_task_only_run_exits_1(self):
        task_run = self.root / "AGI_Research" / "runs" / "code-1"
        task_run.mkdir(parents=True)
        (task_run / "task.json").write_text("{}\n", encoding="utf-8")
        result = self.cli("run", "--run", task_run, "--battery", "claim", "--id", "C-1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no goal.json", result.stderr)

    def test_gate_mode_exits_1_until_thresholds_exist(self):
        self.claim()
        result = self.cli("run", "--run", self.run, "--battery", "claim", "--id", "C-1",
                          "--mode", "gate")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no fitted thresholds", result.stderr)
        self.assertEqual(self.records(), [])

    def test_the_fake_adapter_needs_a_file(self):
        self.claim()
        result = self.cli("run", "--run", self.run, "--battery", "claim", "--id", "C-1",
                          "--adapter", "fake")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--fake-answers", result.stderr)

    # --- the questions, and the wiring around the script ----------------------------------

    def test_questions_prints_the_battery_for_the_calibration_tool(self):
        result = self.cli("questions", "--battery", "claim")
        self.assertEqual(result.returncode, 0, result.stderr)
        questions = json.loads(result.stdout)
        self.assertEqual(sorted(questions), ["contradicted", "inferred", "supported", "wider"])
        for name, question in questions.items():
            with self.subTest(question=name):
                self.assertEqual(question["type"], "noul")
                self.assertTrue(question["instructions"].strip())
                self.assertTrue(question["criteria"]["true"].strip())
                self.assertTrue(question["criteria"]["false"].strip())

    def test_judge_is_a_harness_tool_and_a_bundled_script(self):
        self.assertIn("judge", harness.TOOLS)
        bundled = [str(relative) for _, relative in harness.resources()]
        self.assertIn("runtime/scripts/judge.py", bundled)
        self.assertIn("references/judge.md", bundled)

    def test_the_skill_runs_the_judge_after_a_claim_is_recorded(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertLess(text.index("scripts/claims.py add"),
                        text.index("scripts/judge.py run --run <run> --battery claim"))
        self.assertIn("references/judge.md", text)


if __name__ == "__main__":
    unittest.main()
