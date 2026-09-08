import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_skill  # noqa: E402

REAL = ROOT / "skills" / "research-council"


def write_skill(tmp, dirname, frontmatter, body="# x\n"):
    d = Path(tmp) / dirname
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return d


class ValidateSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_real_skill_is_valid(self):
        self.assertEqual(validate_skill.validate(REAL), [])

    def test_cli_prints_ok_and_exits_zero(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(REAL)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "OK")

    def test_uppercase_name_rejected(self):
        d = write_skill(self.tmp, "Research-Council", "name: Research-Council\ndescription: x")
        errs = validate_skill.validate(d)
        self.assertTrue(any(e.startswith("name:") and "lowercase" in e for e in errs), errs)

    def test_name_must_match_directory(self):
        d = write_skill(self.tmp, "other-dir", "name: research-council\ndescription: x")
        errs = validate_skill.validate(d)
        self.assertTrue(any("must match directory" in e for e in errs), errs)

    def test_missing_description_rejected(self):
        d = write_skill(self.tmp, "a-skill", "name: a-skill")
        errs = validate_skill.validate(d)
        self.assertTrue(any(e.startswith("description:") for e in errs), errs)

    def test_unknown_key_rejected(self):
        d = write_skill(self.tmp, "a-skill", "name: a-skill\ndescription: x\nversion: 1.0")
        errs = validate_skill.validate(d)
        self.assertTrue(any("unknown key 'version'" in e for e in errs), errs)

    def test_metadata_nested_value_rejected(self):
        d = write_skill(self.tmp, "a-skill", "name: a-skill\ndescription: x\nmetadata:\n  manifest:\n    deep: 1")
        errs = validate_skill.validate(d)
        self.assertTrue(errs, "nested metadata must be rejected")

    def test_body_over_500_lines_rejected(self):
        d = write_skill(self.tmp, "a-skill", "name: a-skill\ndescription: x", body="line\n" * 501)
        errs = validate_skill.validate(d)
        self.assertTrue(any(e.startswith("body:") for e in errs), errs)

    def test_cli_exit_one_names_rule(self):
        d = write_skill(self.tmp, "a-skill", "name: A-Skill\ndescription: x")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_skill.py"), str(d)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL name:", r.stdout)


if __name__ == "__main__":
    unittest.main()
