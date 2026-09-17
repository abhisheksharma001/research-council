"""S-37: task.py writes a frozen task record whose caps are the user's, never a default."""
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
import journal  # noqa: E402
import task  # noqa: E402

SCRIPT = ROOT / "scripts" / "task.py"
CAPS = {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0, "set_by": "user"}


def body(**overrides):
    b = {
        "request_text": "Add a --json flag to scripts/triage.py that prints the verdict as JSON.",
        "test_command": "python3 -m unittest tests.test_triage",
        "allowed_paths": ["scripts/triage.py", "tests/test_triage.py"],
        "max_diff_lines": 80,
        "expected_small": False,
        "explain": True,
        "budget": dict(CAPS),
    }
    b.update(overrides)
    return b


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, input=stdin)

    def write_config(self, budget):
        cfg = self.root / ".code-council"
        cfg.mkdir()
        (cfg / "config.json").write_text(json.dumps({"budget": budget}))

    # new
    def test_body_is_valid(self):
        self.assertEqual(task.validate(body()), [])

    def test_new_writes_frozen_task_under_code(self):
        run = task.new(self.root, body())
        self.assertEqual(run.parent, self.root / "AGI_Research" / "code")
        t = json.loads((run / "task.json").read_text())
        uuid.UUID(t["task_id"], version=4)
        self.assertEqual(t["repo_root"], str(self.root))
        self.assertEqual(t["start_commit"], "none")
        self.assertIs(t["allow_verifier_edits"], False)
        self.assertEqual(t["budget"], CAPS)
        self.assertEqual(len(t["frozen_sha256"]), 64)
        self.assertEqual(t["frozen_sha256"], goal.freeze(t))
        self.assertEqual(task.load(run)["task_id"], t["task_id"])
        self.assertTrue(set(task.SCRIPT_FIELDS) <= set(t))

    def test_start_commit_is_git_head(self):
        git(self.root, "init", "-q")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        (self.root / ".gitignore").write_text("AGI_Research/\n")
        t = task.load(task.new(self.root, body()))
        self.assertEqual(t["start_commit"], git(self.root, "rev-parse", "HEAD"))

    def test_root_must_exist(self):
        with self.assertRaisesRegex(ValueError, "root must be an existing directory"):
            task.new(self.root / "missing", body())

    # acceptance: missing test_command or allowed_paths exits 1 naming the field
    def test_missing_test_command_names_field(self):
        b = body()
        del b["test_command"]
        r = self.cli("new", "--root", str(self.root), "--from", "-", stdin=json.dumps(b))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing field: test_command", r.stderr)
        self.assertFalse((self.root / "AGI_Research").exists())

    def test_missing_allowed_paths_names_field(self):
        b = body()
        del b["allowed_paths"]
        r = self.cli("new", "--root", str(self.root), "--from", "-", stdin=json.dumps(b))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing field: allowed_paths", r.stderr)
        self.assertFalse((self.root / "AGI_Research").exists())

    def test_empty_allowed_paths_rejected(self):
        self.assertIn("invalid field: allowed_paths (must be a list of at least one non-empty string)",
                      task.validate(body(allowed_paths=[])))

    def test_empty_test_command_rejected(self):
        self.assertIn("invalid field: test_command (must be a non-empty string)",
                      task.validate(body(test_command=" ")))

    def test_max_diff_lines_is_a_whole_number_above_zero(self):
        for bad in (0, -1, 2.5, True, "80"):
            with self.subTest(bad=bad):
                self.assertIn("invalid field: max_diff_lines (must be a whole number above 0)",
                              task.validate(body(max_diff_lines=bad)))

    def test_bool_fields_must_be_bool(self):
        for f in ("expected_small", "explain", "allow_verifier_edits"):
            with self.subTest(field=f):
                self.assertIn(f"invalid field: {f} (must be true or false)", task.validate(body(**{f: "yes"})))

    def test_unknown_field_rejected(self):
        self.assertIn("unknown field: reviewer", task.validate(body(reviewer="me")))

    # caps: the user's, never a default
    def test_missing_cap_is_named_not_defaulted(self):
        b = body()
        del b["budget"]["max_subagents"]
        r = self.cli("new", "--root", str(self.root), "--from", "-", stdin=json.dumps(b))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing field: budget.max_subagents", r.stderr)
        self.assertFalse((self.root / "AGI_Research").exists())

    def test_no_budget_and_no_config_names_the_config_file(self):
        b = body()
        del b["budget"]
        errs = task.validate(b, task.read_config(self.root))
        self.assertEqual(len(errs), 1)
        self.assertIn("missing field: budget", errs[0])
        self.assertIn(".code-council/config.json", errs[0])

    def test_zero_cap_rejected_except_usd(self):
        for k in ("minutes", "max_actions", "max_subagents"):
            with self.subTest(cap=k):
                b = body()
                b["budget"][k] = 0
                self.assertIn(f"invalid field: budget.{k} (must be a number above 0)", task.validate(b))
        b = body()
        b["budget"]["usd_estimate_cap"] = 0
        self.assertEqual(task.validate(b), [])

    def test_set_by_must_be_user(self):
        b = body()
        b["budget"]["set_by"] = "script"
        self.assertIn('invalid field: budget.set_by (must be "user")', task.validate(b))

    def test_config_supplies_caps(self):
        caps = dict(CAPS, minutes=45)
        self.write_config(caps)
        b = body()
        del b["budget"]
        t = task.load(task.new(self.root, b))
        self.assertEqual(t["budget"], caps)

    def test_config_missing_cap_is_named(self):
        caps = dict(CAPS)
        del caps["minutes"]
        self.write_config(caps)
        b = body()
        del b["budget"]
        r = self.cli("new", "--root", str(self.root), "--from", "-", stdin=json.dumps(b))
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing field: .code-council/config.json budget.minutes", r.stderr)

    def test_config_and_body_budget_together_rejected(self):
        self.write_config(dict(CAPS))
        with self.assertRaisesRegex(ValueError, "caps come from the config"):
            task.new(self.root, body())

    def test_config_without_budget_block_rejected(self):
        (self.root / ".code-council").mkdir()
        (self.root / ".code-council" / "config.json").write_text(json.dumps({"minutes": 20}))
        with self.assertRaisesRegex(ValueError, "must be an object with a budget block"):
            task.new(self.root, body())

    # frozen
    def test_check_detects_hand_edit(self):
        run = task.new(self.root, body())
        path = run / "task.json"
        t = json.loads(path.read_text())
        t["test_command"] = "true"
        path.write_text(json.dumps(t))
        r = self.cli("check", "--run", str(run))
        self.assertEqual(r.returncode, 1)
        self.assertIn("frozen_sha256 mismatch", r.stderr)

    def test_check_ok_on_untouched_task(self):
        run = task.new(self.root, body())
        r = self.cli("check", "--run", str(run))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("ok: task "))

    def test_there_is_no_revise(self):
        r = self.cli("revise", "--run", str(self.root), "--from", "-", "--reason", "x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid choice: 'revise'", r.stderr)

    # workspace
    def test_warns_when_workspace_git_would_track_the_run_folder(self):
        git(self.root, "init", "-q")
        r = self.cli("new", "--root", str(self.root), "--from", "-", stdin=json.dumps(body()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: AGI_Research/ is not ignored", r.stderr)
        self.assertTrue(Path(r.stdout.strip()).is_file())

    def test_journal_accepts_a_task_run(self):
        run = task.new(self.root, body())
        journal.add(run, "exec", None, "python3 -m unittest tests.test_triage")
        self.assertEqual(journal.read(run)[0]["kind"], "exec")


if __name__ == "__main__":
    unittest.main()
