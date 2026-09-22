"""S-67: a backticked path in a tracked Markdown file is a path that exists.

`CLAUDE.md` states the convention; this module is where it is enforced, because the suite is
what CI runs. Planned, deleted and run-folder names are written plain, so the only thing a
backticked path can be is something a reader can open in a fresh checkout.
"""
import functools
import posixpath
import re
import subprocess
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
SPAN = re.compile(r"`([^`\n]+)`")
TRAILING_LINE = re.compile(r":\d+(-\d+)?$")
NEVER_A_PATH = "<>*{}?|\"'$"


def tracked():
    """Every path git knows about, repo-relative. Untracked and ignored files are not documented."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return tuple(out.stdout.split("\n")[:-1]) if out.stdout else ()


@functools.lru_cache(maxsize=None)
def checkout(paths):
    """(files, directories) a fresh checkout holds, both repo-relative and both from git alone.

    The filesystem is not asked. A gitignored run folder sitting in the working copy would make
    `AGI_Research/` resolve on the machine that wrote the sentence and nowhere else, which is the
    one failure this convention exists to prevent.
    """
    files = set(paths)
    dirs = {str(parent) for path in paths for parent in PurePosixPath(path).parents}
    return files, dirs


def is_path_claim(span):
    """True when a backticked span promises a path rather than a command, a URL or a name.

    Conservative on purpose: a span is only a claim when a separator stands between two of its
    segments and nothing marks it as something else. One segment is a name, not a path, whether
    or not it ends in a slash — goal.json and AGI_Research/ both name something that lives in a
    run folder rather than in the checkout, and AGI_Research/ is also the literal line
    `references/goal.md` tells the Supervisor to add to a .gitignore. Whitespace means a command
    line, and a leading ~ or / points outside the checkout, which this repository cannot promise
    anything about.
    """
    return ("/" in span.rstrip("/")
            and not re.search(r"\s", span)
            and "://" not in span
            and not span.startswith(("~", "/"))
            and not any(c in span for c in NEVER_A_PATH))


def resolves(span, doc, paths):
    """Whether `span`, claimed in `doc`, names a file or folder a fresh checkout holds.

    Tried in the order a reader would: beside the document, from the repository root, and
    finally the tail of exactly one tracked path — which is how a skill's own prose can say
    `references/tiers.md` for its sibling and how prose in `docs/` can name a skill's reference
    file without spelling the whole path. A tail matching two paths is not resolved: an
    ambiguous promise is not a promise, and the full path is the way to make it one.
    """
    target = posixpath.normpath(TRAILING_LINE.sub("", span))
    if target == ".":
        return True
    files, dirs = checkout(paths)
    here = str(PurePosixPath(doc.relative_to(ROOT)).parent)
    for base in (here, "."):
        candidate = posixpath.normpath(posixpath.join(base, target))
        if candidate in files or candidate in dirs:
            return True
    return len([p for p in paths if p == target or p.endswith("/" + target)]) == 1


def violations():
    """Every (file, line, span) whose backticks promise a path the checkout does not hold."""
    paths = tracked()
    found = []
    for name in (p for p in paths if p.endswith(".md")):
        doc = ROOT / name
        for number, line in enumerate(doc.read_text().splitlines(), 1):
            for span in SPAN.findall(line):
                if is_path_claim(span) and not resolves(span, doc, paths):
                    found.append((name, number, span))
    return found


class DocPaths(unittest.TestCase):
    def test_every_backticked_path_in_a_tracked_markdown_file_exists(self):
        found = violations()
        self.assertEqual(found, [], msg="write a planned or deleted name plain:\n" + "\n".join(
            f"  {name}:{number}  `{span}`" for name, number, span in found))

    def test_a_missing_path_is_reported_with_its_file_line_and_span(self):
        doc = ROOT / "docs" / "bugs.md"
        original = doc.read_bytes()
        try:
            doc.write_bytes(original + b"\nsee `docs/no-such-file.md` for this.\n")
            found = violations()
            self.assertIn(("docs/bugs.md", len(original.decode().splitlines()) + 2,
                           "docs/no-such-file.md"), found)
        finally:
            doc.write_bytes(original)

    def test_a_command_a_url_and_a_planned_name_are_not_read_as_path_claims(self):
        for span in ("python3 scripts/budget.py check --run <run>", "https://pypi.org/project/x/",
                     "AGI_Research/runs/<goal_id>/", "~/.claude/skills/mystandard/SKILL.md",
                     "scripts/*.py", "goal.json", "AGI_Research/", "fence/"):
            self.assertFalse(is_path_claim(span), msg=span)

    def test_a_file_present_but_untracked_does_not_resolve(self):
        """A gitignored run folder in the working copy must not make a sentence about it true."""
        doc = ROOT / "docs" / "bugs.md"
        stray = ROOT / "docs" / "stray-untracked-probe.md"
        stray.write_text("probe\n")
        try:
            self.assertTrue(stray.exists())
            self.assertFalse(resolves("docs/stray-untracked-probe.md", doc, tracked()))
        finally:
            stray.unlink()

    def test_the_convention_names_where_it_is_enforced(self):
        self.assertIn("tests/test_doc_paths.py", (ROOT / "CLAUDE.md").read_text())


if __name__ == "__main__":
    unittest.main()
