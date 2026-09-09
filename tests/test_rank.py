import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import goal  # noqa: E402
import rank  # noqa: E402

RANK_SCRIPT = ROOT / "scripts" / "rank.py"
FIXTURE = ROOT / "tests" / "fixtures" / "goal_booking.json"


def hyp(i, **over):
    h = {"id": f"H{i}", "statement": f"statement {i}", "predicted_result": f"result {i}",
         "strongest_alternative": f"H{i % 3 + 1}", "needed_evidence": [f"artifact {i}"],
         "stop_condition": f"stop {i}", "parent_id": None, "status": "open"}
    h.update(over)
    return h


def run_cli(*args):
    return subprocess.run([sys.executable, str(RANK_SCRIPT), *args], capture_output=True, text=True)


class RankTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = goal.new(Path(self.tmp.name), json.loads(FIXTURE.read_text(encoding="utf-8")))
        self.write([hyp(1), hyp(2), hyp(3)])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, hypotheses):
        doc = {"hypotheses": hypotheses, "investigations": [{"id": "I-1", "discriminates": ["H1", "H2"],
               "action": "read log", "expected_if": {"H1": "x", "H2": "y"}}]}
        (self.run / "hypotheses.json").write_text(json.dumps(doc), encoding="utf-8")

    def ratings(self):
        return {h["id"]: h["elo"] for h in rank.load(self.run)["hypotheses"]}

    def play(self, winner_id, loser_id, seed=0):
        """Force a pair between two ids by writing pairs.jsonl directly, then record."""
        pairs = rank._jsonl(self.run / rank.PAIRS)
        pid = f"P-{len(pairs) + 1}"
        with (self.run / rank.PAIRS).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"pair_id": pid, "a": winner_id, "b": loser_id, "seed": seed,
                                 "issued_at": "t"}) + "\n")
        return rank.record(self.run, pid, "A", f"{winner_id} over {loser_id}")

    # pair
    def test_pair_needs_two_open_hypotheses(self):
        self.write([hyp(1), hyp(2, status="refuted")])
        with self.assertRaises(ValueError):
            rank.pair(self.run, 1)
        self.assertFalse((self.run / rank.PAIRS).exists())

    def test_pair_excludes_non_open_hypotheses(self):
        self.write([hyp(1), hyp(2, status="refuted"), hyp(3)])
        out = rank.pair(self.run, 1)
        rec = rank._jsonl(self.run / rank.PAIRS)[0]
        self.assertEqual({rec["a"], rec["b"]}, {"H1", "H3"})
        self.assertEqual(out["pair_id"], "P-1")

    def test_pair_output_is_blinded(self):
        self.write([hyp(1, elo=1300, comparisons=2, author="alice"), hyp(2)])
        out = rank.pair(self.run, 1)
        for side in ("A", "B"):
            self.assertEqual(set(out[side]), set(rank.BLIND_FIELDS))
        self.assertNotIn("H1", json.dumps(out))
        self.assertNotIn("alice", json.dumps(out))

    def test_pair_order_follows_seed_and_both_orders_occur(self):
        orders = set()
        for seed in range(12):
            self.write([hyp(1), hyp(2)])
            (self.run / rank.PAIRS).unlink(missing_ok=True)
            rank.pair(self.run, seed)
            again = rank.pair(self.run, seed)
            recs = rank._jsonl(self.run / rank.PAIRS)
            self.assertEqual((recs[0]["a"], recs[0]["b"]), (recs[1]["a"], recs[1]["b"]))
            orders.add((recs[0]["a"], recs[0]["b"]))
            self.assertEqual(again["pair_id"], "P-2")
        self.assertEqual(orders, {("H1", "H2"), ("H2", "H1")})

    def test_pair_prefers_fewest_comparisons_then_highest_rating(self):
        self.write([hyp(1, elo=1250, comparisons=1), hyp(2, elo=1210, comparisons=1),
                    hyp(3, elo=1190, comparisons=0)])
        first, second = rank.choose(rank.load(self.run), {})
        self.assertEqual((first["id"], second["id"]), ("H3", "H1"))

    def test_pair_prefers_unplayed_then_shared_opponents(self):
        self.write([hyp(1), hyp(2), hyp(3), hyp(4)])
        self.play("H1", "H2")   # H1 and H2 have played; H1's opponent set = {H2}
        self.play("H3", "H2")   # H3 shares opponent H2 with H1
        first, second = rank.choose(rank.load(self.run), rank._opponents(self.run))
        self.assertEqual(first["id"], "H4")  # 0 comparisons
        # H4 has no opponents, so shared=0 for all; unplayed all; highest elo wins: H1/H3 1208 tie -> id
        self.assertEqual(second["id"], "H1")
        self.write([hyp(1, comparisons=1, elo=1208), hyp(2, comparisons=2, elo=1184),
                    hyp(3, comparisons=1, elo=1208), hyp(4, comparisons=1, elo=1200)])
        opp = {"H1": {"H2"}, "H2": {"H1", "H3"}, "H3": {"H2"}, "H4": set()}
        first, second = rank.choose(rank.load(self.run), opp)
        self.assertEqual(first["id"], "H1")   # comparisons 1, highest elo, lowest id
        self.assertEqual(second["id"], "H3")  # unplayed vs H1 and shares H2; beats H4 (no shared)

    # record
    def test_record_a_beats_b_from_1200_gives_1208_and_1192(self):
        out = rank.pair(self.run, 3)
        line = rank.record(self.run, out["pair_id"], "A", "A has evidence")
        r = self.ratings()
        self.assertAlmostEqual(r[line["a"]], 1208)
        self.assertAlmostEqual(r[line["b"]], 1192)
        self.assertEqual(line["winner_id"], line["a"])
        for h in rank.load(self.run)["hypotheses"]:
            if h["id"] in (line["a"], line["b"]):
                self.assertEqual(h["comparisons"], 1)

    def test_record_draw_between_equals_changes_nothing(self):
        out = rank.pair(self.run, 3)
        line = rank.record(self.run, out["pair_id"], "draw", "nothing on file discriminates")
        self.assertIsNone(line["winner_id"])
        self.assertEqual(set(self.ratings().values()), {1200})

    def test_record_appends_comparison_line_and_keeps_investigations(self):
        out = rank.pair(self.run, 3)
        rank.record(self.run, out["pair_id"], "B", "B narrower")
        lines = rank._jsonl(self.run / rank.COMPARISONS)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["pair_id"], out["pair_id"])
        self.assertEqual(lines[0]["judgment"], "B narrower")
        self.assertEqual(lines[0]["elo_before"], [1200, 1200])
        doc = json.loads((self.run / "hypotheses.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["investigations"][0]["id"], "I-1")

    def test_record_refuses_unknown_pair_and_duplicate(self):
        with self.assertRaises(ValueError):
            rank.record(self.run, "P-9", "A", "x")
        out = rank.pair(self.run, 3)
        rank.record(self.run, out["pair_id"], "A", "x")
        with self.assertRaises(ValueError):
            rank.record(self.run, out["pair_id"], "B", "y")
        self.assertEqual(len(rank._jsonl(self.run / rank.COMPARISONS)), 1)
        self.assertAlmostEqual(max(self.ratings().values()), 1208)

    def test_record_requires_judgment(self):
        out = rank.pair(self.run, 3)
        with self.assertRaises(ValueError):
            rank.record(self.run, out["pair_id"], "A", "   ")
        self.assertFalse((self.run / rank.COMPARISONS).exists())

    def test_record_never_changes_status_or_touches_claims(self):
        claims = self.run / "claims.jsonl"
        claims.write_text('{"claim_id": "C-1", "evidence_ids": []}\n', encoding="utf-8")
        out = rank.pair(self.run, 3)
        rank.record(self.run, out["pair_id"], "A", "x")
        self.assertEqual(claims.read_text(encoding="utf-8"), '{"claim_id": "C-1", "evidence_ids": []}\n')
        self.assertEqual({h["status"] for h in rank.load(self.run)["hypotheses"]}, {"open"})
        src = RANK_SCRIPT.read_text(encoding="utf-8")
        code = src.split('"""', 2)[2].lower()  # everything after the module docstring
        for word in ("claims", "verified", "promote", "library"):
            self.assertNotIn(word, code)

    # stop
    def test_stop_sets_status_and_reason_and_keeps_ratings(self):
        self.play("H2", "H1")
        before = self.ratings()
        h = rank.stop(self.run, "H1", "O-11")
        self.assertEqual((h["status"], h["stopped_reason"]), ("stopped", "O-11"))
        doc = rank.load(self.run)
        self.assertEqual(self.ratings(), before)
        self.assertEqual({x["id"]: x["status"] for x in doc["hypotheses"]},
                         {"H1": "stopped", "H2": "open", "H3": "open"})
        self.assertEqual(len(doc["investigations"]), 1)

    def test_pair_never_returns_a_stopped_hypothesis(self):
        rank.stop(self.run, "H1", "O-11")
        for seed in range(6):
            rank.pair(self.run, seed)
        drawn = {x for p in rank._jsonl(self.run / rank.PAIRS) for x in (p["a"], p["b"])}
        self.assertEqual(drawn, {"H2", "H3"})

    def test_table_shows_stopped(self):
        rank.stop(self.run, "H1", "O-11")
        row = [r for r in rank.table(rank.load(self.run)).splitlines() if r.startswith("H1")][0]
        self.assertEqual(row.split()[3], "stopped")

    def test_stop_refuses_unknown_non_open_and_empty_reason_without_writing(self):
        self.write([hyp(1), hyp(2, status="refuted")])
        before = (self.run / "hypotheses.json").read_text(encoding="utf-8")
        for args in (("H9", "O-1"), ("H2", "O-1"), ("H1", " ")):
            with self.assertRaises(ValueError):
                rank.stop(self.run, *args)
        self.assertEqual((self.run / "hypotheses.json").read_text(encoding="utf-8"), before)
        rank.stop(self.run, "H1", "O-1")
        with self.assertRaises(ValueError):  # already stopped
            rank.stop(self.run, "H1", "O-2")

    def test_stop_cli_and_supervisor_only_docs(self):
        r = run_cli("stop", "--run", str(self.run), "--hyp", "H1", "--reason", "O-11")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "H1 stopped: O-11")
        r = run_cli("table", "--run", str(self.run))
        self.assertIn("stopped", r.stdout)
        council = (ROOT / "skills" / "research-council" / "references" / "council.md").read_text(encoding="utf-8")
        stage2 = council.split("**Stage 2")[1].split("**Stage 3")[0]
        self.assertIn("rank.py stop", stage2)
        self.assertLess(stage2.index("Spawn Meta-review"), stage2.index("rank.py stop"))
        meta = (ROOT / "agents" / "meta-review.md").read_text(encoding="utf-8")
        self.assertIn("stop: H1, H4", meta)
        for role in ("generation", "reflection", "ranking", "meta-review"):
            self.assertNotIn("rank.py stop", (ROOT / "agents" / f"{role}.md").read_text(encoding="utf-8"))

    # cycles
    def test_cycles_lists_non_transitive_triple(self):
        self.play("H1", "H2")
        self.play("H2", "H3")
        self.play("H3", "H1")
        self.assertEqual(rank.cycles(self.run), [("H1", "H2", "H3")])

    def test_cycles_empty_when_transitive_or_drawn(self):
        self.play("H1", "H2")
        self.play("H2", "H3")
        self.play("H1", "H3")
        self.assertEqual(rank.cycles(self.run), [])
        out = rank.pair(self.run, 3)
        rank.record(self.run, out["pair_id"], "draw", "tie")
        self.assertEqual(rank.cycles(self.run), [])

    # table
    def test_table_orders_by_rating_with_counts(self):
        self.play("H2", "H1")
        rows = rank.table(rank.load(self.run)).splitlines()
        self.assertTrue(rows[0].startswith("id"))
        self.assertEqual([r.split()[0] for r in rows[1:]], ["H2", "H3", "H1"])
        self.assertEqual(rows[1].split()[1:3], ["1208", "1"])
        self.assertEqual(rows[2].split()[1:3], ["1200", "0"])

    # cli
    def test_cli_round_trip(self):
        r = run_cli("pair", "--run", str(self.run), "--seed", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        r = run_cli("record", "--run", str(self.run), "--pair", out["pair_id"], "--winner", "A",
                    "--judgment", "A has two supporting claims")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1208", r.stdout)
        r = run_cli("cycles", "--run", str(self.run))
        self.assertEqual(r.stdout.strip(), "0 cycle(s)")
        r = run_cli("table", "--run", str(self.run))
        self.assertIn("1192", r.stdout)
        r = run_cli("record", "--run", str(self.run), "--pair", "P-7", "--winner", "A", "--judgment", "x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown pair", r.stderr)


if __name__ == "__main__":
    unittest.main()
