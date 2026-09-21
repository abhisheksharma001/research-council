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

    # S-42: the Thinker is spawned with the first edit, fenced like any other role, and its tests are added or waived
    def write_block(self):
        t = text()
        return t[t.find("**Write, with the Thinker in parallel.**"):t.find("**Guards.**")]

    def test_write_stage_spawns_the_thinker_in_the_same_turn_as_the_first_edit(self):
        self.assertIn("Spawn code-thinker in the same turn you make the first edit", self.write_block())

    def test_write_stage_fences_the_spawn_and_saves_thinker_json_after_the_check(self):
        block = self.write_block()
        for needle in ("scripts/budget.py check --run <run>",
                       "scripts/fence.py snapshot --run <run> --role code-thinker",
                       "scripts/fence.py check --run <run> --role code-thinker",
                       "thinker.json", "--kind subagent"):
            self.assertIn(needle, block, needle)
        order = [block.index(s) for s in ("fence.py snapshot", "Spawn code-thinker",
                                          "fence.py check", "thinker.json")]
        self.assertEqual(order, sorted(order))

    def test_write_stage_closes_a_test_it_cannot_pass_with_the_users_words(self):
        block = self.write_block()
        self.assertIn("done.py resolve --run <run> --test T-n --waived", block)
        self.assertIn("never by your own judgement", block)

    def test_write_stage_journals_a_misestimate_when_a_small_task_grows(self):
        block = self.write_block()
        self.assertIn("expected_small: true` ends over ten diff lines", block)
        self.assertIn("--kind note --cost_usd null --detail misestimate", block)

    # S-43: every stage carries the commands that run it, the stages run in one order, and the reply
    # quotes what the scripts printed
    def span(self, start, end):
        t = text()
        return t[t.find(start):t.find(end)]

    def test_task_stage_asks_for_the_caps_once_per_repository(self):
        block = self.span("**Task.**", "**Write, with the Thinker in parallel.**")
        for needle in (".code-council/config.json", "ask the user for all four numbers",
                       'scripts/task.py new --root "$WORKSPACE"', "never default one",
                       "AGI_Research/ is not ignored"):
            self.assertIn(needle, block, needle)

    def test_guards_stage_runs_both_guards_and_splits_over_the_line_cap(self):
        block = self.span("**Guards.**", "**Tier.**")
        for needle in ("scripts/scope.py check --run <run>", "scripts/deps.py check --run <run>",
                       "propose a split into tasks", "the user picks which", "never raise `max_diff_lines`"):
            self.assertIn(needle, block, needle)

    def test_fix_stage_closes_a_blocking_finding_by_a_fix_or_the_users_words(self):
        block = self.span("**Fix.**", "**Reply.**")
        for needle in ("done.py resolve --run <run> --finding <id> --fixed",
                       'done.py resolve --run <run> --finding <id> --waived "<the user\'s words>"',
                       "Your own reading of the finding closes nothing",
                       "advisory findings are named in the reply"):
            self.assertIn(needle, block, needle)

    def test_done_stage_takes_its_line_from_the_script_not_the_terminal(self):
        block = self.span("**Done.**", "**Reply.**")
        for needle in ("scripts/done.py check --run <run>", "`DONE <sha256>`", "`NOT DONE`",
                       "act on the reason, then run the check again",
                       "is not a substitute for this command"):
            self.assertIn(needle, block, needle)

    def test_the_stages_run_in_one_order(self):
        t = text()
        order = [t.find(s) for s in ("Spawn code-thinker", "scope.py check",
                                     "Spawn code-reviewer", "done.py check")]
        self.assertNotIn(-1, order, order)
        self.assertEqual(order, sorted(order), order)

    def test_reply_quotes_the_printed_line_and_the_budget_meter(self):
        block = self.span("**Reply.**", "## Outputs")
        for needle in ("The printed line verbatim as the first line",
                       "scripts/budget.py check --run <run>`, verbatim",
                       "Never write the word done in a reply that has no printed line behind it"):
            self.assertIn(needle, block, needle)

    def test_reply_explains_every_changed_file_in_learning_mode(self):
        block = self.span("**Reply.**", "## Outputs")
        self.assertIn("`explain: true`", block)
        self.assertIn("one entry per changed file saying what changed, why, and which test proves it", block)


if __name__ == "__main__":
    unittest.main()
