import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import goal  # noqa: E402
import promote  # noqa: E402
import retrieve  # noqa: E402

SCRIPT = ROOT / "scripts" / "retrieve.py"
FIXTURE = ROOT / "tests" / "fixtures" / "skill_min" / "booking-lookup-window"
GOAL_FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"
GOAL_MD = ROOT / "skills" / "research-council" / "references" / "goal.md"
SKILL_MD = ROOT / "skills" / "research-council" / "SKILL.md"

SKILLS = [
    # skill_id, version, scope, description, triggers, mechanism, counterexamples
    ("booking-lookup-window", "1.0.0", "private",
     "Check whether a lookup tool went silent inside a window of a call export.",
     ["bookings failing", "call volume normal", "lookup tool silent", "call export"],
     "Zero lookup attempts while calls continue means the tool was not offered to the model.",
     ["Calls routed to a different assistant also show zero attempts."]),
    ("booking-lookup-window", "1.1.0", "private",
     "Check whether a lookup tool went silent inside a window of a call export.",
     ["bookings failing", "call volume normal", "lookup tool silent", "call export"],
     "Zero lookup attempts while calls continue means the tool was not offered to the model.",
     ["Calls routed to a different assistant also show zero attempts."]),
    ("webhook-retry-storm", "1.0.0", "public",
     "Spot duplicate webhook deliveries caused by provider retries.",
     ["webhook retries", "duplicate events", "idempotency key"],
     "Repeated event ids inside one minute mean the provider retried, not the consumer.",
     ["Consumer double-processes without any retries."]),
    ("stale-cache-probe", "1.0.0", "public",
     "Tell whether a cache served old prices past its expiry.",
     ["stale cache", "old prices"],
     "Prices older than the expiry with fresh upstream values mean the cache was not invalidated.",
     []),
]
DEPRECATED = ("stale-cache-probe", "1.0.0")


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def build_library(root):
    """A real library: every skill promoted through promote.py, then one entry marked deprecated."""
    library = root / "library"
    library.mkdir()
    (library / promote.REGISTRY).write_text('{\n  "schema_version": 1,\n  "entries": []\n}\n', encoding="utf-8")
    (library / promote.RECEIPTS).write_text("", encoding="utf-8")
    for n, (skill_id, version, scope, desc, triggers, mechanism, counter) in enumerate(SKILLS):
        dest = root / "candidates" / str(n) / skill_id
        shutil.copytree(FIXTURE, dest)
        m = json.loads((dest / promote.MANIFEST).read_text(encoding="utf-8"))
        m["skill_id"], m["name"], m["version"] = skill_id, skill_id, version
        m["access"]["scope"] = scope
        m["applicability"] = {"triggers": triggers, "known_counterexamples": counter}
        m["mechanism"] = mechanism
        (dest / promote.MANIFEST).write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
        skill = (dest / "SKILL.md").read_text(encoding="utf-8")
        skill = skill.replace("name: booking-lookup-window", f"name: {skill_id}", 1)
        skill = re.sub(r"^description: .*$", f"description: {desc}", skill, count=1, flags=re.M)
        (dest / "SKILL.md").write_text(skill, encoding="utf-8")
        result = promote.promote(dest, library)
        assert result["ok"], result
    set_status(library, *DEPRECATED, status="deprecated")
    return library


def set_status(library, skill_id, version, **fields):
    path = library / promote.REGISTRY
    registry = json.loads(path.read_text(encoding="utf-8"))
    for e in registry["entries"]:
        if (e["skill_id"], e["version"]) == (skill_id, version):
            e.update(fields)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


class RetrieveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.library = build_library(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy_library(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "library"
        shutil.copytree(self.library, dest)
        return dest

    def ids(self, found):
        return [(r["skill_id"], r["version"]) for r in found["results"]]

    # --- acceptance ---------------------------------------------------------------
    def test_three_shared_trigger_tokens_ranks_that_skill_first(self):
        # query shares bookings, failing, silent with booking-lookup-window's triggers; none with webhook-retry-storm
        query = "bookings are failing and the lookup is silent"
        found = retrieve.retrieve(query, self.library, scope="private")
        self.assertEqual(found["results"][0]["skill_id"], "booking-lookup-window")
        self.assertGreaterEqual(found["results"][0]["score"], 3)
        self.assertNotIn("webhook-retry-storm", [r["skill_id"] for r in found["results"]])
        cli = run_cli("--query", query, "--library", str(self.library), "--scope", "private")
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertIn("1. booking-lookup-window@", cli.stdout)
        self.assertNotIn("webhook-retry-storm", cli.stdout)

    def test_deprecated_status_is_not_shown_and_is_shown_once_validated_again(self):
        query = "stale cache old prices"
        cli = run_cli("--query", query, "--library", str(self.library))
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertNotIn("stale-cache-probe", cli.stdout)
        self.assertIn("no matching skills", cli.stdout)
        library = self.copy_library()
        set_status(library, *DEPRECATED, status="validated")
        self.assertEqual(self.ids(retrieve.retrieve(query, library)), [DEPRECATED])

    # --- filters ------------------------------------------------------------------
    def test_inactive_entry_is_not_shown(self):
        library = self.copy_library()
        set_status(library, "webhook-retry-storm", "1.0.0", active=False)
        self.assertEqual(self.ids(retrieve.retrieve("duplicate webhook retries", library)), [])

    def test_public_scope_hides_private_skills_and_says_how_many(self):
        query = "bookings failing lookup silent"
        found = retrieve.retrieve(query, self.library)
        self.assertEqual(found["results"], [])
        self.assertEqual(found["hidden_private"], 2)
        cli = run_cli("--query", query, "--library", str(self.library))
        self.assertIn("hidden: 2 private skill(s); pass --scope private", cli.stdout)

    def test_private_scope_shows_public_and_private(self):
        found = retrieve.retrieve("bookings failing duplicate webhook", self.library, scope="private")
        self.assertEqual(found["hidden_private"], 0)
        self.assertEqual({r["skill_id"] for r in found["results"]}, {"booking-lookup-window", "webhook-retry-storm"})

    def test_unknown_scope_is_refused(self):
        with self.assertRaises(ValueError):
            retrieve.retrieve("x", self.library, scope="secret")

    def test_missing_library_is_refused_on_the_cli(self):
        cli = run_cli("--query", "x", "--library", str(Path(self.tmp.name) / "nope"))
        self.assertEqual(cli.returncode, 1)
        self.assertIn("refused:", cli.stdout)

    # --- scoring ------------------------------------------------------------------
    def test_tokens_lowercase_strip_punctuation_and_drop_stopwords(self):
        self.assertEqual(retrieve.tokens("The Bookings, are FAILING! (a lot)"), {"bookings", "failing", "lot"})

    def test_score_counts_distinct_shared_tokens_not_repeats(self):
        found = retrieve.retrieve("bookings bookings bookings", self.library, scope="private")
        self.assertEqual(found["query_tokens"], ["bookings"])
        self.assertEqual(found["results"][0]["score"], 1)
        self.assertEqual(found["results"][0]["matched"], ["bookings"])

    def test_newer_version_ranks_first_when_scores_tie(self):
        found = retrieve.retrieve("bookings failing", self.library, scope="private")
        self.assertEqual(self.ids(found)[:2], [("booking-lookup-window", "1.1.0"), ("booking-lookup-window", "1.0.0")])

    def test_description_from_skill_md_is_searched(self):
        # "deliveries" appears only in webhook-retry-storm's SKILL.md description
        found = retrieve.retrieve("deliveries", self.library)
        self.assertEqual(self.ids(found), [("webhook-retry-storm", "1.0.0")])
        self.assertEqual(found["results"][0]["matched"], ["deliveries"])

    def test_only_the_four_named_fields_are_searched(self):
        # "reachable" appears in the fixture manifest's goal field and nowhere in the four searched fields
        self.assertEqual(self.ids(retrieve.retrieve("reachable", self.library, scope="private")), [])

    def test_at_most_five_results(self):
        entry, unit, manifest = retrieve.load_units(self.library)[0]
        fake = [({**entry, "skill_id": f"skill-{i}"}, unit, manifest) for i in range(8)]
        with mock.patch.object(retrieve, "load_units", return_value=fake):
            found = retrieve.retrieve("bookings failing", self.library, scope="private")
        self.assertEqual(len(found["results"]), 5)

    # --- output -------------------------------------------------------------------
    def test_output_shows_validation_status_boundaries_and_the_not_authority_line(self):
        cli = run_cli("--query", "bookings failing", "--library", str(self.library), "--scope", "private")
        first = cli.stdout.splitlines()[0]
        self.assertIn("similarity is not authority", first)
        entry = next(e for e in json.loads((self.library / promote.REGISTRY).read_text())["entries"]
                     if (e["skill_id"], e["version"]) == ("booking-lookup-window", "1.1.0"))
        self.assertIn(f"status validated (validation {entry['validation_id']}, {entry['promoted_at']})", cli.stdout)
        self.assertIn("known counterexamples: Calls routed to a different assistant also show zero attempts.", cli.stdout)
        self.assertIn("boundary: none recorded", cli.stdout)
        self.assertIn("contracts: T-1, T-2", cli.stdout)

    def test_snapshot_line_is_a_valid_library_snapshot_for_goal_py(self):
        found = retrieve.retrieve("bookings failing", self.library, scope="private")
        snap = retrieve.snapshot_line(found["results"])
        self.assertRegex(snap, r"^booking-lookup-window@1\.1\.0 validation [0-9a-f-]{36} contracts T-1,T-2; booking-lookup-window@1\.0\.0 ")
        body = json.loads(GOAL_FIXTURE.read_text(encoding="utf-8"))
        body["library_snapshot"] = snap
        self.assertEqual(goal.validate(body), [])
        cli = run_cli("--query", "bookings failing", "--library", str(self.library), "--scope", "private")
        self.assertIn(f"snapshot: {snap}", cli.stdout)

    def test_empty_result_prints_snapshot_null(self):
        cli = run_cli("--query", "zzz", "--library", str(self.library))
        self.assertIn("no matching skills", cli.stdout)
        self.assertIn("snapshot: null", cli.stdout)

    # --- wiring -------------------------------------------------------------------
    def test_goal_md_and_skill_md_route_retrieval_before_hypotheses(self):
        goal_md = GOAL_MD.read_text(encoding="utf-8")
        self.assertIn("scripts/retrieve.py", goal_md)
        self.assertIn("similarity is not authority", " ".join(goal_md.lower().split()))
        self.assertLess(goal_md.index("retrieve.py"), goal_md.index("## Template"))
        skill = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("scripts/retrieve.py", skill)
        self.assertNotIn("S-11 retrieval, not yet implemented", skill)


if __name__ == "__main__":
    unittest.main()
