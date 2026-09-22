"""S-69: a bug row says where its fix landed.

`docs/bugs.md` is what a reader consults to learn whether a defect is still present. A row that
claims a fix without naming the pull request that carried it cannot be checked against the
repository, and a row left at "fixed locally" or "PR pending" after the merge understates work
that is on main — bug 22, one file along. So a state cell either names a merge or says the fix
has not landed.
"""
import re
import unittest
from pathlib import Path

BUGS = Path(__file__).resolve().parent.parent / "docs" / "bugs.md"
MERGED = re.compile(r"PR #\d+")
NOT_LANDED = re.compile(r"\b(open|queued|parked|blocked)\b")


def rows():
    """(id, state) for every data row of every table in the bug log.

    The two tables have six and four columns, so the state is the last cell rather than a fixed
    index, and a header or separator row is told apart by its own shape instead of by counting
    lines: a separator holds nothing but dashes, colons and spaces, and a header opens with the
    column name the tables share.
    """
    found = []
    for line in BUGS.read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4 or set("".join(cells)) <= set("-: "):
            continue
        if cells[0] in ("id", "date"):
            continue
        found.append((cells[0], cells[-1]))
    return found


class BugLogTests(unittest.TestCase):
    def test_the_log_still_has_rows_to_check(self):
        """A parser that silently finds nothing would pass every other test here."""
        self.assertGreaterEqual(len(rows()), 30)

    def test_every_row_names_its_merge_or_says_the_fix_has_not_landed(self):
        for identifier, state in rows():
            with self.subTest(row=identifier):
                self.assertTrue(
                    MERGED.search(state) or NOT_LANDED.search(state),
                    msg=f"row {identifier} claims a fix without naming PR #<number>: {state!r}")


if __name__ == "__main__":
    unittest.main()
