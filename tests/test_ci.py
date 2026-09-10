"""S-31: CI runs the same commands the register's Verify lines run, on every push to main and every PR."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


class CI(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_workflow_runs_the_test_suite(self):
        self.assertIn("python3 -m unittest discover -s tests -v", self.text)

    def test_workflow_validates_every_skill(self):
        for skill in sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()):
            self.assertIn(f"python3 scripts/validate_skill.py skills/{skill}", self.text, msg=skill)

    def test_workflow_triggers_on_pull_request_and_main_push(self):
        self.assertIn("pull_request:", self.text)
        self.assertIn("branches: [main]", self.text)

    def test_workflow_installs_nothing(self):
        for word in ("pip install", "requirements", "npm"):
            self.assertNotIn(word, self.text, msg=word)
