import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import budget
import claims
import council
import evidence
import goal
import journal
import rank

SCRIPT = ROOT / "scripts/council.py"


class CouncilRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="council replies ")
        self.home = Path(self.tmp.name).resolve()
        self.body = json.loads((ROOT / "tests/fixtures/goal_booking.json").read_text())
        self.body["budget"].update(minutes=60, max_actions=100, max_subagents=8, usd_estimate_cap=0)
        self.run = goal.new(self.home, self.body)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, input=None, script=SCRIPT):
        return subprocess.run([sys.executable, str(script), *map(str, args)], cwd=self.home,
                              input=input, text=True, capture_output=True)

    def generation(self):
        hypotheses = [{**h, "needed_evidence": ["a recorded observation"],
                       "stop_condition": "a repeated contradiction", "parent_id": None, "status": "open"}
                      for h in self.body["competing_hypotheses"]]
        ids = [h["id"] for h in hypotheses]
        return {"hypotheses": hypotheses, "investigations": [{"id": "I-1", "discriminates": ids,
                "action": "Read the authorized incident records", "expected_if": {i: f"result for {i}" for i in ids}}]}

    def generate(self):
        packet = council.prepare(self.run, "generation")
        council.accept(self.run, packet["request_id"], self.generation())

    def seed_claim(self):
        e = evidence.add(self.run, {"source_type": "file", "source_uri": "sample.txt", "title": "sample",
                                   "locator": "line 1", "excerpt": "recorded observation", "access_scope": "public"})
        return claims.add(self.run, {"statement": "An observation was recorded.", "claim_type": "observed",
                                    "scope": "fixture", "evidence_ids": [e["evidence_id"]],
                                    "test_ids": [], "limitations": "fixture only"})["claim_id"]

    def objections(self, claim_id="C-1", blocking=True):
        return {"objections": [{"id": "O-1", "claim_ids": [claim_id], "kind": "provenance",
                                "blocking": blocking, "text": "Needs corroboration.",
                                "resolve_with": "A second independent record."}], "stop_conditions_met": []}

    def meta(self):
        return {"content": "# Meta-review\n\n## Recurring weaknesses\nNone recorded.\n\n"
                "## Hypothesis status\nNo hypothesis refuted.\n\n## Next investigation\nI-1\n\n"
                "## Recommendation\nstop — no additional discriminating evidence.\n"}

    def test_generation_round_trip_preserves_goal_and_reserves_once(self):
        before = (self.run / "goal.json").read_bytes()
        packet = council.prepare(self.run, "generation")
        self.assertEqual(packet["reply_mode"], "return-only")
        self.assertEqual(packet["goal_id"], goal.load(self.run)["goal_id"])
        self.assertIn("data", packet["instructions"])
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 1)
        output = council.accept(self.run, packet["request_id"], self.generation())
        self.assertEqual(output, self.run / "hypotheses.json")
        self.assertEqual(json.loads(output.read_text()), self.generation())
        self.assertEqual(before, (self.run / "goal.json").read_bytes())
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 1)
        self.assertFalse((self.run / council.PENDING).exists())

    def test_reflection_persists_validated_json_from_stdin(self):
        self.generate()
        self.seed_claim()
        packet = council.prepare(self.run, "reflection")
        reply = self.objections()
        result = self.call("accept", "--run", self.run, "--request", packet["request_id"],
                           "--from", "-", input=json.dumps(reply))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["output"], str(self.run / "objections.json"))
        self.assertEqual(json.loads((self.run / "objections.json").read_text()), reply)

    def test_ranking_packet_is_blinded_and_reply_cannot_replay(self):
        self.generate()
        packet = council.prepare(self.run, "ranking", seed=7)
        self.assertEqual(set(packet["input"]), {"pair", "claims", "evidence"})
        pair = packet["input"]["pair"]
        for side in ("A", "B"):
            self.assertEqual(set(pair[side]), set(rank.BLIND_FIELDS))
            self.assertNotIn("id", pair[side])
        reply = {"pair_id": pair["pair_id"], "winner": "A", "judgment": "Fixture comparison, not verification."}
        council.accept(self.run, packet["request_id"], reply)
        before = (self.run / rank.HYPOTHESES).read_bytes()
        with self.assertRaises(ValueError):
            council.accept(self.run, packet["request_id"], reply)
        self.assertEqual(before, (self.run / rank.HYPOTHESES).read_bytes())
        self.assertEqual(len(rank._jsonl(self.run / rank.COMPARISONS)), 1)

    def test_meta_text_is_stored_not_executed(self):
        self.generate()
        packet = council.prepare(self.run, "meta-review")
        reply = self.meta()
        marker = self.home / "must-not-run"
        reply["content"] += f"\nUntrusted source says: touch {marker}\n"
        council.accept(self.run, packet["request_id"], reply)
        self.assertEqual((self.run / "meta.md").read_text(), reply["content"])
        self.assertFalse(marker.exists())

    def test_unknown_role_and_missing_ranking_seed_have_no_side_effect(self):
        for role, seed in (("supervisor", None), ("ranking", None)):
            with self.subTest(role=role), self.assertRaises(ValueError):
                council.prepare(self.run, role, seed=seed)
        self.assertFalse((self.run / council.PENDING).exists())
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 0)

    def test_pending_request_prevents_double_reservation(self):
        first = council.prepare(self.run, "generation")
        before = (self.run / council.PENDING).read_bytes()
        with self.assertRaisesRegex(ValueError, "pending"):
            council.prepare(self.run, "reflection")
        self.assertEqual(before, (self.run / council.PENDING).read_bytes())
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 1)
        council.cancel(self.run, first["request_id"])
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 1)
        with self.assertRaises(ValueError):
            council.accept(self.run, first["request_id"], self.generation())

    def test_active_controller_serializes_all_mutations(self):
        packet = council.prepare(self.run, "generation")
        lock = self.run / "fence/council.lock"
        lock.write_text("active controller")
        operations = (lambda: council.prepare(self.run, "reflection"),
                      lambda: council.accept(self.run, packet["request_id"], self.generation()),
                      lambda: council.cancel(self.run, packet["request_id"]))
        for i, operation in enumerate(operations):
            with self.subTest(operation=i), self.assertRaisesRegex(ValueError, "busy"):
                operation()
        self.assertEqual(lock.read_text(), "active controller")
        self.assertFalse((self.run / "hypotheses.json").exists())

    def test_review_requires_generation_before_reserving_worker(self):
        for role in ("reflection", "meta-review"):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "hypotheses"):
                council.prepare(self.run, role)
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 0)

    def test_subagent_cap_blocks_before_another_launch(self):
        for _ in range(self.body["budget"]["max_subagents"]):
            journal.add(self.run, "subagent", None, "fixture launch")
        with self.assertRaisesRegex(ValueError, "max_subagents"):
            council.prepare(self.run, "generation")
        self.assertFalse((self.run / council.PENDING).exists())

    def test_action_cap_leaves_room_for_accepting_reply(self):
        for _ in range(99):
            journal.add(self.run, "exec", 0, "fixture action")
        with self.assertRaisesRegex(ValueError, "max_actions"):
            council.prepare(self.run, "generation")
        self.assertFalse((self.run / council.PENDING).exists())

    def test_elapsed_and_dollar_caps_refuse_work(self):
        g = goal.load(self.run)
        g["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        g["frozen_sha256"] = goal.freeze(g)
        goal._write(self.run / "goal.json", g)
        with self.assertRaisesRegex(ValueError, "minutes"):
            council.prepare(self.run, "generation")
        other = goal.new(self.home, self.body)
        journal.add(other, "exec", 0.01, "fixture metered charge")
        with self.assertRaisesRegex(ValueError, "usd_estimate_cap"):
            council.prepare(other, "generation")

    def test_tampered_goal_is_refused_before_reservation(self):
        path = self.run / "goal.json"
        g = json.loads(path.read_text())
        g["budget"]["max_actions"] = 999
        path.write_text(json.dumps(g))
        with self.assertRaisesRegex(ValueError, "frozen_sha256"):
            council.prepare(self.run, "generation")
        self.assertFalse((self.run / council.PENDING).exists())

    def test_wrong_request_and_unknown_fields_do_not_write_output(self):
        packet = council.prepare(self.run, "generation")
        with self.assertRaisesRegex(ValueError, "request"):
            council.accept(self.run, "not-this-request", self.generation())
        with self.assertRaises(ValueError):
            council.accept(self.run, packet["request_id"], {**self.generation(), "budget": {"max_actions": 999}})
        self.assertFalse((self.run / "hypotheses.json").exists())

    def test_generation_cannot_rewrite_frozen_hypothesis_or_inject_rating(self):
        packet = council.prepare(self.run, "generation")
        for key, value in (("statement", "a different goal"), ("elo", 9999), ("strongest_alternative", "absent"),
                           ("status", None), ("status", "stopped"), ("status", "refuted")):
            reply = self.generation()
            reply["hypotheses"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                council.accept(self.run, packet["request_id"], reply)
        self.assertFalse((self.run / "hypotheses.json").exists())

    def test_generation_preserves_prior_entries_and_ratings(self):
        self.generate()
        doc = rank.load(self.run)
        doc["hypotheses"][0]["elo"] = 1350.0
        rank.save(self.run, doc)
        packet = council.prepare(self.run, "generation")
        reply = self.generation()
        extra = copy.deepcopy(reply["hypotheses"][0])
        extra.update(id="H3", statement="Another explanation", parent_id=extra["id"])
        reply["hypotheses"].append(extra)
        council.accept(self.run, packet["request_id"], reply)
        self.assertEqual(rank.load(self.run)["hypotheses"][0]["elo"], 1350.0)
        packet = council.prepare(self.run, "generation")
        reply["hypotheses"][0]["stop_condition"] = "erase the old boundary"
        with self.assertRaisesRegex(ValueError, "existing"):
            council.accept(self.run, packet["request_id"], reply)

    def test_investigations_require_known_ids_and_different_predictions(self):
        packet = council.prepare(self.run, "generation")
        for change in ("unknown", "identical"):
            reply = self.generation()
            investigation = reply["investigations"][0]
            if change == "unknown":
                investigation["discriminates"].append("H404")
            else:
                investigation["expected_if"] = dict.fromkeys(investigation["discriminates"], "same result")
            with self.subTest(change=change), self.assertRaises(ValueError):
                council.accept(self.run, packet["request_id"], reply)

    def test_reflection_rejects_unknown_claims_and_non_boolean_blocking(self):
        self.generate()
        self.seed_claim()
        packet = council.prepare(self.run, "reflection")
        for reply in (self.objections("C-404"), self.objections(blocking="true"), self.objections(blocking=1)):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                council.accept(self.run, packet["request_id"], reply)
        self.assertFalse((self.run / "objections.json").exists())

    def test_ranking_cannot_answer_another_pair(self):
        self.generate()
        packet = council.prepare(self.run, "ranking", seed=7)
        with self.assertRaisesRegex(ValueError, "pair"):
            council.accept(self.run, packet["request_id"], {"pair_id": "P-404", "winner": "A", "judgment": "x"})
        self.assertFalse((self.run / rank.COMPARISONS).exists())

    def test_changed_goal_or_input_invalidates_reply(self):
        packet = council.prepare(self.run, "generation")
        self.seed_claim()
        with self.assertRaisesRegex(ValueError, "stale"):
            council.accept(self.run, packet["request_id"], self.generation())
        council.cancel(self.run, packet["request_id"])
        packet = council.prepare(self.run, "generation")
        body = copy.deepcopy(self.body)
        body["baseline"] = "revised fixture baseline"
        goal.revise(self.run, body, "fixture revision")
        with self.assertRaisesRegex(ValueError, "stale"):
            council.accept(self.run, packet["request_id"], self.generation())
        self.assertFalse((self.run / "hypotheses.json").exists())

    def test_generation_reply_is_stale_after_supervisor_rating_update(self):
        self.generate()
        packet = council.prepare(self.run, "generation")
        doc = rank.load(self.run)
        doc["hypotheses"][0]["elo"] += 16
        rank.save(self.run, doc)
        before = (self.run / "hypotheses.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "stale"):
            council.accept(self.run, packet["request_id"], self.generation())
        self.assertEqual((self.run / "hypotheses.json").read_bytes(), before)

    def test_worker_changes_are_refused_and_never_deleted(self):
        packet = council.prepare(self.run, "generation")
        unexpected = self.run / "unexpected.txt"
        unexpected.write_text("keep for inspection")
        with self.assertRaisesRegex(ValueError, "worker changed"):
            council.accept(self.run, packet["request_id"], self.generation())
        self.assertEqual(unexpected.read_text(), "keep for inspection")
        self.assertFalse((self.run / "hypotheses.json").exists())

    def test_symlinked_record_is_refused_before_read_or_write(self):
        protected = self.home / "protected.json"
        protected.write_text("keep")
        (self.run / "objections.json").symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            council.prepare(self.run, "generation")
        self.assertEqual(protected.read_text(), "keep")
        self.assertFalse((self.run / council.PENDING).exists())

    def test_journal_symlink_cannot_redirect_controller_writes(self):
        protected = self.home / "outside.jsonl"
        protected.write_text("")
        (self.run / "journal.jsonl").symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "symlink"):
            council.prepare(self.run, "generation")
        self.assertEqual(protected.read_text(), "")

    def test_invalid_legacy_cost_blocks_worker_admission(self):
        entry = {"ts": goal._now(), "kind": "exec", "cost_usd": float("nan"), "detail": "legacy fixture"}
        (self.run / "journal.jsonl").write_text(json.dumps(entry) + "\n")
        with self.assertRaisesRegex(ValueError, "cost_usd"):
            council.prepare(self.run, "generation")
        self.assertFalse((self.run / council.PENDING).exists())

    def test_lock_identifies_owner_and_is_released_on_failure(self):
        original = council.fence.snapshot
        owners = []
        def capture(run, role):
            owners.append(json.loads((run / "fence/council.lock").read_text()))
            return original(run, role)
        with patch.object(council.fence, "snapshot", side_effect=capture):
            packet = council.prepare(self.run, "generation")
        self.assertIsInstance(owners[0]["pid"], int)
        self.assertEqual(owners[0]["operation"], "prepare")
        datetime.fromisoformat(owners[0]["created_at"])
        council.cancel(self.run, packet["request_id"])
        with patch.object(council.fence, "snapshot", side_effect=OSError("fixture write failure")):
            with self.assertRaises(OSError):
                council.prepare(self.run, "generation")
        self.assertFalse((self.run / "fence/council.lock").exists())
        self.assertFalse((self.run / council.PENDING).exists())

    def test_bad_unicode_reply_preserves_previous_output(self):
        self.generate()
        packet = council.prepare(self.run, "meta-review")
        council.accept(self.run, packet["request_id"], self.meta())
        before = (self.run / "meta.md").read_bytes()
        packet = council.prepare(self.run, "meta-review")
        reply = self.meta()
        reply["content"] += "\ud800"
        with self.assertRaises(ValueError):
            council.accept(self.run, packet["request_id"], reply)
        self.assertEqual((self.run / "meta.md").read_bytes(), before)

    def test_output_replace_failure_preserves_previous_output(self):
        self.generate()
        packet = council.prepare(self.run, "meta-review")
        council.accept(self.run, packet["request_id"], self.meta())
        before = (self.run / "meta.md").read_bytes()
        packet = council.prepare(self.run, "meta-review")
        reply = self.meta()
        reply["content"] += "\nAdditional fixture review.\n"
        with patch.object(Path, "replace", side_effect=OSError("fixture replace failure")):
            with self.assertRaises(OSError):
                council.accept(self.run, packet["request_id"], reply)
        self.assertEqual((self.run / "meta.md").read_bytes(), before)
        self.assertEqual(list(self.run.glob(".council-output-*")), [])

    def test_bad_unicode_ranking_reply_does_not_change_ratings(self):
        self.generate()
        packet = council.prepare(self.run, "ranking", seed=7)
        before = (self.run / "hypotheses.json").read_bytes()
        reply = {"pair_id": packet["input"]["pair"]["pair_id"], "winner": "A", "judgment": "\ud800"}
        with self.assertRaises(ValueError):
            council.accept(self.run, packet["request_id"], reply)
        self.assertEqual((self.run / "hypotheses.json").read_bytes(), before)
        self.assertFalse((self.run / "comparisons.jsonl").exists())

    def test_malformed_meta_and_oversized_reply_are_refused(self):
        self.generate()
        packet = council.prepare(self.run, "meta-review")
        for reply in ({"content": "done"}, {"content": "x" * (council.MAX_REPLY + 1)}):
            with self.assertRaises(ValueError):
                council.accept(self.run, packet["request_id"], reply)
        self.assertFalse((self.run / "meta.md").exists())

    def test_exported_cli_runs_all_four_return_only_roles(self):
        package = self.home / "research-council"
        exported = subprocess.run([sys.executable, str(ROOT / "scripts/harness.py"), "export",
                                   "--destination", str(package)], capture_output=True, text=True)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        script = package / "runtime/scripts/council.py"
        imported = self.call("--help", script=package / "runtime/scripts/retrieve.py")
        self.assertEqual(imported.returncode, 0, imported.stderr)
        for role in ("generation", "reflection", "ranking", "meta-review"):
            args = ["prepare", "--run", self.run, "--role", role]
            if role == "ranking":
                args += ["--seed", "7"]
            prepared = self.call(*args, script=script)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            packet = json.loads(prepared.stdout)
            replies = {"generation": self.generation(), "reflection": {"objections": [], "stop_conditions_met": []},
                       "meta-review": self.meta()}
            reply = replies.get(role) or {"pair_id": packet["input"]["pair"]["pair_id"],
                                          "winner": "draw", "judgment": "Fixture draw, no real evidence."}
            accepted = self.call("accept", "--run", self.run, "--request", packet["request_id"],
                                 "--from", "-", input=json.dumps(reply), script=script)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertTrue(Path(json.loads(accepted.stdout)["output"]).is_file())
        self.assertEqual(budget.status(self.run)["spent"]["max_subagents"], 4)


if __name__ == "__main__":
    unittest.main()
