import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evals  # noqa: E402

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def task(tid, kind="golden", **over):
    body = {"id": tid, "kind": kind, "request": f"why did {tid} fail",
            "known_answer": "the config flag was off", "source": "run 622aeb79",
            "rubric": [{"id": "R1", "text": "names the flag", "match": r"config(uration)? flag"},
                       {"id": "R2", "text": "does not blame the API", "must_not_match": r"upstream api"}]}
    body.update(over)
    return body


class EvalsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.tasks, self.sessions = base / "tasks", base / "sessions"
        self.tasks.mkdir()
        self.put(task("T-01", files={"notes/source.md": "The API was fine."}), task("T-02", "trap"))

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, *bodies):
        for body in bodies:
            (self.tasks / f"{body['id']}.json").write_text(json.dumps(body), encoding="utf-8")

    def start(self, usd=4, minutes=60, runs=2):
        return evals.start("s1", usd, minutes, runs, self.tasks, self.sessions, now=T0)

    def answer(self, text):
        path = Path(self.tmp.name) / "answer.md"
        path.write_text(text, encoding="utf-8")
        return path

    def rec(self, tid, arm, run, text="The config flag was off.", cost=0.5):
        return evals.record("s1", tid, arm, run, self.answer(text), cost, 5, self.sessions)

    # tasks
    def test_a_bad_task_is_refused_with_every_problem(self):
        self.put(task("T-03", kind="easy", rubric=[{"id": "R1", "text": "x", "match": "(",
                                                    "must_not_match": "y"}]),
                 task("T-04", files={"../escape.md": "x"}))
        (self.tasks / "T-05.json").write_text(json.dumps(task("T-9")), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            evals.load_tasks(self.tasks)
        text = str(caught.exception)
        for part in ("T-03: kind", "T-03: each rubric item", "T-04: files", "T-05: id must be"):
            self.assertIn(part, text)

    def test_a_bad_regex_and_repeated_rubric_ids_are_refused(self):
        self.put(task("T-03", rubric=[{"id": "R1", "text": "x", "match": "("},
                                      {"id": "R1", "text": "y", "match": "z"}]))
        with self.assertRaises(ValueError) as caught:
            evals.load_tasks(self.tasks)
        self.assertIn("T-03: rubric R1 is not a valid regular expression", str(caught.exception))
        self.assertIn("T-03: rubric ids repeat", str(caught.exception))

    def test_scoring_is_case_insensitive_and_must_not_match_fails_on_a_hit(self):
        t = task("T-01")
        self.assertEqual(evals.score(t, "The CONFIGURATION FLAG was off"), {"R1": True, "R2": True})
        self.assertEqual(evals.score(t, "The upstream API broke"), {"R1": False, "R2": False})

    def test_the_repo_task_folder_validates_and_complete_needs_the_full_set(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "evals.py"), "validate", "--complete"],
                           capture_output=True, text=True)
        found = evals.counts(evals.load_tasks())
        full = all(found[k] >= v for k, v in evals.COMPLETE.items())
        self.assertEqual(r.returncode, 0 if full else 1, r.stderr)
        self.assertEqual(evals.COMPLETE, {"total": 20, "trap": 2, "mind_change": 1})

    # plan
    def test_the_plan_pairs_arms_and_alternates_who_goes_first(self):
        steps = evals.plan(["T-02", "T-01"], 2)
        self.assertEqual(len(steps), 8)
        firsts = [steps[i][1] for i in range(0, 8, 2)]
        self.assertEqual(firsts, ["plain", "council", "council", "plain"])
        for i in range(0, 8, 2):
            self.assertEqual(steps[i][0::2], steps[i + 1][0::2])
            self.assertNotEqual(steps[i][1], steps[i + 1][1])

    def test_start_needs_user_caps_and_happens_once(self):
        for usd, minutes, runs in ((0, 60, 1), (5, -1, 1), (True, 60, 1), (5, 60, 0)):
            with self.assertRaises(ValueError):
                evals.start("bad", usd, minutes, runs, self.tasks, self.sessions)
        self.assertFalse((self.sessions / "bad").exists())
        session = self.start()
        self.assertEqual(session["caps"], {"usd": 4, "minutes": 60, "set_by": "user"})
        self.assertEqual(set(session["tasks"]), {"T-01", "T-02"})
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.start()
        with self.assertRaisesRegex(ValueError, "letters, digits"):
            evals.start("../x", 1, 1, 1, self.tasks, self.sessions)

    # next and record
    def test_next_gives_both_arms_the_same_share_and_the_planted_files(self):
        self.start()
        status, info = evals.next_run("s1", self.sessions, now=T0 + timedelta(minutes=12))
        self.assertEqual((status, info["task"], info["arm"], info["run"]), ("run", "T-01", "plain", 1))
        self.assertEqual(info["share"], {"usd": 0.5, "minutes": 6.0})
        self.assertEqual((Path(info["workspace"]) / "notes/source.md").read_text(encoding="utf-8"),
                         "The API was fine.")
        self.rec("T-01", "plain", 1, cost=1.0)
        status, info = evals.next_run("s1", self.sessions, now=T0 + timedelta(minutes=12))
        self.assertEqual((info["arm"], info["share"]), ("council", {"usd": 3 / 7, "minutes": 48 / 7}))

    def test_record_must_follow_the_plan_and_the_frozen_task(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "next planned run is T-01 plain run 1"):
            self.rec("T-01", "council", 1)
        for cost, minutes in ((-1, 5), (True, 5), (0.1, -2)):
            with self.assertRaises(ValueError):
                evals.record("s1", "T-01", "plain", 1, self.answer("x"), cost, minutes, self.sessions)
        with self.assertRaisesRegex(ValueError, "empty"):
            self.rec("T-01", "plain", 1, text="  ")
        self.put(task("T-01", request="changed"))
        with self.assertRaisesRegex(ValueError, "T-01 changed since start"):
            self.rec("T-01", "plain", 1)
        self.assertFalse((self.sessions / "s1" / "results.jsonl").exists())

    def test_a_cap_stops_next_but_never_stops_recording(self):
        self.start(usd=1)
        self.rec("T-01", "plain", 1, cost=1.5)
        status, info = evals.next_run("s1", self.sessions, now=T0)
        self.assertEqual((status, info["over"]), ("cap", ["usd"]))
        line = self.rec("T-01", "council", 1, text="The upstream API.", cost=None)
        self.assertEqual(line["passed"], {"R1": False, "R2": False})
        status, info = evals.next_run("s1", self.sessions, now=T0 + timedelta(minutes=61))
        self.assertEqual(info["over"], ["usd", "minutes"])

    def test_summary_compares_complete_pairs_only_and_says_when_partial(self):
        self.start(runs=1)
        self.rec("T-01", "plain", 1, text="The upstream API.", cost=None)
        self.rec("T-01", "council", 1)
        self.rec("T-02", "council", 1)
        out = evals.summary("s1", self.sessions, now=T0 + timedelta(minutes=30))
        self.assertEqual(out, [
            "runs: 3 of 4 planned",
            "council: 2 runs, mean rubric 1.00, fully passed 2",
            "plain: 1 runs, mean rubric 0.00, fully passed 0",
            "paired tasks: 1; council better 1, plain better 0, equal 0",
            "spent: $1.00/$4, 30/60 min (unmetered: 1)",
            "incomplete: a partial plan says nothing about the tasks it did not reach"])
        self.rec("T-02", "plain", 1)
        self.assertEqual(evals.next_run("s1", self.sessions)[0], "done")
        self.assertNotIn("incomplete", " ".join(evals.summary("s1", self.sessions)))
