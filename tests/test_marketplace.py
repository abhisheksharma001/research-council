"""S-45: the repo is its own one-plugin marketplace, so two commands install it from GitHub."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
README = ROOT / "README.md"


class Marketplace(unittest.TestCase):
    def setUp(self):
        self.market = json.loads(MARKETPLACE.read_text())
        self.plugin = json.loads(PLUGIN.read_text())

    def test_lists_exactly_the_plugin_in_this_repo(self):
        names = [entry["name"] for entry in self.market["plugins"]]
        self.assertEqual(names, [self.plugin["name"]])

    def test_source_is_the_repo_root_where_plugin_json_lives(self):
        source = self.market["plugins"][0]["source"]
        self.assertEqual(source, "./")
        self.assertTrue((ROOT / source / ".claude-plugin" / "plugin.json").is_file())

    def test_version_lives_only_in_plugin_json(self):
        self.assertNotIn("version", self.market)
        self.assertNotIn("version", self.market["plugins"][0])

    def test_readme_install_commands_match_the_marketplace_name(self):
        text = README.read_text()
        self.assertIn("claude plugin marketplace add abhisheksharma001/research-council", text)
        self.assertIn(f"claude plugin install {self.plugin['name']}@{self.market['name']}", text)


if __name__ == "__main__":
    unittest.main()
