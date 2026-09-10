import copy
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import goal  # noqa: E402

SCRIPT = ROOT / "scripts" / "goal.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"


def body():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fixture_is_valid(self):
        self.assertEqual(goal.validate(body()), [])

    def test_new_writes_frozen_goal(self):
        run = goal.new(self.root, body())
        self.assertEqual(run.parent, self.root / "AGI_Research" / "runs")
        g = json.loads((run / "goal.json").read_text())
        uuid.UUID(g["goal_id"], version=4)
        self.assertEqual(g["revision"], 1)
        self.assertEqual(len(g["frozen_sha256"]), 64)
        self.assertEqual(g["frozen_sha256"], goal.freeze(g))
        self.assertEqual(goal.load(run)["goal_id"], g["goal_id"])

    def test_missing_competing_hypotheses_names_field(self):
        b = body()
        del b["competing_hypotheses"]
        self.assertIn("missing field: competing_hypotheses", goal.validate(b))

    def test_one_hypothesis_rejected(self):
        b = body()
        b["competing_hypotheses"] = b["competing_hypotheses"][:1]
        errs = goal.validate(b)
        self.assertEqual(len(errs), 1)
        self.assertIn("competing_hypotheses", errs[0])

    def test_hypothesis_missing_key_named(self):
        b = body()
        del b["competing_hypotheses"][1]["predicted_result"]
        self.assertIn("missing field: competing_hypotheses[1].predicted_result",
                      goal.validate(b))

    def test_empty_success_criteria_rejected(self):
        b = body()
        b["success_criteria"] = []
        errs = goal.validate(b)
        self.assertEqual(len(errs), 1)
        self.assertIn("success_criteria", errs[0])

    def test_missing_budget_rejected(self):
        b = body()
        del b["budget"]
        self.assertIn("missing field: budget", goal.validate(b))

    def test_budget_number_missing_named(self):
        b = body()
        del b["budget"]["usd_estimate_cap"]
        self.assertIn("missing field: budget.usd_estimate_cap", goal.validate(b))

    def test_zero_usd_cap_is_accepted_other_zero_caps_are_not(self):
        b = body()
        b["budget"]["usd_estimate_cap"] = 0
        self.assertEqual(goal.validate(b), [])
        b["budget"]["max_subagents"] = 0
        self.assertIn("invalid field: budget.max_subagents (must be a number above 0)", goal.validate(b))

    def test_negative_usd_cap_rejected(self):
        b = body()
        b["budget"]["usd_estimate_cap"] = -1
        self.assertIn("invalid field: budget.usd_estimate_cap (must be a number 0 or above)", goal.validate(b))

    def test_budget_caps_must_be_finite_and_representable(self):
        for key in goal.BUDGET_NUMBERS:
            for value in (float("nan"), float("inf"), float("-inf"), 10 ** 1000):
                b = body()
                b["budget"][key] = value
                with self.subTest(key=key, value=str(value)[:20]):
                    self.assertTrue(any(f"budget.{key}" in error for error in goal.validate(b)))

    def test_revision_cannot_replace_cap_with_nan(self):
        run = goal.new(self.root, body())
        before = (run / "goal.json").read_bytes()
        b = body()
        b["budget"]["max_actions"] = float("nan")
        with self.assertRaises(ValueError):
            goal.revise(run, b, "invalid fixture revision")
        self.assertEqual(before, (run / "goal.json").read_bytes())
        self.assertFalse((run / "goal.history.jsonl").exists())

    def test_unknown_field_rejected(self):
        b = body()
        b["priority"] = "high"
        self.assertIn("unknown field: priority", goal.validate(b))

    def test_hand_edit_detected(self):
        run = goal.new(self.root, body())
        path = run / "goal.json"
        g = json.loads(path.read_text())
        g["budget"]["max_actions"] = 9999
        path.write_text(json.dumps(g))
        with self.assertRaises(ValueError):
            goal.load(run)

    def test_revise_bumps_revision_and_keeps_history(self):
        run = goal.new(self.root, body())
        first = goal.load(run)
        b = body()
        b["unknowns"].append("Whether the earlier window had the same config change.")
        second = goal.revise(run, b, "user added an unknown")
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["goal_id"], first["goal_id"])
        self.assertEqual(second["created_at"], first["created_at"])
        self.assertNotEqual(second["frozen_sha256"], first["frozen_sha256"])
        self.assertEqual(goal.load(run)["revision"], 2)
        lines = (run / "goal.history.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        hist = json.loads(lines[0])
        self.assertEqual(hist["reason"], "user added an unknown")
        self.assertEqual(hist["goal"]["frozen_sha256"], first["frozen_sha256"])

    def test_revise_refuses_budget_raise(self):
        run = goal.new(self.root, body())
        b = body()
        b["budget"]["max_actions"] += 1
        with self.assertRaises(ValueError) as cm:
            goal.revise(run, b, "want more")
        self.assertIn("max_actions", str(cm.exception))
        self.assertFalse((run / "goal.history.jsonl").exists())

    def test_revise_refuses_tampered_goal(self):
        run = goal.new(self.root, body())
        path = run / "goal.json"
        path.write_text(path.read_text().replace('"revision": 1', '"revision": 7'))
        with self.assertRaises(ValueError):
            goal.revise(run, body(), "any")

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, str(SCRIPT), "new", "--root", str(self.root),
                             "--from", str(FIXTURE)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        run = Path(ok.stdout.strip()).parent
        chk = subprocess.run([sys.executable, str(SCRIPT), "check", "--run", str(run)],
                             capture_output=True, text=True)
        self.assertEqual(chk.returncode, 0, chk.stderr)

        b = body()
        b["competing_hypotheses"] = b["competing_hypotheses"][:1]
        bad = subprocess.run([sys.executable, str(SCRIPT), "new", "--root", str(self.root),
                              "--from", "-"], input=json.dumps(b),
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("competing_hypotheses", bad.stderr)


SILENT_USER_SENTENCE = (
    "If the user has not given the numbers or the criterion in this session, stop and ask "
    "again. Never copy them from a fixture, a memo or an earlier run, and never write "
    "`set_by: user` for a value the user did not say."
)


class SilentUserSentence(unittest.TestCase):
    """S-13: a silent user never gets a copied budget or criterion (bug 1, 2026-09-09)."""

    def test_goal_md_and_skill_md_carry_silent_user_sentence(self):
        files = [
            ROOT / "skills" / "research-council" / "references" / "goal.md",
            ROOT / "skills" / "research-council" / "SKILL.md",
        ]
        for path in files:
            text = " ".join(path.read_text(encoding="utf-8").split())
            self.assertTrue(SILENT_USER_SENTENCE in text,
                            f"{path.relative_to(ROOT)} lacks the silent-user sentence")


class IgnoreWarning(unittest.TestCase):
    """S-16: a git workspace that does not ignore AGI_Research gets a warning, exit 0 (bug 4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def new(self):
        return subprocess.run([sys.executable, str(SCRIPT), "new", "--root", str(self.root),
                               "--from", str(FIXTURE)], capture_output=True, text=True)

    def test_git_checkout_without_ignore_rule_warns_and_exits_0(self):
        (self.root / ".git").mkdir()
        (self.root / ".gitignore").write_text("*.pyc\n")
        r = self.new()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: AGI_Research/ is not ignored by", r.stderr)
        self.assertIn(str(self.root / ".gitignore"), r.stderr)
        self.assertEqual((self.root / ".gitignore").read_text(), "*.pyc\n")

    def test_git_checkout_without_any_gitignore_warns(self):
        (self.root / ".git").mkdir()
        r = self.new()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: AGI_Research/", r.stderr)
        self.assertFalse((self.root / ".gitignore").exists())

    def test_git_checkout_with_ignore_rule_prints_nothing_extra(self):
        (self.root / ".git").mkdir()
        (self.root / ".gitignore").write_text("*.pyc\nAGI_Research/\n")
        r = self.new()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")

    def test_plain_folder_prints_nothing_extra(self):
        r = self.new()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")

    def test_skill_md_says_add_ignore_line_only_with_the_users_go(self):
        text = " ".join((ROOT / "skills" / "research-council" / "SKILL.md").read_text().split())
        self.assertIn("add the line `AGI_Research/` to the workspace `.gitignore` only with their go", text)


if __name__ == "__main__":
    unittest.main()
