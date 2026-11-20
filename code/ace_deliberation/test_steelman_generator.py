"""Periksa jalur terkuat, batas keluarga sumber, dan penolakan bukti palsu."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import steelman_generator as steelman
from ace_deliberation.test_argument_graph import edge, node


def fixture():
    links = [
        ("s1", "A", "supports", "0.2"), ("s1", "hop", "supports", "0.8"),
        ("hop", "A", "supports", "0.6"), ("A", "hop", "supports", "0.9"),
        ("s2", "A", "supports", "0.4"), ("s3", "A", "supports", "0.4"),
        ("s3", "B", "supports", "0.9"), ("A", "P", "attacks", "0.7"),
        ("B", "P", "attacks", "0.8"), ("C", "P", "attacks", "1"),
    ]
    return {
        "target_claim": "P", "max_families": 2,
        "graph": {"nodes": [node(k) for k in ("P", "A", "B", "C", "hop")]
                           + [node(k, "evidence") for k in ("s1", "s2", "s3")],
                  "edges": [edge(start, end, kind) for start, end, kind, _ in links]},
        "strengths": [{"source": start, "target": end, "relation": kind, "strength": weight}
                      for start, end, kind, weight in links],
        "sources": [{"id": identifier, "family": family, "reliability": 1}
                    for identifier, family in (("s1", "joint"), ("s2", "joint"), ("s3", "independent"))],
    }


class SteelmanTests(unittest.TestCase):
    def test_uses_longer_stronger_path_and_independent_family(self):
        report = steelman.reconstruct(fixture())
        self.assertEqual(report["best_supported_opposition"], "A")
        a, b, c = report["alternatives"]
        self.assertEqual(a["score"], {"numerator": 1, "denominator": 1})
        self.assertEqual([note["node"]["id"] for note in a["evidence"]], ["s1", "s3"])
        path = a["evidence"][0]["support_path"]
        self.assertEqual([(link["source"], link["target"]) for link in path], [("s1", "hop"), ("hop", "A")])
        self.assertEqual(path[0]["source_ref"], "fixture/review")
        self.assertEqual(b["evidence"][0]["strength"], {"numerator": 4, "denominator": 5})
        self.assertEqual(c["evidence"], [])
        self.assertEqual(c["position"]["source_ref"], "fixture/C")

    def test_limit_changes_best_opposition_without_inventing_evidence(self):
        report = steelman.reconstruct({**fixture(), "max_families": 1})
        self.assertEqual(report["best_supported_opposition"], "B")
        self.assertEqual(len(report["alternatives"][0]["evidence"]), 1)

    def test_source_reliability_caps_path_and_breaks_tie_by_shortest_route(self):
        raw = fixture()
        raw["sources"][0]["reliability"] = "0.2"
        raw["strengths"][4]["strength"] = "0.1"
        a = next(row for row in steelman.reconstruct(raw)["alternatives"] if row["position"]["id"] == "A")
        s1 = next(row for row in a["evidence"] if row["node"]["id"] == "s1")
        self.assertEqual(s1["support_path"], [edge("s1", "A")])

    def test_no_supported_opposition_is_visible(self):
        raw = fixture()
        for source in raw["sources"]:
            source["reliability"] = 0
        report = steelman.reconstruct(raw)
        self.assertIsNone(report["best_supported_opposition"])
        self.assertEqual(report["status"], "no_supported_opposition")
        self.assertEqual(len(report["alternatives"]), 3)

    def test_reordering_independent_inputs_changes_no_byte_of_report(self):
        raw = fixture()
        original = steelman.reconstruct(raw)
        for key in ("nodes", "edges"):
            raw["graph"][key].reverse()
        raw["strengths"].reverse()
        raw["sources"].reverse()
        self.assertEqual(steelman.reconstruct(raw), original)

    def test_rejects_missing_weight_wrong_target_and_duplicate_catalog(self):
        raw = fixture()
        cases = [
            {"strengths": raw["strengths"][:-1]}, {"target_claim": "s1"}, {"max_families": True},
            {"sources": [raw["sources"][0]] * 3},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(steelman.SteelmanError):
                steelman.reconstruct({**raw, **changes})

    def test_cli_reads_graph_and_reports_claim_with_provenance(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "graph.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(steelman.main([str(path)]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["target"]["source_ref"], "fixture/P")
        self.assertEqual(result["alternatives"][0]["attack"]["relation"], "attacks")

    def test_attack_with_zero_strength_keeps_candidate_visible_without_support(self):
        raw = fixture()
        row = next(row for row in raw["strengths"] if row["source"] == "A" and row["relation"] == "attacks")
        row["strength"] = 0
        report = steelman.reconstruct(raw)
        self.assertEqual(report["best_supported_opposition"], "B")
        a = next(item for item in report["alternatives"] if item["position"]["id"] == "A")
        self.assertEqual(a["score"], {"numerator": 0, "denominator": 1})
        self.assertEqual(a["evidence"], [])
