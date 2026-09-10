"""S-30: every entry point says who runs the harness (an AGI-class model); no role gained a tool."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHRASE = "AGI-class model"


class WhoRunsThis(unittest.TestCase):
    def test_spec_has_one_who_runs_this_section(self):
        text = (ROOT / "docs" / "spec-v1.md").read_text()
        self.assertEqual(text.count("\n## Who runs this\n"), 1)

    def test_every_entry_point_names_the_model_class(self):
        files = sorted(ROOT.glob("agents/*.md")) + sorted(ROOT.glob("skills/*/SKILL.md"))
        self.assertEqual(len(files), 6, [f.name for f in files])
        for f in files:
            self.assertIn(PHRASE, f.read_text(), msg=str(f.relative_to(ROOT)))

    def test_no_role_gained_a_web_or_shell_tool(self):
        for f in sorted(ROOT.glob("agents/*.md")):
            tools = re.search(r"^tools: (.*)$", f.read_text(), re.M).group(1)
            for banned in ("Web", "Bash"):
                self.assertNotIn(banned, tools, msg=f"{f.name}: {tools}")


if __name__ == "__main__":
    unittest.main()
