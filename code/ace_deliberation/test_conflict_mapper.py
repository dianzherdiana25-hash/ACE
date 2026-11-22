"""Periksa rujukan kepentingan, siklus, rentang waktu, dan tumpang tindih posisi."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import conflict_mapper


def edge(source, target, *, topic=None, relation="member_of", start="2026-11-01", until=None):
    return {"source": source, "target": target, "topic": topic, "relation": relation,
            "valid_from": start, "valid_until": until, "source_ref": f"fixture/{source}/{target}"}


def position(identity, people, gainers, *, topic="budget"):
    return {"id": identity, "topic": topic, "advocates": people, "beneficiaries": gainers,
            "source_ref": f"fixture/{identity}"}


def fixture():
    return {
        "as_of": "2026-11-20", "actors": ["op1", "op2", "affiliate", "beneficiary"], "max_depth": 3,
        "links": [edge("op1", "affiliate"), edge("affiliate", "op1", relation="controls"),
                  edge("affiliate", "beneficiary", topic="budget", relation="holds_interest"),
                  edge("op2", "beneficiary", until="2026-11-20")],
        "positions": [position("one", ["op1", "op2"], ["beneficiary"]),
                      position("two", ["op2"], ["beneficiary", "op2"]),
                      position("three", ["op1"], ["beneficiary"], topic="other")],
        "oppositions": [{"left": "two", "right": "one", "source_ref": "fixture/opposition"}],
    }


class ConflictTests(unittest.TestCase):
    def test_captures_indirect_interest_with_observed_provenance(self):
        report = conflict_mapper.map_conflicts(fixture())
        a, c, b = report["positions"]
        self.assertEqual(a["id"], "one")
        linked, = a["interest_witnesses"]
        self.assertEqual((linked["advocate"], linked["beneficiary"], linked["kind"]),
                         ("op1", "beneficiary", "linked"))
        self.assertEqual([hop["source_ref"] for hop in linked["path"]],
                         ["fixture/op1/affiliate", "fixture/affiliate/beneficiary"])
        self.assertEqual(b["interest_witnesses"],
                         [{"advocate": "op2", "beneficiary": "op2", "kind": "direct", "path": []}])
        self.assertEqual(c["interest_witnesses"], [])

    def test_opposed_positions_share_actor_and_beneficiary_without_verdict(self):
        row, = conflict_mapper.map_conflicts(fixture())["oppositions"]
        self.assertEqual(row, {"left": "one", "right": "two", "source_ref": "fixture/opposition",
                               "shared_advocates": ["op2"], "shared_beneficiaries": ["beneficiary"]})

    def test_depth_limit_and_date_cutoff_have_separate_effects(self):
        raw = fixture()
        raw["max_depth"] = 1
        self.assertEqual(conflict_mapper.map_conflicts(raw)["positions"][0]["interest_witnesses"], [])
        raw["as_of"] = "2026-11-19"
        self.assertEqual(conflict_mapper.map_conflicts(raw)["positions"][0]["interest_witnesses"][0]["advocate"],
                         "op2")

    def test_stable_order_for_positions_relations_and_normalized_opposition(self):
        raw = fixture()
        expected = conflict_mapper.map_conflicts(raw)
        for key in ("actors", "links", "positions"):
            raw[key].reverse()
        raw["oppositions"][0].update(left="one", right="two")
        self.assertEqual(conflict_mapper.map_conflicts(raw), expected)

    def test_rejects_cross_topic_opposition_duplicate_ref_or_unlisted_actor(self):
        for patch in ("cross_topic", "duplicate", "actor"):
            raw = fixture()
            if patch == "cross_topic":
                raw["oppositions"][0]["left"] = "three"
            elif patch == "duplicate":
                raw["links"].append(raw["links"][0])
            else:
                raw["positions"][0]["advocates"].append("unknown")
            with self.subTest(patch=patch), self.assertRaises(conflict_mapper.ConflictError):
                conflict_mapper.map_conflicts(raw)

    def test_cli_reproduces_trace(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "positions.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(conflict_mapper.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), conflict_mapper.map_conflicts(raw))

    def test_witness_chooses_shortest_path_and_stable_ref_at_equal_length(self):
        raw = fixture()
        direct = edge("op1", "beneficiary", relation="consults_for")
        raw["links"].extend([direct, {**direct, "source_ref": "fixture/aaa"}])
        witness, = conflict_mapper.map_conflicts(raw)["positions"][0]["interest_witnesses"]
        self.assertEqual(len(witness["path"]), 1)
        self.assertEqual(witness["path"][0]["source_ref"], "fixture/aaa")

    def test_future_links_and_direction_do_not_create_backdated_paths(self):
        raw = fixture()
        raw["links"] = [
            edge("op1", "beneficiary", start="2026-11-21"),
            edge("beneficiary", "op1"),
        ]
        self.assertEqual(conflict_mapper.map_conflicts(raw)["positions"][0]["interest_witnesses"], [])

    def test_duplicate_oppositions_are_rejected_even_if_reversed(self):
        raw = fixture()
        raw["oppositions"].append({"left": "one", "right": "two", "source_ref": "fixture/other"})
        with self.assertRaisesRegex(conflict_mapper.ConflictError, "Oposisi ganda"):
            conflict_mapper.map_conflicts(raw)
