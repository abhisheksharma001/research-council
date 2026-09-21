"""S-39: deps.py lets no new dependency into the diff without a record that it exists."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deps  # noqa: E402
import evidence  # noqa: E402
import task  # noqa: E402

SCRIPT = ROOT / "scripts" / "deps.py"
HARNESS = ROOT / "scripts" / "harness.py"
EVIDENCE = ROOT / "scripts" / "evidence.py"
CAPS = {"minutes": 20, "max_actions": 60, "max_subagents": 3, "usd_estimate_cap": 0, "set_by": "user"}
FILES = {
    "app/main.py": "import os\nimport json\n\ndef main():\n    return json.dumps({})\n",
    "app/helpers.py": "H = 1\n",
    "requirements.txt": "# pinned\nzzdatalib==1.0\n-r extra.txt\n",
    "pyproject.toml": '[project]\nname = "demo"\ndependencies = ["zz-typed-lib>=1"]\n',
    "package.json": '{"name": "demo", "dependencies": {"zzhttp": "^1"}}\n',
    "README.md": "# demo\n",
    ".gitignore": "AGI_Research/\n",
}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def web(uri, **over):
    body = {"source_type": "web", "source_uri": uri, "title": "registry page", "locator": "top of page",
            "excerpt": "Released: 2026-01-01", "access_scope": "public"}
    body.update(over)
    return body


class DepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        for name, text in FILES.items():
            self.write(name, text)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "start")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def append(self, name, text):
        self.write(name, (self.root / name).read_text() + text)

    def new_task(self, **overrides):
        body = {"request_text": "Add a fetch helper.", "test_command": "python3 -m unittest", "allowed_paths": ["**"],
                "max_diff_lines": 200, "expected_small": False, "explain": True, "budget": dict(CAPS)}
        body.update(overrides)
        return task.new(self.root, body)

    def cli(self, run, script=SCRIPT, *before, env=None):
        return subprocess.run([sys.executable, str(script), *before, "check", "--run", str(run)],
                              capture_output=True, text=True, cwd=self.root, env={**os.environ, **(env or {})})

    # nothing new
    def test_clean_tree_has_no_new_names(self):
        r = self.cli(self.new_task())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 0\n")

    def test_relative_imports_and_prose_are_not_dependencies(self):
        run = self.new_task()
        self.append("app/main.py", "from . import helpers\nfrom .helpers import H\n")
        self.append("README.md", "import pyautoscrape\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 0\n")

    def test_version_bump_in_a_manifest_is_not_a_new_name(self):
        run = self.new_task()
        self.write("requirements.txt", "# pinned\nzzdatalib==2.0\n-r extra.txt\n")
        self.write("package.json", '{"name": "demo", "dependencies": {"zzhttp": "^2"}}\n')
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 0\n")

    # resolved
    def test_stdlib_and_repository_modules_resolve(self):
        run = self.new_task()
        self.append("app/main.py", "from __future__ import annotations\nimport re\nimport helpers\nfrom app.helpers import H\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 4\nresolved: __future__ (stdlib)\nresolved: app (in the repository)\n"
                                   "resolved: helpers (in the repository)\nresolved: re (stdlib)\n")

    def test_installed_module_resolves(self):
        run = self.new_task()
        self.append("app/main.py", "import zzinstalled\n")
        with tempfile.TemporaryDirectory() as site:
            (Path(site) / "zzinstalled.py").write_text("X = 1\n")
            r = self.cli(run, env={"PYTHONPATH": site})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 1\nresolved: zzinstalled (installed)\n")
        self.assertEqual(self.cli(run).returncode, 2)

    def test_manifests_at_start_commit_resolve_with_folded_names(self):
        run = self.new_task()
        self.append("app/main.py", "import zzdatalib\nimport zz_typed_lib\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 2\nresolved: zz_typed_lib (in pyproject.toml at start_commit)\n"
                                   "resolved: zzdatalib (in requirements.txt at start_commit)\n")

    def test_lock_files_at_start_commit_resolve(self):
        self.write("poetry.lock", '[[package]]\nname = "zzlocked"\nversion = "1.0"\n')
        self.write("package-lock.json", '{"packages": {"": {}, "node_modules/zzlockednpm": {"version": "1.0"}}}\n')
        self.write("yarn.lock", '# yarn lockfile v1\n\n"@zz/yarned@^1.0.0":\n  version "1.0.0"\n')
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "locks")
        run = self.new_task()
        self.append("app/main.py", "import zzlocked\n")
        self.write("package.json", '{"name": "demo", "dependencies": {"zzhttp": "^1", "zzlockednpm": "1", "@zz/yarned": "1"}}\n')
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 3\nresolved: @zz/yarned (in yarn.lock at start_commit)\n"
                                   "resolved: zzlocked (in poetry.lock at start_commit)\n"
                                   "resolved: zzlockednpm (in package-lock.json at start_commit)\n")

    # acceptance: an import nothing names is unresolved until a registry record exists
    def test_hallucinated_import_is_unresolved(self):
        run = self.new_task()
        self.append("app/main.py", "import pyautoscrape\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "unresolved: pyautoscrape\n")

    def test_registry_record_resolves_the_exact_name(self):
        run = self.new_task()
        self.append("app/main.py", "import pyautoscrape\n")
        evidence.add(run, web("https://pypi.org/project/pyautoscrape-extra/"))
        evidence.add(run, web("https://pypi.org/project/pyautoscrape/1.0/"))
        evidence.add(run, web("https://pypi.org/project/pyautoscrape/", source_type="file"))
        self.assertEqual(self.cli(run).returncode, 2)
        evidence.add(run, web("https://www.pypi.org/project/PyAutoScrape"))
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 1\nresolved: pyautoscrape (evidence E-4)\n")

    def test_npm_name_needs_an_npm_record(self):
        run = self.new_task()
        self.write("package.json", '{"name": "demo", "dependencies": {"zzhttp": "^1", "left-pad-zz": "1"},'
                                   ' "devDependencies": {"@zz/tool": "1"}}\n')
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "unresolved: @zz/tool\nunresolved: left-pad-zz\n")
        evidence.add(run, web("https://pypi.org/project/left-pad-zz/"))
        self.assertEqual(self.cli(run).stdout, "unresolved: @zz/tool\nunresolved: left-pad-zz\n")
        evidence.add(run, web("https://www.npmjs.com/package/left-pad-zz"))
        evidence.add(run, web("https://www.npmjs.com/package/%40zz/tool"))
        r = self.cli(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 2\nresolved: @zz/tool (evidence E-3)\nresolved: left-pad-zz (evidence E-2)\n")

    def test_names_added_to_manifests_are_checked(self):
        run = self.new_task()
        self.append("requirements.txt", "pyautoscrape>=1  # scraping\nzz-http-client @ https://example.invalid/x.whl\n")
        self.write("pyproject.toml", FILES["pyproject.toml"] + '[project.optional-dependencies]\ndev = ["zz-dev-tool"]\n')
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "unresolved: pyautoscrape\nunresolved: zz-dev-tool\nunresolved: zz-http-client\n")

    def test_a_manifest_edited_in_the_same_diff_does_not_resolve_its_own_import(self):
        run = self.new_task()
        self.append("requirements.txt", "pyautoscrape\n")
        self.append("app/main.py", "import zzdatalib, pyautoscrape as scrape\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "unresolved: pyautoscrape\n")

    def test_new_untracked_file_imports_are_seen(self):
        run = self.new_task()
        self.write("app/fetch.py", "import pyautoscrape\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "unresolved: pyautoscrape\n")

    # units
    def test_python_import_forms(self):
        lines = ["import a.b as ab, c", "  from d.e import (", "from . import f", "from .g import h",
                 "x = 'import i'", "# import j", "import", "from k import l"]
        self.assertEqual(deps.python_imports(lines), {"a", "c", "d", "k"})

    def test_manifest_kinds(self):
        self.assertEqual([deps.kind(p) for p in ("requirements-dev.txt", "docs/requirements.txt", "x/package.json",
                                                  "pyproject.toml", "requirements.md", "a/b.py", "uv.lock", "notes.txt")],
                         ["requirements", "requirements", "package", "pyproject", None, "py", "lock", None])

    # offline, read-only
    def test_check_opens_no_socket_and_runs_only_git(self):
        run = self.new_task()
        self.append("app/main.py", "import pyautoscrape\n")
        seen = set()
        real = subprocess.run

        def spy(argv, *args, **kwargs):
            seen.add(Path(argv[0]).name)
            return real(argv, *args, **kwargs)

        with mock.patch("socket.socket", side_effect=AssertionError("network")), mock.patch("subprocess.run", spy):
            resolved, unresolved = deps.check(run)
        self.assertEqual((resolved, unresolved), ([], ["pyautoscrape"]))
        self.assertEqual(seen, {"git"})

    def test_check_never_touches_the_working_tree(self):
        run = self.new_task()
        self.append("app/main.py", "import pyautoscrape\n")
        self.append("requirements.txt", "pyautoscrape\n")
        self.write("app/fetch.py", "import zzdatalib\n")
        before = (git(self.root, "status", "--porcelain"), git(self.root, "diff"))
        self.assertEqual(self.cli(run).returncode, 2)
        self.assertEqual((git(self.root, "status", "--porcelain"), git(self.root, "diff")), before)

    # bad input
    def test_manifest_that_does_not_parse_is_exit_1(self):
        run = self.new_task()
        self.write("pyproject.toml", "[project\n")
        r = self.cli(run)
        self.assertEqual(r.returncode, 1)
        self.assertIn("pyproject.toml does not parse", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_tampered_task_is_exit_1(self):
        run = self.new_task()
        t = json.loads((run / "task.json").read_text())
        t["request_text"] = "x"
        (run / "task.json").write_text(json.dumps(t))
        r = self.cli(run)
        self.assertEqual(r.returncode, 1)
        self.assertIn("frozen_sha256 mismatch", r.stderr)

    def test_workspace_without_git_is_exit_1(self):
        with tempfile.TemporaryDirectory() as plain:
            body = {"request_text": "x", "test_command": "true", "allowed_paths": ["a"], "max_diff_lines": 5,
                    "expected_small": True, "explain": False, "budget": dict(CAPS)}
            r = self.cli(task.new(plain, body))
        self.assertEqual(r.returncode, 1)
        self.assertIn("start_commit is none", r.stderr)

    # plumbing
    def test_evidence_cli_accepts_a_task_run(self):
        run = self.new_task()
        r = subprocess.run([sys.executable, str(EVIDENCE), "add", "--run", str(run), "--from", "-"],
                           input=json.dumps(web("https://pypi.org/project/pyautoscrape/")), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("E-1 recorded (web: "))
        self.assertEqual(evidence.read(run)[0]["source_uri"], "https://pypi.org/project/pyautoscrape/")

    def test_harness_runs_deps_in_the_workspace(self):
        run = self.new_task()
        r = self.cli(run, HARNESS, "run", "--workspace", str(self.root), "deps")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "new: 0\n")


if __name__ == "__main__":
    unittest.main()
