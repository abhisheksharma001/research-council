import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import budget  # noqa: E402
import goal  # noqa: E402
import journal  # noqa: E402
import task  # noqa: E402

BUDGET_SCRIPT = ROOT / "scripts" / "budget.py"
JOURNAL_SCRIPT = ROOT / "scripts" / "journal.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"


def body():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = goal.new(self.root, body())  # caps: 60 min, 200 actions, 4 subagents, $5

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, kind, cost=None, n=1):
        for _ in range(n):
            journal.add(self.run, kind, cost, f"{kind} entry")

    # journal.py
    def test_journal_add_appends_line_with_timestamp(self):
        self.log("fetch", 0.1)
        self.log("note")
        entries = journal.read(self.run)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["kind"], "fetch")
        self.assertEqual(entries[0]["cost_usd"], 0.1)
        self.assertIsNone(entries[1]["cost_usd"])
        datetime.fromisoformat(entries[0]["ts"])

    def test_journal_rejects_unknown_kind(self):
        with self.assertRaisesRegex(ValueError, "invalid kind: 'think'"):
            journal.add(self.run, "think", None, "x")
        self.assertEqual(journal.read(self.run), [])

    def test_journal_requires_goal(self):
        with self.assertRaisesRegex(ValueError, "no goal.json"):
            journal.add(self.root / "nowhere", "fetch", None, "x")

    def test_parse_cost(self):
        self.assertIsNone(journal.parse_cost("null"))
        self.assertEqual(journal.parse_cost("0.40"), 0.4)
        with self.assertRaisesRegex(ValueError, "invalid cost_usd"):
            journal.parse_cost("free")
        with self.assertRaisesRegex(ValueError, "invalid cost_usd"):
            journal.parse_cost("-1")

    def test_cost_parser_rejects_nonfinite_values(self):
        for value in ("nan", "inf", "-inf", "1e999"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "cost_usd"):
                journal.parse_cost(value)

    def test_journal_api_rejects_invalid_cost_without_writing(self):
        for value in (float("nan"), float("inf"), float("-inf"), -1, True, "1", {}, 10 ** 1000):
            with self.subTest(value=str(value)[:20]), self.assertRaisesRegex(ValueError, "cost_usd"):
                journal.add(self.run, "exec", value, "invalid fixture cost")
        self.assertFalse((self.run / "journal.jsonl").exists())

    def test_nonfinite_cost_cli_is_refused(self):
        result = subprocess.run([sys.executable, str(JOURNAL_SCRIPT), "add", "--run", str(self.run),
                                 "--kind", "exec", "--cost_usd", "nan", "--detail", "invalid fixture cost"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cost_usd", result.stderr)
        self.assertFalse((self.run / "journal.jsonl").exists())

    def test_budget_refuses_legacy_invalid_or_missing_cost(self):
        for value in (float("nan"), float("inf"), -1, True, "1", {}):
            entry = {"ts": goal._now(), "kind": "exec", "detail": "legacy fixture", "cost_usd": value}
            (self.run / "journal.jsonl").write_text(json.dumps(entry) + "\n")
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "cost_usd"):
                budget.status(self.run)
        (self.run / "journal.jsonl").write_text(json.dumps({"kind": "exec", "detail": "missing cost"}) + "\n")
        with self.assertRaisesRegex(ValueError, "cost_usd"):
            budget.status(self.run)

    def test_loaded_nonfinite_cap_is_refused_even_with_consistent_hash(self):
        g = goal.load(self.run)
        g["budget"]["usd_estimate_cap"] = float("nan")
        g["frozen_sha256"] = goal.freeze(g)
        (self.run / "goal.json").write_text(json.dumps(g))
        with self.assertRaisesRegex(ValueError, "budget"):
            budget.status(self.run)

    def test_cost_total_overflow_is_refused(self):
        self.log("exec", 1e308, n=2)
        with self.assertRaisesRegex(ValueError, "cost"):
            budget.status(self.run)

    # budget.py
    def test_status_line_format(self):
        self.log("fetch", 0.25, n=3)
        self.log("subagent", None, n=2)
        self.log("note", None)
        created = datetime.fromisoformat(goal.load(self.run)["created_at"])
        st = budget.status(self.run, now=created + timedelta(minutes=12, seconds=30))
        self.assertEqual(budget.line(st),
                         "spent: 12/60 min, 5/200 actions, 2/4 subagents, ~$0.75/$5 (unmetered: 3)")
        self.assertEqual(st["exceeded"], [])

    def stamp(self, *offsets):
        """Write journal.jsonl with one read entry at each offset in minutes from created_at."""
        created = datetime.fromisoformat(goal.load(self.run)["created_at"])
        marks = [created + timedelta(minutes=m) for m in offsets]
        (self.run / journal.FILENAME).write_text(
            "".join(json.dumps({"ts": m.isoformat(), "kind": "read", "cost_usd": None,
                                "detail": "read entry"}) + "\n" for m in marks),
            encoding="utf-8")
        return created, marks

    def test_the_longest_quiet_stretch_is_reported_beside_the_wall_clock(self):
        created, marks = self.stamp(2, 5, 293, 295)
        st = budget.status(self.run, now=created + timedelta(minutes=313))
        self.assertEqual(st["spent"]["minutes"], 313)
        self.assertEqual(st["exceeded"], ["minutes"])
        self.assertEqual(st["longest_gap"], (288, marks[2].isoformat()))
        self.assertEqual(budget.pause_line(st),
                         "minutes are wall clock since created_at; "
                         f"longest quiet stretch: 288 min, ending {marks[2].isoformat()}")
        # the CLI reads the real clock, so its minutes differ; the quiet stretch does not
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", str(self.run)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[1], budget.pause_line(st))

    def test_a_pause_before_the_first_entry_is_a_quiet_stretch(self):
        created, marks = self.stamp(40, 41)
        st = budget.status(self.run, now=created + timedelta(minutes=42))
        self.assertEqual(st["longest_gap"], (40, marks[0].isoformat()))

    def test_an_empty_journal_has_no_quiet_stretch(self):
        st = budget.status(self.run)
        self.assertIsNone(st["longest_gap"])
        self.assertIsNone(budget.pause_line(st))
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", str(self.run)],
                           capture_output=True, text=True)
        self.assertEqual(len(r.stdout.splitlines()), 1, r.stdout)

    def test_judge_is_a_metered_action_from_the_cli(self):
        r = subprocess.run([sys.executable, str(JOURNAL_SCRIPT), "add", "--run", str(self.run),
                            "--kind", "judge", "--cost_usd", "0.00002",
                            "--detail", "judge claim C-1 unsure"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        st = budget.status(self.run)
        self.assertEqual(st["spent"]["max_actions"], 1)
        self.assertEqual(st["spent"]["usd_estimate_cap"], 0.00002)
        self.assertEqual(st["spent"]["max_subagents"], 0)
        self.assertEqual(st["exceeded"], [])

    def test_note_is_not_an_action(self):
        self.log("note", None, n=5)
        self.assertEqual(budget.status(self.run)["spent"]["max_actions"], 0)

    def test_disconfirm_names_hypotheses_and_is_not_an_action(self):
        entry = journal.add(self.run, "disconfirm", None, "searched for errors", ["H1"])
        self.assertEqual(entry["hypothesis_ids"], ["H1"])
        self.assertEqual(budget.status(self.run)["spent"]["max_actions"], 0)

    def test_disconfirm_without_hypothesis_rejected(self):
        with self.assertRaisesRegex(ValueError, "--hypothesis"):
            journal.add(self.run, "disconfirm", None, "searched for errors")
        with self.assertRaisesRegex(ValueError, "only for kind disconfirm"):
            journal.add(self.run, "note", None, "a note", ["H1"])

    def test_empty_journal_is_zero_not_error(self):
        st = budget.status(self.run)
        self.assertEqual(st["spent"]["max_actions"], 0)
        self.assertEqual(st["unmetered"], 0)

    def test_actions_exceed_names_cap(self):
        self.log("read", None, n=201)
        self.assertEqual(budget.status(self.run)["exceeded"], ["max_actions"])

    def test_at_cap_is_not_exceeded(self):
        self.log("read", None, n=200)
        self.assertEqual(budget.status(self.run)["exceeded"], [])

    def test_subagents_exceed_names_cap(self):
        self.log("subagent", 0.01, n=5)
        self.assertEqual(budget.status(self.run)["exceeded"], ["max_subagents"])

    def test_minutes_exceed_names_cap(self):
        created = datetime.fromisoformat(goal.load(self.run)["created_at"])
        st = budget.status(self.run, now=created + timedelta(minutes=61))
        self.assertEqual(st["exceeded"], ["minutes"])

    def test_usd_exceed_names_cap_and_nulls_count_zero(self):
        self.log("fetch", 3.0)
        self.log("fetch", 2.5)
        self.log("fetch", None, n=4)
        st = budget.status(self.run)
        self.assertEqual(st["spent"]["usd_estimate_cap"], 5.5)
        self.assertEqual(st["unmetered"], 4)
        self.assertEqual(st["exceeded"], ["usd_estimate_cap"])

    def test_zero_usd_cap_exceeded_by_first_metered_cost(self):
        b = body()
        b["budget"]["usd_estimate_cap"] = 0
        run = goal.new(self.root / "zero", b)
        journal.add(run, "fetch", None, "unmetered")
        self.assertEqual(budget.status(run)["exceeded"], [])
        journal.add(run, "fetch", 0.01, "metered")
        self.assertEqual(budget.status(run)["exceeded"], ["usd_estimate_cap"])

    def test_hand_raised_cap_is_refused(self):
        path = self.run / "goal.json"
        g = json.loads(path.read_text())
        g["budget"]["max_actions"] = 10_000
        path.write_text(json.dumps(g))
        with self.assertRaisesRegex(ValueError, "frozen_sha256 mismatch"):
            budget.status(self.run)

    def test_missing_cap_has_no_default(self):
        path = self.run / "goal.json"
        g = json.loads(path.read_text())
        del g["budget"]["usd_estimate_cap"]
        del g["frozen_sha256"]
        g["frozen_sha256"] = goal.freeze(g)  # consistent hash, but a cap is gone
        path.write_text(json.dumps(g))
        with self.assertRaisesRegex(ValueError, "budget missing: usd_estimate_cap"):
            budget.status(self.run)

    def test_goal_without_budget_rejected_by_goal_new(self):
        b = body()
        del b["budget"]
        with self.assertRaisesRegex(ValueError, "missing field: budget"):
            goal.new(self.root / "other", b)

    def test_cli_exit_codes(self):
        run = str(self.run)
        r = subprocess.run([sys.executable, str(JOURNAL_SCRIPT), "add", "--run", run, "--kind",
                            "exec", "--cost_usd", "null", "--detail", "pytest"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, str(JOURNAL_SCRIPT), "add", "--run", run, "--kind",
                            "guess", "--cost_usd", "null", "--detail", "x"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid kind", r.stderr)
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", run],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("spent: 0/60 min, 1/200 actions, 0/4 subagents, "
                                            "~$0.00/$5 (unmetered: 1)"), r.stdout)
        self.log("subagent", None, n=5)
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", run],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("exceeded: max_subagents (5/4)", r.stderr)
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run",
                            str(self.root / "nowhere")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


class TaskBudgetTests(unittest.TestCase):
    """S-37: budget.py meters a code-writer-council run (task.json) with the same caps and exit codes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.run = task.new(self.root, {
            "request_text": "rename a flag", "test_command": "python3 -m unittest",
            "allowed_paths": ["scripts/triage.py"], "max_diff_lines": 40,
            "expected_small": True, "explain": False,
            "budget": {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0,
                       "set_by": "user"}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_line_for_a_task_run(self):
        journal.add(self.run, "exec", None, "tests")
        created = datetime.fromisoformat(task.load(self.run)["created_at"])
        st = budget.status(self.run, now=created + timedelta(minutes=3))
        self.assertEqual(budget.line(st), "spent: 3/20 min, 1/60 actions, 0/3 subagents, ~$0.00/$0 (unmetered: 1)")
        self.assertEqual(st["exceeded"], [])

    def test_hand_edited_task_is_refused(self):
        path = self.run / "task.json"
        t = json.loads(path.read_text())
        t["budget"]["max_actions"] = 10_000
        path.write_text(json.dumps(t))
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", str(self.run)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("frozen_sha256 mismatch", r.stderr)

    def test_task_missing_cap_has_no_default(self):
        path = self.run / "task.json"
        t = json.loads(path.read_text())
        del t["budget"]["max_subagents"]
        t["frozen_sha256"] = goal.freeze(t)  # consistent hash, but a cap is gone
        path.write_text(json.dumps(t))
        with self.assertRaisesRegex(ValueError, "task.json budget missing: max_subagents"):
            budget.status(self.run)

    def test_task_caps_exceed_exit_2(self):
        for _ in range(4):
            journal.add(self.run, "subagent", None, "reviewer")
        r = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "check", "--run", str(self.run)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("exceeded: max_subagents (4/3)", r.stderr)

    def test_task_zero_usd_cap_exceeded_by_first_metered_cost(self):
        journal.add(self.run, "fetch", None, "unmetered")
        self.assertEqual(budget.status(self.run)["exceeded"], [])
        journal.add(self.run, "fetch", 0.01, "metered")
        self.assertEqual(budget.status(self.run)["exceeded"], ["usd_estimate_cap"])


CAPS_TABLES = (
    ROOT / "skills" / "research-council" / "references" / "budget.md",
    ROOT / "skills" / "code-writer-council" / "references" / "task.md",
)


class CapsTableTests(unittest.TestCase):
    def test_each_max_actions_row_names_the_kinds_budget_counts(self):
        for path in CAPS_TABLES:
            with self.subTest(path=path.name):
                rows = [l for l in path.read_text(encoding="utf-8").splitlines()
                        if l.startswith("| `max_actions` |")]
                self.assertEqual(len(rows), 1, f"{path.name}: no single max_actions row")
                listed = rows[0].split("journal lines of kind ", 1)[1].split(" (", 1)[0]
                kinds = {k.strip() for k in listed.split(",")}
                self.assertEqual(kinds, set(journal.ACTION_KINDS), path.name)


if __name__ == "__main__":
    unittest.main()
