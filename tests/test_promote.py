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
import promote  # noqa: E402
import validate_manifest  # noqa: E402

PROMOTE_SCRIPT = ROOT / "scripts" / "promote.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_manifest.py"
FIXTURE = ROOT / "tests" / "fixtures" / "skill_min" / "booking-lookup-window"
SCHEMA = ROOT / "library" / "schema" / "manifest.schema.json"
LIBRARY_MD = ROOT / "skills" / "research-council" / "references" / "library.md"
SKILL_MD = ROOT / "skills" / "research-council" / "SKILL.md"
DESIGNED_FIELDS = (
    "schema_version", "skill_id", "name", "version", "record_type", "evidence_level", "origin",
    "goal", "applicability", "inputs", "outputs", "mechanism", "procedure", "dependencies",
    "conflicts", "refs", "task_contracts", "curiosity", "lineage", "integrity", "access",
)


def run_cli(script, *args):
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def read_manifest(candidate):
    return json.loads((candidate / promote.MANIFEST).read_text(encoding="utf-8"))


def write_manifest(candidate, manifest):
    (candidate / promote.MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


class PromoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.library = self.root / "library"
        self.library.mkdir()
        (self.library / promote.REGISTRY).write_text('{\n  "schema_version": 1,\n  "entries": []\n}\n', encoding="utf-8")
        (self.library / promote.RECEIPTS).write_text("", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self, skill_id="booking-lookup-window", version="1.0.0"):
        """A fresh copy of the fixture skill, renamed if asked. Name always equals skill_id."""
        self.n = getattr(self, "n", 0) + 1
        dest = self.root / "candidates" / f"{self.n}-{version}" / skill_id
        shutil.copytree(FIXTURE, dest)
        m = read_manifest(dest)
        m["skill_id"], m["name"], m["version"] = skill_id, skill_id, version
        write_manifest(dest, m)
        skill = (dest / "SKILL.md").read_text(encoding="utf-8")
        (dest / "SKILL.md").write_text(skill.replace("name: booking-lookup-window", f"name: {skill_id}", 1), encoding="utf-8")
        return dest

    def registry_bytes(self):
        return (self.library / promote.REGISTRY).read_bytes()

    def receipts(self):
        text = (self.library / promote.RECEIPTS).read_text(encoding="utf-8")
        return [json.loads(l) for l in text.splitlines() if l.strip()]

    def unit(self, skill_id, version):
        return self.library / promote.UNITS / skill_id / version / skill_id

    # --- acceptance ---------------------------------------------------------------

    def test_all_pass_registry_lists_new_version_and_receipts_gain_one_line(self):
        before = self.registry_bytes()
        proc = run_cli(PROMOTE_SCRIPT, "--candidate", str(self.candidate()), "--library", str(self.library))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("promoted ", proc.stdout)
        registry = json.loads(self.registry_bytes())
        self.assertEqual([(e["skill_id"], e["version"]) for e in registry["entries"]], [("booking-lookup-window", "1.0.0")])
        entry = registry["entries"][0]
        self.assertEqual(entry["status"], "validated")
        self.assertTrue(entry["active"])
        self.assertEqual(len(self.receipts()), 1)
        self.assertNotEqual(before, self.registry_bytes())
        self.assertTrue((self.unit("booking-lookup-window", "1.0.0") / promote.VALIDATION).is_file())

    def test_retained_contract_failure_exits_1_and_registry_is_byte_identical(self):
        self.assertTrue(promote.promote(self.candidate(), self.library)["ok"])
        retained = self.unit("booking-lookup-window", "1.0.0")
        m = read_manifest(retained)
        m["task_contracts"][0]["expected_stdout"] = "WRONG OUTPUT"
        write_manifest(retained, m)
        before, receipts_before = self.registry_bytes(), self.receipts()
        proc = run_cli(PROMOTE_SCRIPT, "--candidate", str(self.candidate("other-check")), "--library", str(self.library))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL booking-lookup-window@1.0.0 T-1: stdout lacks 'WRONG OUTPUT'", proc.stdout)
        self.assertIn("registry untouched", proc.stdout)
        self.assertEqual(before, self.registry_bytes())
        self.assertEqual(receipts_before, self.receipts())
        self.assertFalse(self.unit("other-check", "1.0.0").exists())

    # --- contracts ----------------------------------------------------------------

    def test_candidate_contract_failure_refuses_and_writes_nothing(self):
        cand = self.candidate()
        m = read_manifest(cand)
        m["task_contracts"][1]["expected_exit"] = 3
        write_manifest(cand, m)
        before = self.registry_bytes()
        result = promote.promote(cand, self.library)
        self.assertFalse(result["ok"])
        failed = [r for r in result["results"] if not r["ok"]]
        self.assertEqual([(r["contract"], r["detail"]) for r in failed], [("T-2", "exit 0, expected 3")])
        self.assertEqual(before, self.registry_bytes())
        self.assertEqual(self.receipts(), [])
        self.assertFalse((self.library / promote.UNITS).exists() and any((self.library / promote.UNITS).iterdir()))

    def test_changed_fixture_fails_its_contract_by_hash(self):
        cand = self.candidate()
        calls = cand / "references" / "fixtures" / "calls.json"
        calls.write_text(calls.read_text(encoding="utf-8").replace("c-5", "c-9"), encoding="utf-8")
        result = promote.promote(cand, self.library)
        self.assertFalse(result["ok"])
        self.assertTrue(all("changed since the contract was written" in r["detail"] for r in result["results"]))

    def test_every_contract_of_every_active_version_runs_no_sampling(self):
        self.assertTrue(promote.promote(self.candidate(), self.library)["ok"])
        self.assertTrue(promote.promote(self.candidate("second-check"), self.library)["ok"])
        with mock.patch("promote.run_contract", wraps=promote.run_contract) as spy:
            result = promote.promote(self.candidate("third-check"), self.library)
        self.assertTrue(result["ok"])
        ran = sorted((r["skill_id"], r["contract"]) for r in result["results"])
        self.assertEqual(ran, sorted([
            ("booking-lookup-window", "T-1"), ("booking-lookup-window", "T-2"),
            ("second-check", "T-1"), ("second-check", "T-2"),
            ("third-check", "T-1"), ("third-check", "T-2"),
        ]))
        self.assertEqual(spy.call_count, 6)

    def test_contracts_run_inside_their_own_unit_directory(self):
        self.assertTrue(promote.promote(self.candidate(), self.library)["ok"])
        with mock.patch("promote.run_contract", wraps=promote.run_contract) as spy:
            promote.promote(self.candidate("second-check"), self.library)
        cwds = [Path(call.args[0]) for call in spy.call_args_list]
        self.assertEqual(cwds[:2], [self.unit("booking-lookup-window", "1.0.0")] * 2)
        self.assertEqual(cwds[2].name, "second-check")

    def test_static_failure_runs_no_commands(self):
        cand = self.candidate()
        m = read_manifest(cand)
        del m["mechanism"]
        write_manifest(cand, m)
        with mock.patch("promote.run_contract") as spy:
            with self.assertRaises(ValueError) as ctx:
                promote.promote(cand, self.library)
        self.assertIn("$.mechanism: required", str(ctx.exception))
        self.assertEqual(spy.call_count, 0)

    # --- static rules -------------------------------------------------------------

    def test_skill_md_must_validate_and_name_must_match_directory(self):
        cand = self.candidate()
        skill = cand / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace("name: booking-lookup-window", "name: Booking-Lookup", 1), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            promote.promote(cand, self.library)
        self.assertIn("skill: name:", str(ctx.exception))

    def test_integrity_hash_mismatch_is_refused(self):
        cand = self.candidate()
        claims = cand / promote.CLAIMS
        claims.write_text(claims.read_text(encoding="utf-8").replace("04:00", "04:01"), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            promote.promote(cand, self.library)
        self.assertIn("integrity: references/claims.jsonl does not match", str(ctx.exception))

    def test_refs_must_resolve_to_shipped_claims_or_evidence(self):
        cand = self.candidate()
        m = read_manifest(cand)
        m["refs"].append("C-9")
        write_manifest(cand, m)
        with self.assertRaises(ValueError) as ctx:
            promote.promote(cand, self.library)
        self.assertIn("refs: C-9 is not in the shipped", str(ctx.exception))

    def test_dependencies_must_be_active_library_versions(self):
        cand = self.candidate("needs-base")
        m = read_manifest(cand)
        m["dependencies"] = [{"skill_id": "booking-lookup-window", "version": "1.0.0"}]
        write_manifest(cand, m)
        with self.assertRaises(ValueError) as ctx:
            promote.promote(cand, self.library)
        self.assertIn("dependencies: booking-lookup-window@1.0.0 is not an active", str(ctx.exception))
        self.assertTrue(promote.promote(self.candidate(), self.library)["ok"])
        self.assertTrue(promote.promote(cand, self.library)["ok"])

    def test_versions_are_immutable_and_prior_versions_stay_active(self):
        self.assertTrue(promote.promote(self.candidate(), self.library)["ok"])
        with self.assertRaises(ValueError) as ctx:
            promote.promote(self.candidate(), self.library)
        self.assertIn("already registered", str(ctx.exception))
        self.assertTrue(promote.promote(self.candidate(version="1.0.1"), self.library)["ok"])
        entries = json.loads(self.registry_bytes())["entries"]
        self.assertEqual([(e["version"], e["active"]) for e in entries], [("1.0.0", True), ("1.0.1", True)])

    def test_candidate_must_not_ship_validation_json(self):
        cand = self.candidate()
        (cand / promote.VALIDATION).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            promote.promote(cand, self.library)
        self.assertIn("must not ship references/validation.json", str(ctx.exception))

    # --- what a success writes ----------------------------------------------------

    def test_receipts_chain_registry_hashes_and_no_temp_file_remains(self):
        r0 = self.registry_bytes()
        promote.promote(self.candidate(), self.library)
        r1 = self.registry_bytes()
        promote.promote(self.candidate("second-check"), self.library)
        r2 = self.registry_bytes()
        a, b = self.receipts()
        self.assertEqual(a["prior_registry_sha256"], promote.sha256_bytes(r0))
        self.assertEqual(a["new_registry_sha256"], promote.sha256_bytes(r1))
        self.assertEqual(b["prior_registry_sha256"], promote.sha256_bytes(r1))
        self.assertEqual(b["new_registry_sha256"], promote.sha256_bytes(r2))
        self.assertFalse((self.library / (promote.REGISTRY + ".tmp")).exists())

    def test_package_sha256_covers_shipped_files_but_not_validation_json(self):
        result = promote.promote(self.candidate(), self.library)
        unit = Path(result["unit"])
        entry = json.loads(self.registry_bytes())["entries"][0]
        self.assertEqual(entry["package_sha256"], promote.package_sha256(unit))
        self.assertEqual(entry["package_sha256"], self.receipts()[0]["package_sha256"])
        (unit / promote.VALIDATION).write_text("{}", encoding="utf-8")
        self.assertEqual(entry["package_sha256"], promote.package_sha256(unit))
        (unit / "scripts" / "check_window.py").write_text("print('x')\n", encoding="utf-8")
        self.assertNotEqual(entry["package_sha256"], promote.package_sha256(unit))

    def test_validation_json_lists_every_contract_run_with_its_validation_id(self):
        result = promote.promote(self.candidate(), self.library)
        doc = json.loads((Path(result["unit"]) / promote.VALIDATION).read_text(encoding="utf-8"))
        self.assertEqual(doc["validation_id"], result["validation_id"])
        self.assertEqual(doc["validation_id"], json.loads(self.registry_bytes())["entries"][0]["validation_id"])
        self.assertEqual([c["contract"] for c in doc["contracts"]], ["T-1", "T-2"])
        self.assertTrue(all(c["ok"] for c in doc["contracts"]))

    # --- schema checker -----------------------------------------------------------

    def test_schema_names_every_designed_field_and_requires_them(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(sorted(schema["required"]), sorted(DESIGNED_FIELDS))
        self.assertEqual(sorted(schema["properties"]), sorted(DESIGNED_FIELDS))

    def test_validate_manifest_reports_enum_type_pattern_and_unknown_fields(self):
        m = read_manifest(FIXTURE)
        m["record_type"] = "essay"
        m["version"] = "one"
        m["task_contracts"][0]["expected_exit"] = "0"
        m["extra"] = 1
        errors = validate_manifest.validate(m)
        self.assertIn("$.record_type: must be one of ['research-procedure', 'recipe', 'diagnostic', 'boundary']", errors)
        self.assertTrue(any(e.startswith("$.version: does not match") for e in errors))
        self.assertIn("$.task_contracts[0].expected_exit: must be integer", errors)
        self.assertIn("$.extra: not an allowed field", errors)

    def test_validate_manifest_cross_field_rules_and_unknown_schema_keyword(self):
        m = read_manifest(FIXTURE)
        del m["task_contracts"][0]["fixture_hash"]
        m["integrity"]["files"]["references/claims.jsonl"] = "abc"
        errors = validate_manifest.validate(m)
        self.assertIn("$.task_contracts[0]: fixture and fixture_hash must be given together", errors)
        self.assertIn("$.integrity.files.references/claims.jsonl: must be a sha256 hex digest", errors)
        self.assertEqual(validate_manifest.check(1, {"maximum": 3}), ["$: schema uses unsupported keyword(s) ['maximum']"])

    def test_validate_manifest_cli(self):
        ok = run_cli(VALIDATE_SCRIPT, str(FIXTURE / promote.MANIFEST))
        self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "OK"))
        bad = self.root / "bad.json"
        bad.write_text('{"schema_version": 2}', encoding="utf-8")
        proc = run_cli(VALIDATE_SCRIPT, str(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("FAIL $.schema_version: must equal 1", proc.stdout)

    # --- docs and repo state --------------------------------------------------------

    def test_shipped_library_is_empty_and_fixture_manifest_is_valid(self):
        registry = json.loads((ROOT / "library" / promote.REGISTRY).read_text(encoding="utf-8"))
        self.assertEqual(registry["entries"], [])
        self.assertEqual((ROOT / "library" / promote.RECEIPTS).read_text(encoding="utf-8"), "")
        self.assertEqual(validate_manifest.validate(read_manifest(FIXTURE)), [])

    def test_library_md_and_skill_md_route_promotion_through_promote_py_only(self):
        doc = LIBRARY_MD.read_text(encoding="utf-8")
        for needle in ("scripts/promote.py --candidate", "every task contract", "registry.json", "receipts.jsonl",
                       "never", "Supervisor", "validation.json"):
            self.assertIn(needle, doc)
        skill = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("scripts/promote.py", skill)
        self.assertIn("references/library.md", skill)
        self.assertNotIn("S-10 library, not yet implemented", skill)
        for agent in (ROOT / "agents").glob("*.md"):
            tools = re.search(r"^tools:\s*(.*)$", agent.read_text(encoding="utf-8"), re.M).group(1)
            self.assertNotIn("Bash", tools, agent.name)


if __name__ == "__main__":
    unittest.main()
