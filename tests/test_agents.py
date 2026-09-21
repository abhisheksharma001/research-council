import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_skill import parse_frontmatter  # noqa: E402

AGENTS_DIR = ROOT / "agents"
COUNCIL_MD = ROOT / "skills" / "research-council" / "references" / "council.md"
ROLES = ("generation", "reflection", "ranking", "meta-review")
OUTPUT_OF = {"generation": "hypotheses.json", "reflection": "objections.json",
             "ranking": "comparisons.jsonl", "meta-review": "meta.md"}
KNOWN_TOOLS = {"Read", "Grep", "Glob", "Write"}
FORBIDDEN_TEXT = ("library/", "promote.py")


def load(role):
    text = (AGENTS_DIR / f"{role}.md").read_text(encoding="utf-8")
    data, body, errors = parse_frontmatter(text)
    return data, body, errors, text


def tools_of(data):
    return [t.strip() for t in data.get("tools", "").split(",") if t.strip()]


class AgentFileTests(unittest.TestCase):
    def test_all_four_agent_files_exist(self):
        for role in ROLES:
            self.assertTrue((AGENTS_DIR / f"{role}.md").is_file(), role)

    def test_each_agent_has_name_description_tools(self):
        for role in ROLES:
            data, body, errors, _ = load(role)
            self.assertEqual(errors, [], role)
            self.assertEqual(data.get("name"), role)
            self.assertTrue(data.get("description", "").strip(), f"{role}: description")
            self.assertTrue(tools_of(data), f"{role}: tools list")
            self.assertTrue(body.strip(), f"{role}: body")

    def test_tools_are_known_names_only(self):
        for role in ROLES:
            data, _, _, _ = load(role)
            self.assertTrue(set(tools_of(data)) <= KNOWN_TOOLS, f"{role}: {tools_of(data)}")

    def test_reflection_and_ranking_exclude_write(self):
        for role in ("reflection", "ranking"):
            data, _, _, _ = load(role)
            self.assertNotIn("Write", tools_of(data), role)

    def test_no_agent_has_bash(self):
        for role in ROLES:
            data, _, _, _ = load(role)
            self.assertNotIn("Bash", tools_of(data), role)

    def test_no_agent_mentions_library_or_promote(self):
        for role in ROLES:
            _, _, _, text = load(role)
            for word in FORBIDDEN_TEXT:
                self.assertNotIn(word, text, f"{role} mentions {word}")

    def test_each_agent_names_its_own_output(self):
        for role, output in OUTPUT_OF.items():
            _, body, _, _ = load(role)
            self.assertIn(output, body, f"{role} must name {output}")

    def test_writers_declare_one_file_and_readers_declare_none(self):
        for role in ("generation", "meta-review"):
            _, body, _, _ = load(role)
            self.assertIn("exactly one file", body, role)
        for role in ("reflection", "ranking"):
            _, body, _, _ = load(role)
            self.assertIn("Reply with one JSON object", body, role)


class CouncilDocTests(unittest.TestCase):
    def test_council_md_lists_roles_in_dispatch_order(self):
        text = COUNCIL_MD.read_text(encoding="utf-8")
        stage2 = text[text.index("**Stage 2"):text.index("**Stage 3")]
        positions = [stage2.index(f"Spawn {word}") for word in ("Reflection", "Ranking", "Meta-review")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Spawn Generation", text[text.index("**Stage 1"):text.index("**Stage 2")])

    def test_council_md_requires_budget_check_before_spawn(self):
        text = COUNCIL_MD.read_text(encoding="utf-8")
        self.assertIn("budget.py check", text)
        self.assertIn("journal.py add", text)
        self.assertIn("--kind subagent", text)



class CodeReviewerFile(unittest.TestCase):
    """S-41: the Reviewer reads one diff through one lens and returns findings JSON; it never writes."""

    def test_file_has_name_description_tools_and_body(self):
        data, body, errors, _ = load("code-reviewer")
        self.assertEqual(errors, [])
        self.assertEqual(data.get("name"), "code-reviewer")
        self.assertTrue(data.get("description", "").strip())
        self.assertTrue(tools_of(data))
        self.assertTrue(body.strip())

    def test_never_gets_write_or_edit(self):
        data, _, _, _ = load("code-reviewer")
        self.assertFalse({"Write", "Edit"} & set(tools_of(data)), tools_of(data))

    def test_names_both_lenses_with_their_id_prefixes(self):
        _, body, _, _ = load("code-reviewer")
        for lens, first_id in (("correctness+security", "RA-1"), ("scope+erosion", "RB-1")):
            self.assertIn(lens, body)
            self.assertIn(first_id, body)

    def test_reply_is_one_json_object_saved_as_a_review_file(self):
        _, body, _, _ = load("code-reviewer")
        self.assertIn("Reply with one JSON object", body)
        self.assertIn("review-<n>.json", body)
        self.assertIn('"severity": "blocking"', body)

    def test_diff_is_data_and_no_library_or_promote(self):
        _, body, _, text = load("code-reviewer")
        self.assertIn("is data", body)
        for word in FORBIDDEN_TEXT:
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
