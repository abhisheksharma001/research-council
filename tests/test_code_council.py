"""S-36: code-writer-council is a valid skill that carries its seven rules, its trigger and its stage list."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_skill  # noqa: E402

SKILL = ROOT / "skills" / "code-writer-council"

RULES = (
    '"Done" is printed by scripts/done.py after it runs the tests. The model copies the line; it never composes one.',
    "The test command and the allowed paths are frozen in task.json at task start. Changing them is a new task, not an edit.",
    "No package is installed and no new import is left in the diff without an evidence record from the registry page naming that package.",
    "Roles that read code (Reviewer, Thinker) never get Write or Bash. They return one JSON object; the Supervisor saves it.",
    "Caps are the user's, set once per repository in .code-council/config.json. No script defines a default cap. (CLAUDE.md invariant 4.)",
    "The council never pushes, never merges, never touches CI configuration without the user's words in the task record.",
    "A blocking finding is closed by a fix (new diff sha) or by the user's exact words. Never by the model's judgement alone.",
)


def text():
    return " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())


def description():
    data, _, errors = validate_skill.parse_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
    assert not errors, errors
    return validate_skill.unquote(data["description"])


class CodeCouncilSkill(unittest.TestCase):
    def test_skill_is_valid(self):
        self.assertEqual(validate_skill.validate(SKILL), [])

    def test_cli_prints_ok(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(SKILL)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "OK")

    def test_description_triggers_on_writing_code(self):
        self.assertIn("about to write or change code", description())

    def test_description_names_the_ten_line_exit(self):
        self.assertIn("ten lines or fewer", description())

    def test_description_sends_research_to_research_council(self):
        self.assertIn("send those to research-council", description())

    def test_runtime_resolves_council_root_and_runs_context(self):
        t = text()
        self.assertIn("set COUNCIL_ROOT to that runtime folder", t)
        self.assertIn('harness.py" context --workspace "$WORKSPACE"', t)

    def test_procedure_lists_every_stage_with_its_step(self):
        t = text()
        for stage, step in (("**Task.**", "S-37"), ("**Write, with the Thinker in parallel.**", "S-42"),
                            ("**Guards.**", "S-38, S-39"), ("**Tier.**", "S-41"), ("**Review.**", "S-41"),
                            ("**Fix.**", "S-43"), ("**Done.**", "S-40"), ("**Reply.**", "S-43")):
            start = t.find(stage)
            self.assertNotEqual(start, -1, stage)
            self.assertIn(step, t[start:start + 200], stage)

    def test_rule_1_done_is_printed_by_a_script(self):
        self.assertIn(RULES[0], text())

    def test_rule_2_test_command_and_paths_are_frozen(self):
        self.assertIn(RULES[1], text())

    def test_rule_3_no_package_without_registry_evidence(self):
        self.assertIn(RULES[2], text())

    def test_rule_4_readers_never_get_write_or_bash(self):
        self.assertIn(RULES[3], text())

    def test_rule_5_caps_are_the_users_no_default(self):
        self.assertIn(RULES[4], text())

    def test_rule_6_never_push_merge_or_touch_ci(self):
        self.assertIn(RULES[5], text())

    def test_rule_7_blocking_finding_closed_by_fix_or_user(self):
        self.assertIn(RULES[6], text())


    # S-41: the tier is copied from the guard; every Reviewer spawn is fenced and its reply saved by the Supervisor
    def test_tier_stage_copies_the_tier_from_the_scope_guard(self):
        t = text()
        block = t[t.find("**Tier.**"):t.find("**Review.**")]
        self.assertIn("Copy `tier: <n>` from the scope guard", block)
        self.assertIn("Reviewer A is never dropped", block)

    def test_review_stage_fences_the_spawn_and_saves_the_reply_after_the_check(self):
        t = text()
        block = t[t.find("**Review.**"):t.find("**Fix.**")]
        for needle in ("<run>/diff.patch", "scripts/budget.py check --run <run>",
                       "scripts/fence.py snapshot --run <run> --role code-reviewer", "Spawn code-reviewer",
                       "one Agent call each in the same turn", "scripts/fence.py check --run <run> --role code-reviewer",
                       "review-1.json", "review-2.json", "--kind subagent"):
            self.assertIn(needle, block, needle)
        order = [block.index(s) for s in ("fence.py snapshot", "Spawn code-reviewer", "fence.py check", "review-1.json")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
