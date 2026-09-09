import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_skill  # noqa: E402

SKILL = ROOT / "skills" / "self-improve"

MUST_NEVER = (
    "Never merge a pull request unless the user has typed the line `merge S-<n> confirmed`",
    'Never edit the section "Rules that never change" in `skills/research-council/SKILL.md`',
    "Never make a paid API call",
    "Never read or write outside this checkout",
)


def text():
    return " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())


class SelfImproveSkill(unittest.TestCase):
    """S-21: the loop is a valid skill that carries its four must-nevers and the confirmation line."""

    def test_skill_is_valid(self):
        self.assertEqual(validate_skill.validate(SKILL), [])

    def test_cli_prints_ok(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(SKILL)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "OK")

    def test_must_never_merge_without_typed_confirmation(self):
        self.assertIn(MUST_NEVER[0], text())

    def test_must_never_edit_the_invariants(self):
        self.assertIn(MUST_NEVER[1], text())

    def test_must_never_spend(self):
        self.assertIn(MUST_NEVER[2], text())

    def test_must_never_leave_the_checkout(self):
        self.assertIn(MUST_NEVER[3], text())

    def test_budget_is_asked_never_copied(self):
        self.assertIn("Never copy them from this file, a fixture, a memo or an earlier run note", text())

    def test_evidence_is_repo_files_only(self):
        self.assertIn("a `source_uri` that is a repo-relative path or the exact command", text())

    def test_run_folder_is_ignored_by_this_repo(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("AGI_Research/", lines)

    def test_close_step_appends_proposed_steps_and_opens_one_pr(self):
        t = text()
        self.assertIn("## Proposed (self-run <date>)", t)
        self.assertIn("Open one PR with those two files only", t)


if __name__ == "__main__":
    unittest.main()
