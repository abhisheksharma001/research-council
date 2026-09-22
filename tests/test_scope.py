"""S-38: scope.py keeps the diff inside the task's paths, line cap and verifier files."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scope  # noqa: E402
import task  # noqa: E402

SCRIPT = ROOT / "scripts" / "scope.py"
HARNESS = ROOT / "scripts" / "harness.py"
CAPS = {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0, "set_by": "user"}
TEST_FILE = """import unittest

# proves the verdict

class TriageTests(unittest.TestCase):
    def test_verdict(self):
        self.assertEqual(1, 1)
"""
FILES = {
    "scripts/triage.py": "VERDICT = 'big'\n\ndef verdict():\n    return VERDICT\n",
    "tests/test_triage.py": TEST_FILE,
    "README.md": "# demo\n",
    ".github/workflows/ci.yml": "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    "run_tests.sh": "# runs the suite\nset -e\npython3 -m unittest \\\n  --failfast\n",
    "tests/fixtures/schema.sql": "-- seed rows\nSELECT 1;\n",
    "tests/fixtures/cases.tbl": "# a case table\n-- not a comment here\n",
    "tests/helper_test.c": "/* checks\n * continued\n */\nint main(void) { return 0; }\n",
    ".gitignore": "AGI_Research/\n",
}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        for name, text in FILES.items():
            self.write(name, text)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "start")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def append(self, name, text):
        self.write(name, (self.root / name).read_text() + text)

    def drop_line(self, name, needle):
        lines = (self.root / name).read_text().splitlines(keepends=True)
        self.write(name, "".join(line for line in lines if needle not in line))

    def new_task(self, **overrides):
        body = {
            "request_text": "Make triage.py return the verdict as JSON.",
            "test_command": "python3 -m unittest tests.test_triage",
            "allowed_paths": ["scripts/triage.py", "tests/test_triage.py"],
            "max_diff_lines": 80,
            "expected_small": False,
            "explain": True,
            "budget": dict(CAPS),
        }
        body.update(overrides)
        return task.new(self.root, body)

    def cli(self, run, script=SCRIPT, *before):
        return subprocess.run([sys.executable, str(script), *before, "check", "--run", str(run)],
                              capture_output=True, text=True, cwd=self.root)

    # tiers and lines
    def test_clean_tree_is_tier_1_with_zero_lines(self):
        r = self.cli(self.new_task())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 0\n")

    def test_lines_are_added_plus_removed_since_start_commit(self):
        run = self.new_task()
        self.write("scripts/triage.py", 'import json\nVERDICT = "big"\n\ndef verdict():\n    return VERDICT\n')
        git(self.root, "commit", "-q", "-am", "mid-task commit")
        self.append("scripts/triage.py", "\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 4\n")

    def test_eleven_lines_is_tier_2_and_over_a_hundred_is_tier_3(self):
        run = self.new_task(max_diff_lines=500)
        self.append("scripts/triage.py", "x = 1\n" * 11)
        self.assertEqual(self.cli(run).stdout, "tier: 2\nlines: 11\n")
        self.append("scripts/triage.py", "x = 1\n" * 90)
        self.assertEqual(self.cli(run).stdout, "tier: 3\nlines: 101\n")

    def test_tier_boundaries(self):
        self.assertEqual([scope.tier(n) for n in (0, 10, 11, 100, 101)], [1, 1, 2, 2, 3])

    # outside
    def test_changed_file_outside_allowed_paths_exits_2(self):
        run = self.new_task()
        self.append("README.md", "more\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "outside: README.md\n")

    def test_new_untracked_file_is_named_and_counted(self):
        run = self.new_task()
        self.write("scripts/new.py", "a = 1\nb = 2\nc = 3\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "outside: scripts/new.py\n")
        r = self.cli(self.new_task(allowed_paths=["scripts/*.py"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 3\n")

    def test_star_stays_in_one_folder_and_double_star_crosses(self):
        self.write("scripts/lib/util.py", "u = 1\n")
        r = self.cli(self.new_task(allowed_paths=["scripts/*.py"]))
        self.assertEqual(r.stdout, "outside: scripts/lib/util.py\n")
        r = self.cli(self.new_task(allowed_paths=["scripts/**"]))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_glob_matches_the_whole_path(self):
        self.assertTrue(scope.allowed("docs/a/b.md", ["**/*.md"]))
        self.assertTrue(scope.allowed("b.md", ["**/*.md"]))
        self.assertTrue(scope.allowed("docs/a.md", ["docs/?.md"]))
        self.assertTrue(scope.allowed("docs/b.md", ["docs/[!a].md"]))
        self.assertFalse(scope.allowed("docs/a.md", ["docs/[!a].md"]))
        self.assertFalse(scope.allowed("x/tests/a.py", ["tests/*.py"]))
        self.assertFalse(scope.allowed("tests/a.py.bak", ["tests/*.py"]))

    def test_run_folder_is_never_in_scope(self):
        (self.root / ".gitignore").unlink()
        git(self.root, "commit", "-q", "-am", "no ignore")
        run = self.new_task()
        self.assertTrue((run / "task.json").is_file())
        self.assertIn("AGI_Research/", git(self.root, "status", "--porcelain"))
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 0\n")

    # over
    def test_over_the_line_cap_exits_2(self):
        run = self.new_task(max_diff_lines=20)
        self.append("scripts/triage.py", "x = 1\n" * 21)
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "over: 21/20 lines\n")

    # verifier-edit
    def test_removed_test_function_is_a_verifier_edit(self):
        run = self.new_task()
        self.drop_line("tests/test_triage.py", "def test_verdict")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: tests/test_triage.py: removed line: def test_verdict(self):\n")

    def test_removed_comment_and_blank_lines_are_not_verifier_edits(self):
        run = self.new_task()
        self.drop_line("tests/test_triage.py", "# proves")
        self.write("tests/test_triage.py", (self.root / "tests/test_triage.py").read_text().replace("\n\n", "\n"))
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_added_skip_marker_is_a_verifier_edit(self):
        run = self.new_task()
        self.write("tests/test_triage.py", TEST_FILE.replace("    def test_verdict", '    @unittest.skip("later")\n    def test_verdict'))
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: tests/test_triage.py: added 'skip' marker: @unittest.skip(\"later\")\n")

    def test_new_test_file_with_expected_failure_is_a_verifier_edit(self):
        run = self.new_task(allowed_paths=["tests/**"])
        self.write("tests/test_new.py", "import unittest\n\n@unittest.expectedFailure\ndef test_x(): pass\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: tests/test_new.py: added 'expectedfailure' marker: @unittest.expectedFailure\n")

    def test_a_comment_prefix_belongs_to_the_files_language(self):
        run = self.new_task(allowed_paths=["tests/**", "run_tests.sh"], test_command="bash run_tests.sh")
        self.drop_line("run_tests.sh", "--failfast")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: run_tests.sh: removed line: --failfast\n")
        git(self.root, "checkout", "--", "run_tests.sh")
        self.drop_line("run_tests.sh", "# runs the suite")
        self.assertEqual(self.cli(run).returncode, 0)
        git(self.root, "checkout", "--", "run_tests.sh")
        self.drop_line("tests/fixtures/schema.sql", "-- seed rows")
        self.assertEqual(self.cli(run).returncode, 0)
        self.drop_line("tests/fixtures/schema.sql", "SELECT 1;")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: tests/fixtures/schema.sql: removed line: SELECT 1;\n")
        git(self.root, "checkout", "--", "tests/fixtures/schema.sql")
        self.drop_line("tests/helper_test.c", "* continued")
        self.assertEqual(self.cli(run).returncode, 0)
        git(self.root, "checkout", "--", "tests/helper_test.c")
        self.drop_line("tests/fixtures/cases.tbl", "# a case table")
        self.assertEqual(self.cli(run).returncode, 0)
        self.drop_line("tests/fixtures/cases.tbl", "-- not a comment here")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout,
                         "verifier-edit: tests/fixtures/cases.tbl: removed line: -- not a comment here\n")

    def test_ci_config_and_test_command_files_are_verifiers(self):
        run = self.new_task(allowed_paths=[".github/**", "run_tests.sh"], test_command="bash run_tests.sh")
        self.drop_line(".github/workflows/ci.yml", "runs-on")
        self.drop_line("run_tests.sh", "set -e")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "verifier-edit: .github/workflows/ci.yml: removed line: runs-on: ubuntu-latest\n"
                                   "verifier-edit: run_tests.sh: removed line: set -e\n")

    def test_deleted_test_file_is_a_verifier_edit(self):
        run = self.new_task()
        (self.root / "tests/test_triage.py").unlink()
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout.count("verifier-edit: tests/test_triage.py: removed line: "), 4)

    def test_allow_verifier_edits_silences_the_rule(self):
        run = self.new_task(allow_verifier_edits=True)
        self.drop_line("tests/test_triage.py", "def test_verdict")
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 1\n")

    # bad input
    def test_tampered_task_is_exit_1(self):
        run = self.new_task()
        t = json.loads((run / "task.json").read_text())
        t["allowed_paths"].append("README.md")
        (run / "task.json").write_text(json.dumps(t))
        self.append("README.md", "more\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 1)
        self.assertIn("frozen_sha256 mismatch", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_workspace_without_git_is_exit_1(self):
        with tempfile.TemporaryDirectory() as plain:
            body = {"request_text": "x", "test_command": "true", "allowed_paths": ["a"], "max_diff_lines": 5,
                    "expected_small": True, "explain": False, "budget": dict(CAPS)}
            run = task.new(plain, body)
            r = self.cli(run)
        self.assertEqual(r.returncode, 1)
        self.assertIn("start_commit is none", r.stderr)

    def test_check_never_touches_the_working_tree(self):
        run = self.new_task()
        self.append("scripts/triage.py", "x = 1\n")
        self.write("scripts/new.py", "n = 1\n")
        self.drop_line("tests/test_triage.py", "def test_verdict")
        before = (git(self.root, "status", "--porcelain"), git(self.root, "diff"))
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual((git(self.root, "status", "--porcelain"), git(self.root, "diff")), before)

    def test_harness_runs_scope_in_the_workspace(self):
        run = self.new_task()
        r = self.cli(run, HARNESS, "run", "--workspace", str(self.root), "scope")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "tier: 1\nlines: 0\n")


if __name__ == "__main__":
    unittest.main()
