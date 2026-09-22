"""S-40: done.py prints DONE only after the guards, the frozen tests and the review checks pass."""
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import done  # noqa: E402
import evidence  # noqa: E402
import journal  # noqa: E402
import task  # noqa: E402

SCRIPT = ROOT / "scripts" / "done.py"
HARNESS = ROOT / "scripts" / "harness.py"
CAPS = {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0, "set_by": "user"}
PY = f'"{sys.executable}"'
TEST_COMMAND = PY + " -c 'import sys, app.main as m; sys.exit(0 if m.VERDICT == \"big\" else 3)'"
FILES = {
    "app/main.py": 'VERDICT = "small"\n\ndef verdict():\n    return VERDICT\n',
    "tests/test_main.py": "import unittest\n\nclass MainTests(unittest.TestCase):\n    def test_verdict(self):\n        self.assertEqual(1, 1)\n",
    "README.md": "# demo\n",
    ".gitignore": "AGI_Research/\n__pycache__/\n",
}
SHA = re.compile(r"^DONE ([0-9a-f]{64})\n$")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class DoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        for name, text in FILES.items():
            self.write(name, text)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "start")
        self.start = git(self.root, "rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def append(self, name, text):
        self.write(name, (self.root / name).read_text() + text)

    def fix(self):
        self.write("app/main.py", FILES["app/main.py"].replace('"small"', '"big"'))

    def new_task(self, **overrides):
        body = {"request_text": "Make the verdict big.", "test_command": TEST_COMMAND,
                "allowed_paths": ["app/**", "tests/**"], "max_diff_lines": 80, "expected_small": True,
                "explain": False, "budget": dict(CAPS)}
        body.update(overrides)
        return task.new(self.root, body)

    def review(self, run, n, *findings):
        (run / f"review-{n}.json").write_text(json.dumps({"findings": list(findings)}))

    def finding(self, fid, severity="blocking"):
        return {"id": fid, "file": "app/main.py", "line": 1, "severity": severity, "kind": "logic",
                "text": "verdict is wrong", "fix": "set it"}

    def thinker(self, run, *tests):
        (run / "thinker.json").write_text(json.dumps({"tests": list(tests)}))

    def cli(self, run, *args, script=SCRIPT, before=()):
        return subprocess.run([sys.executable, str(script), *before, args[0], "--run", str(run), *args[1:]],
                              capture_output=True, text=True, cwd=self.root)

    def sha(self):
        return done.diff_sha(*done.diff_material(self.root, self.start))

    # the happy path
    def test_done_prints_the_sha_of_the_diff_after_the_tests_pass(self):
        run = self.new_task()
        self.fix()
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, f"DONE {self.sha()}\n")
        (record,) = evidence.read(run)
        self.assertEqual((record["source_type"], record["source_uri"], record["access_scope"]),
                         ("command", TEST_COMMAND, "private"))
        self.assertTrue(record["locator"].startswith("exit 0 after "), record["locator"])
        (entry,) = journal.read(run)
        self.assertEqual((entry["kind"], entry["cost_usd"]), ("exec", 0.0))
        self.assertIn("exit 0", entry["detail"])

    def test_failing_test_command_is_not_done(self):
        run = self.new_task()
        self.write("app/main.py", FILES["app/main.py"].replace('"small"', '"medium"'))
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\ntests: exit 3\n")
        (record,) = evidence.read(run)
        self.assertTrue(record["locator"].startswith("exit 3 after "), record["locator"])

    def test_excerpt_is_the_last_2000_characters_of_output(self):
        run = self.new_task(test_command=PY + " -c 'print(\"y\" * 2500)'")
        self.fix()
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 0, r.stderr)
        (record,) = evidence.read(run)
        self.assertEqual(len(record["excerpt"]), 2000)
        self.assertEqual(record["excerpt"], "y" * 1999 + "\n")

    def test_sha_covers_untracked_files(self):
        self.assertNotEqual(done.diff_sha(b"", {}), done.diff_sha(b"", {"tests/test_new.py": b"x = 1\n"}))
        run = self.new_task()
        self.fix()
        without = SHA.match(self.cli(run, "check").stdout).group(1)
        self.write("tests/test_new.py", "x = 1\n")
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, f"DONE {self.sha()}\n")
        self.assertNotEqual(SHA.match(r.stdout).group(1), without)

    # guards before the tests
    def test_guards_stop_before_the_tests_run(self):
        run = self.new_task()
        self.fix()
        self.append("README.md", "more\n")
        self.append("app/main.py", "import pyautoscrape\n")
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\noutside: README.md\nunresolved dependency: pyautoscrape\n")
        self.assertFalse((run / "evidence.jsonl").exists())

    def test_exceeded_budget_stops_first(self):
        run = self.new_task()
        self.fix()
        self.append("README.md", "more\n")
        for _ in range(61):
            journal.add(run, "read", 0.0, "x")
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\nbudget: exceeded max_actions (61/60)\n")
        self.assertFalse((run / "evidence.jsonl").exists())

    def test_empty_diff_is_not_done(self):
        r = self.cli(self.new_task(), "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\ndiff: empty (nothing changed since start_commit)\n")

    def test_minutes_left_is_the_test_timeout(self):
        caps = dict(CAPS, minutes=0.05)
        run = self.new_task(budget=caps, test_command=PY + " -c 'import time; time.sleep(30)'")
        self.fix()
        started = time.monotonic()
        r = self.cli(run, "check")
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stdout, r"^NOT DONE\ntests: timed out after \d+s \(minutes cap 0\.05\)\n$")
        (record,) = evidence.read(run)
        self.assertTrue(record["locator"].startswith("exit timeout after "), record["locator"])

    def test_no_minutes_left_skips_the_tests(self):
        run = self.new_task(budget=dict(CAPS, minutes=0.01))
        self.fix()
        time.sleep(0.8)
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\ntests: not run (minutes cap 0.01 reached)\n")
        self.assertFalse((run / "evidence.jsonl").exists())

    def test_tests_that_write_into_the_tree_are_not_done(self):
        run = self.new_task(test_command=PY + " -c 'open(\"app/junk.txt\", \"w\").write(\"x\")'")
        self.fix()
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\ntests: the run changed the diff (files written into the working tree)\n")

    # findings
    def test_blocking_finding_without_a_resolution_is_not_done(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1"), self.finding("R-2", "advisory"))
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\nunresolved finding: R-1\n")

    def test_resolve_fixed_records_the_sha_done_will_print(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1"))
        r = self.cli(run, "resolve", "--finding", "R-1", "--fixed")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = json.loads(r.stdout)
        self.assertEqual(line, {"finding": "R-1", "how": "fixed", "diff_sha": self.sha()})
        self.assertEqual((run / "resolutions.jsonl").read_text(), r.stdout)
        r = self.cli(run, "check")
        self.assertEqual(r.stdout, f"DONE {line['diff_sha']}\n")

    def test_resolve_waived_needs_the_users_words(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1"))
        r = self.cli(run, "resolve", "--finding", "R-1", "--waived", "")
        self.assertEqual(r.returncode, 1)
        self.assertIn("exact words", r.stderr)
        r = self.cli(run, "resolve", "--finding", "R-1", "--waived", "leave it, that branch is unreachable")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"finding": "R-1", "how": "waived",
                                                "user_words": "leave it, that branch is unreachable"})
        self.assertRegex(self.cli(run, "check").stdout, SHA)

    def test_resolve_refuses_unknown_ids_and_fixed_tests(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1"))
        self.thinker(run, {"id": "T-1", "name": "test_big_verdict", "file": "tests/test_main.py", "code": "...",
                           "would_fail_because": "..."})
        r = self.cli(run, "resolve", "--finding", "R-9", "--fixed")
        self.assertEqual((r.returncode, r.stderr), (1, "unknown finding: R-9 (not in any review-<n>.json)\n"))
        r = self.cli(run, "resolve", "--test", "T-1", "--fixed")
        self.assertEqual(r.returncode, 1)
        self.assertIn("use --waived", r.stderr)
        r = self.cli(run, "resolve", "--test", "T-9", "--waived", "skip it")
        self.assertEqual((r.returncode, r.stderr), (1, "unknown test: T-9 (not in thinker.json)\n"))
        r = self.cli(run, "resolve", "--finding", "R-1", "--test", "T-1", "--fixed")
        self.assertEqual(r.returncode, 1)
        self.assertFalse((run / "resolutions.jsonl").exists())

    def test_tier_2_diff_needs_a_review_file_and_the_thinker(self):
        run = self.new_task(expected_small=False)
        self.fix()
        self.append("app/main.py", "# note\n" * 11)
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "NOT DONE\nreview: tier 2 diff has no review-<n>.json\n"
                                   "thinker: no thinker.json for a tier 2 diff\n")
        self.review(run, 1)
        self.thinker(run)
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, SHA)

    def test_thinker_is_not_required_when_the_caps_drop_it(self):
        run = self.new_task(budget=dict(CAPS, max_subagents=1))
        self.fix()
        self.append("app/main.py", "# note\n" * 11)
        self.assertEqual(self.cli(run, "check").stdout, "NOT DONE\nreview: tier 2 diff has no review-<n>.json\n")
        self.review(run, 1)
        self.assertRegex(self.cli(run, "check").stdout, SHA)

    def test_thinker_test_name_must_be_in_the_diff_or_waived(self):
        run = self.new_task()
        self.fix()
        self.thinker(run, {"id": "T-1", "name": "test_big_verdict", "file": "tests/test_big.py", "code": "...",
                           "would_fail_because": "..."})
        r = self.cli(run, "check")
        self.assertEqual(r.stdout, "NOT DONE\nmissing test: T-1 test_big_verdict\n")
        self.write("tests/test_big.py", "def test_big_verdict():\n    assert True\n")
        self.assertRegex(self.cli(run, "check").stdout, SHA)
        (self.root / "tests/test_big.py").unlink()
        self.assertEqual(self.cli(run, "resolve", "--test", "T-1", "--waived", "not this task").returncode, 0)
        self.assertRegex(self.cli(run, "check").stdout, SHA)

    def test_a_mention_of_the_test_name_is_not_the_test(self):
        run = self.new_task()
        self.fix()
        self.thinker(run, {"id": "T-1", "name": "test_big_verdict", "file": "tests/test_big.py", "code": "...",
                           "would_fail_because": "..."})
        self.append("app/main.py", "# test_big_verdict() belongs here\n")
        self.write("app/drafts.py", 'DRAFTED = "test_big_verdict()"\n')
        self.assertEqual(self.cli(run, "check").stdout, "NOT DONE\nmissing test: T-1 test_big_verdict\n")
        self.write("tests/test_big.py", "# test_big_verdict() goes below\n")
        self.assertEqual(self.cli(run, "check").stdout, "NOT DONE\nmissing test: T-1 test_big_verdict\n")
        self.write("tests/test_big.py", "def helper_test_big_verdict():\n    return 1\n")
        self.assertEqual(self.cli(run, "check").stdout, "NOT DONE\nmissing test: T-1 test_big_verdict\n")
        self.write("tests/test_big.py", "def test_big_verdict():\n    assert True\n")
        self.assertRegex(self.cli(run, "check").stdout, SHA)

    # bad input
    def test_finding_id_in_two_review_files_is_exit_1(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1"))
        self.review(run, 2, self.finding("R-1"))
        r = self.cli(run, "check")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(r.stderr, "finding id R-1 appears in review-1.json and review-2.json\n")

    def test_malformed_run_files_are_exit_1(self):
        run = self.new_task()
        self.fix()
        (run / "review-1.json").write_text("{not json")
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("review-1.json does not parse", r.stderr)
        self.review(run, 1, {"id": "R-1", "text": "no severity"})
        self.assertIn("finding 0 needs an id and a severity", self.cli(run, "check").stderr)
        self.review(run, 1, self.finding("R-1"))
        (run / "resolutions.jsonl").write_text('{"finding": "R-1", "how": "fixed"}\n')
        r = self.cli(run, "check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("resolutions.jsonl line 1", r.stderr)
        (run / "resolutions.jsonl").unlink()
        self.thinker(run, {"id": "T-1"})
        self.assertIn("thinker.json: test 0 needs an id and a name", self.cli(run, "check").stderr)
        self.assertEqual(evidence.read(run), [])  # no check above it ever reached the test run

    def test_a_severity_outside_blocking_and_advisory_is_exit_1_before_the_test_run(self):
        run = self.new_task()
        self.fix()
        self.review(run, 1, self.finding("R-1", severity="critical"))
        r = self.cli(run, "check")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("finding 0 needs an id and a severity of blocking or advisory", r.stderr)
        self.assertEqual(evidence.read(run), [])
        self.assertEqual(journal.read(run), [])

    def test_tampered_task_is_exit_1(self):
        run = self.new_task()
        self.fix()
        t = json.loads((run / "task.json").read_text())
        t["test_command"] = "true"
        (run / "task.json").write_text(json.dumps(t))
        r = self.cli(run, "check")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("frozen_sha256 mismatch", r.stderr)

    def test_workspace_without_git_is_exit_1(self):
        with tempfile.TemporaryDirectory() as plain:
            body = {"request_text": "x", "test_command": "true", "allowed_paths": ["a"], "max_diff_lines": 5,
                    "expected_small": True, "explain": False, "budget": dict(CAPS)}
            r = self.cli(task.new(plain, body), "check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("start_commit is none", r.stderr)

    def test_check_never_touches_the_working_tree(self):
        run = self.new_task()
        self.fix()
        self.write("tests/test_new.py", "x = 1\n")
        before = (git(self.root, "status", "--porcelain"), git(self.root, "diff"))
        self.assertEqual(self.cli(run, "check").returncode, 0)
        self.assertEqual((git(self.root, "status", "--porcelain"), git(self.root, "diff")), before)

    def test_harness_runs_done_in_the_workspace(self):
        run = self.new_task()
        self.fix()
        r = self.cli(run, "check", script=HARNESS, before=("run", "--workspace", str(self.root), "done"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, f"DONE {self.sha()}\n")


if __name__ == "__main__":
    unittest.main()
