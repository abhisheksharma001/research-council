import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fence  # noqa: E402
import goal  # noqa: E402
import journal  # noqa: E402
import task  # noqa: E402

SCRIPT = ROOT / "scripts" / "fence.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
COUNCIL_MD = ROOT / "skills" / "research-council" / "references" / "council.md"


class FenceTests(unittest.TestCase):
    """S-24: the after-spawn fence is a script, not a listing by eye."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = goal.new(Path(self.tmp.name), json.loads(FIXTURE.read_text()))
        (self.run / "hypotheses.json").write_text('{"hypotheses": []}\n')
        (self.run / "evidence.jsonl").write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, cmd, role):
        return subprocess.run([sys.executable, str(SCRIPT), cmd, "--run", str(self.run),
                               "--role", role], capture_output=True, text=True)

    def notes(self):
        return [e for e in journal.read(self.run) if e["kind"] == "note"]

    def test_reflection_new_file_exits_2_names_it_and_journals(self):
        self.assertEqual(self.cli("snapshot", "reflection").returncode, 0)
        (self.run / "extra.txt").write_text("hello")
        r = self.cli("check", "reflection")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("violation: reflection wrote extra.txt", r.stdout)
        self.assertEqual(len(self.notes()), 1)
        self.assertIn("reflection wrote extra.txt", self.notes()[0]["detail"])

    def test_generation_changing_only_hypotheses_exits_0(self):
        fence.snapshot(self.run, "generation")
        (self.run / "hypotheses.json").write_text('{"hypotheses": [{"id": "H1"}]}\n')
        r = self.cli("check", "generation")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.notes(), [])

    def test_generation_extra_file_names_only_the_extra_file(self):
        fence.snapshot(self.run, "generation")
        (self.run / "hypotheses.json").write_text('{"hypotheses": [{"id": "H1"}]}\n')
        (self.run / "claims.jsonl").write_text('{"claim_id": "C-1"}\n')
        self.assertEqual(fence.violations(self.run, "generation"), [("wrote", "claims.jsonl")])

    def test_changed_existing_file_is_a_violation(self):
        fence.snapshot(self.run, "ranking")
        (self.run / "evidence.jsonl").write_text('{"evidence_id": "E-1"}\n')
        self.assertEqual(fence.violations(self.run, "ranking"), [("wrote", "evidence.jsonl")])

    def test_removed_file_is_a_violation(self):
        fence.snapshot(self.run, "reflection")
        (self.run / "evidence.jsonl").unlink()
        self.assertEqual(fence.violations(self.run, "reflection"), [("removed", "evidence.jsonl")])

    def test_meta_review_may_write_meta_md_only(self):
        fence.snapshot(self.run, "meta-review")
        (self.run / "meta.md").write_text("# Meta\n")
        self.assertEqual(fence.violations(self.run, "meta-review"), [])
        (self.run / "hypotheses.json").write_text("{}")
        self.assertEqual(fence.violations(self.run, "meta-review"), [("wrote", "hypotheses.json")])

    def test_nested_file_is_seen(self):
        fence.snapshot(self.run, "reflection")
        (self.run / "sub").mkdir()
        (self.run / "sub" / "deep.txt").write_text("x")
        self.assertEqual(fence.violations(self.run, "reflection"), [("wrote", "sub/deep.txt")])

    def test_journal_and_fence_folder_are_never_compared(self):
        fence.snapshot(self.run, "reflection")
        journal.add(self.run, "subagent", None, "reflection round 1")
        fence.snapshot(self.run, "ranking")
        self.assertEqual(fence.violations(self.run, "reflection"), [])

    def test_judge_records_written_during_a_spawn_are_never_compared(self):
        fence.snapshot(self.run, "reflection")
        (self.run / "judge.jsonl").write_text('{"battery": "claim", "subject": "C-1"}\n')
        self.assertEqual(fence.violations(self.run, "reflection"), [])
        self.assertEqual(self.cli("check", "reflection").returncode, 0)

    def test_check_deletes_nothing(self):
        fence.snapshot(self.run, "reflection")
        (self.run / "extra.txt").write_text("hello")
        self.assertEqual(self.cli("check", "reflection").returncode, 2)
        self.assertEqual((self.run / "extra.txt").read_text(), "hello")

    def test_check_without_snapshot_exits_1(self):
        r = self.cli("check", "reflection")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no snapshot for reflection", r.stderr)

    def test_unknown_role_exits_1(self):
        r = self.cli("snapshot", "supervisor")
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid role", r.stderr)
        self.assertFalse((self.run / "fence").exists())


class CouncilFenceBlock(unittest.TestCase):
    def block(self):
        text = COUNCIL_MD.read_text(encoding="utf-8")
        start = text.index("## Every spawn, no exceptions")
        return " ".join(text[start:].split())

    def test_after_every_spawn_uses_the_two_commands(self):
        block = self.block()
        self.assertIn("scripts/fence.py snapshot --run <run> --role <role>", block)
        self.assertIn("scripts/fence.py check --run <run> --role <role>", block)
        self.assertNotIn("this listing is the fence", block)



class CodeCouncilFence(unittest.TestCase):
    """S-41: the Reviewer and the Thinker may create nothing; a task run needs no goal.json."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        body = {"request_text": "x", "test_command": "true", "allowed_paths": ["a"], "max_diff_lines": 5,
                "expected_small": True, "explain": False,
                "budget": {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0, "set_by": "user"}}
        self.run = task.new(self.tmp.name, body)
        (self.run / "diff.patch").write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, cmd, role):
        return subprocess.run([sys.executable, str(SCRIPT), cmd, "--run", str(self.run), "--role", role],
                              capture_output=True, text=True)

    def test_reviewer_creating_any_file_exits_2(self):
        self.assertFalse((self.run / "goal.json").exists())
        self.assertEqual(self.cli("snapshot", "code-reviewer").returncode, 0)
        (self.run / "review-1.json").write_text('{"findings": []}')
        r = self.cli("check", "code-reviewer")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "violation: code-reviewer wrote review-1.json\n")
        notes = [e for e in journal.read(self.run) if e["kind"] == "note"]
        self.assertEqual(len(notes), 1)

    def test_reviewer_and_thinker_that_only_reply_exit_0(self):
        for role in ("code-reviewer", "code-thinker"):
            self.assertEqual(self.cli("snapshot", role).returncode, 0)
            r = self.cli("check", role)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, f"ok: {role} changed nothing outside its reply\n")

    def test_run_with_neither_record_is_exit_1(self):
        with tempfile.TemporaryDirectory() as empty:
            r = subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--run", empty, "--role", "code-reviewer"],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no goal.json or task.json", r.stderr)


if __name__ == "__main__":
    unittest.main()
