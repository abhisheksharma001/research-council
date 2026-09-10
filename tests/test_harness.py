import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harness.py"
ANSWERS = {"q1": True, "q2": True, "q3": True, "q4": True, "q5": False}


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="council harness ")
        self.home = Path(self.tmp.name).resolve()
        self.workspace = self.home / "target project"
        self.workspace.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, script=SCRIPT, input=None):
        return subprocess.run([sys.executable, str(script), *map(str, args)],
                              cwd=self.workspace, input=input, capture_output=True, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def export(self):
        destination = self.home / "research-council"
        result = self.call("export", "--destination", destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        return destination

    def test_triage_runs_from_foreign_cwd_with_spaces(self):
        result = self.call("run", "--workspace", self.workspace, "triage", "--answers", "-",
                           input=json.dumps(ANSWERS))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["verdict"], "big")
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_dispatch_preserves_small_verdict_exit_code(self):
        result = self.call("run", "--workspace", self.workspace, "triage", "--answers", "-",
                           input=json.dumps(dict.fromkeys(ANSWERS, False)))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["verdict"], "small")

    def test_context_distinguishes_workspace_and_runtime_without_writes(self):
        result = self.call("context", "--workspace", self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["council_root"], str(ROOT))
        self.assertEqual(data["workspace"], str(self.workspace.resolve()))
        self.assertEqual(data["skill"], str(ROOT / "skills/research-council/SKILL.md"))
        self.assertEqual(data["library"], str(ROOT / "library"))
        self.assertEqual(data["mode"], "checkout")
        self.assertNotIn("budget", data)
        self.assertIn("model availability", data["unverified_capabilities"])
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_context_requires_existing_workspace(self):
        result = self.call("context", "--workspace", self.home / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workspace", result.stderr)
        self.assertFalse((self.home / "missing").exists())

    def test_unknown_or_administrative_helper_is_not_executed(self):
        for name in ("promote", "bash", "../goal", "goal.py", "triage;touch marker"):
            with self.subTest(name=name):
                result = self.call("run", "--workspace", self.workspace, name)
                self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_export_is_valid_and_contains_helpers_and_roles(self):
        package = self.export()
        result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_skill.py"), str(package)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for path in ("SKILL.md", "references/goal.md", "runtime/scripts/harness.py",
                     "runtime/scripts/goal.py", "runtime/scripts/promote.py",
                     "runtime/agents/reflection.md", "runtime/strategies/fire.md",
                     "runtime/docs/spec-v1.md"):
            self.assertTrue((package / path).is_file(), path)

    def test_moved_export_resolves_its_own_runtime(self):
        package = self.export()
        moved = self.home / "another installation"
        package.rename(moved)
        script = moved / "runtime/scripts/harness.py"
        result = self.call("context", "--workspace", self.workspace, script=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["council_root"], str(moved / "runtime"))
        self.assertEqual(data["skill"], str(moved / "SKILL.md"))
        self.assertEqual(data["mode"], "bundle")
        self.assertIsNone(data["library"])
        self.assertFalse(data["promotion_available"])
        result = self.call("run", "--workspace", self.workspace, "triage", "--answers", "-",
                           input=json.dumps(ANSWERS), script=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["verdict"], "big")

    def test_export_excludes_state_and_host_configuration(self):
        package = self.export()
        forbidden = {"AGI_Research", "library", ".git", ".devin", ".claude-plugin", "tests", "__pycache__"}
        for path in package.rglob("*"):
            self.assertFalse(set(path.relative_to(package).parts) & forbidden, str(path))
        self.assertFalse((package / "runtime/docs/runs").exists())

    def test_export_refuses_existing_destination_without_touching_it(self):
        destination = self.home / "research-council"
        destination.mkdir()
        marker = destination / "keep.txt"
        marker.write_text("keep")
        result = self.call("export", "--destination", destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual(list(destination.iterdir()), [marker])

    def test_export_refuses_wrong_skill_directory_name(self):
        result = self.call("export", "--destination", self.home / "wrong-name")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "wrong-name").exists())

    def test_incomplete_bundle_fails_preflight(self):
        package = self.export()
        (package / "runtime/scripts/goal.py").unlink()
        result = self.call("context", "--workspace", self.workspace,
                           script=package / "runtime/scripts/harness.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("goal.py", result.stderr)

    def test_incomplete_references_fail_preflight(self):
        package = self.export()
        (package / "references/evidence.md").unlink()
        result = self.call("context", "--workspace", self.workspace,
                           script=package / "runtime/scripts/harness.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references/evidence.md", result.stderr)

    def test_internal_symlink_is_not_exported(self):
        package = self.export()
        source = package / "runtime/scripts/goal.py"
        source.unlink()
        source.symlink_to(package / "runtime/scripts/triage.py")
        destination = self.home / "second" / "research-council"
        destination.parent.mkdir()
        result = self.call("export", "--destination", destination,
                           script=package / "runtime/scripts/harness.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertFalse(destination.exists())

    def test_export_refuses_symlinked_source(self):
        package = self.export()
        source = package / "runtime/scripts/goal.py"
        source.unlink()
        outside = self.home / "outside.py"
        outside.write_text("raise SystemExit(99)")
        source.symlink_to(outside)
        destination = self.home / "second" / "research-council"
        destination.parent.mkdir()
        result = self.call("export", "--destination", destination,
                           script=package / "runtime/scripts/harness.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertFalse(destination.exists())

    def test_devin_wrappers_delegate_to_canonical_skills(self):
        for name in ("research-council", "self-improve"):
            wrapper = ROOT / ".devin/skills" / name / "SKILL.md"
            self.assertTrue(wrapper.is_file(), str(wrapper))
            text = wrapper.read_text()
            self.assertIn(f"../../../skills/{name}/SKILL.md", text)
            self.assertIn("actual location", text)
            self.assertTrue((wrapper.parent / f"../../../skills/{name}/SKILL.md").resolve().is_file())
            result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_skill.py"), str(wrapper.parent)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
