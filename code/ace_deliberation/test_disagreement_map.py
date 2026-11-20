"""Uji penyebut per pasangan, data kosong, rujukan, dan SVG yang sah."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree

from ace_deliberation import disagreement_map as disagreement


def row(person, issue, stance):
    return {"participant": person, "issue": issue, "stance": stance,
            "source_ref": f"fixture/{person}/{issue}"}


def fixture():
    return {"participants": ["c", "a", "b"],
            "issues": [{"id": "major", "weight": 4, "source_ref": "fixture/major"},
                       {"id": "minor", "weight": 1, "source_ref": "fixture/minor"}],
            "positions": [row("a", "major", "for"), row("a", "minor", "for"),
                          row("b", "major", "against"), row("b", "minor", "for"),
                          row("c", "major", "abstain")]}


class DisagreementTests(unittest.TestCase):
    def test_weighted_distance_keeps_actual_paired_sources(self):
        report = disagreement.compare(fixture())
        pair = report["pairs"][0]
        self.assertEqual(pair["distance"], {"numerator": 4, "denominator": 5})
        self.assertEqual(pair["compared_weight"], 5)
        self.assertEqual(pair["difference_sources"], [{
            "issue": "major", "issue_ref": "fixture/major",
            "left_ref": "fixture/a/major", "right_ref": "fixture/b/major",
        }])
        self.assertEqual(report["highest_disagreement"], [["a", "b"]])

    def test_missing_and_abstained_have_no_fabricated_distance(self):
        report = disagreement.compare(fixture())
        pair = report["pairs"][1]
        self.assertIsNone(pair["distance"])
        self.assertEqual(pair["missing_issues"], ["minor"])
        self.assertEqual(pair["abstained_issues"], ["major"])
        self.assertEqual(pair["compared_weight"], 0)

    def test_identical_opinions_are_zero_and_do_not_make_highest_nonempty(self):
        raw = fixture()
        raw["positions"][2]["stance"] = "for"
        report = disagreement.compare(raw)
        self.assertEqual(report["pairs"][0]["distance"], {"numerator": 0, "denominator": 1})
        self.assertEqual(report["highest_disagreement"], [])
        self.assertIn("0%", disagreement.render_svg(report))

    def test_graph_has_a_square_matrix_and_rendered_missing_markers(self):
        graphic = disagreement.render_svg(disagreement.compare(fixture()))
        doc = ElementTree.fromstring(graphic)
        self.assertEqual(len(doc.findall("{*}rect")), 10)
        labels = [item.text for item in doc.findall("{*}text")]
        self.assertEqual(labels.count("80%"), 2)
        self.assertEqual(labels.count("?"), 4)
        self.assertEqual(labels.count("–"), 3)

    def test_xml_escapes_labels_without_suppressing_original_identity(self):
        raw = {"participants": ["a<b>", "p & q"], "issues": fixture()["issues"], "positions": []}
        doc = ElementTree.fromstring(disagreement.render_svg(disagreement.compare(raw)))
        labels = [item.text for item in doc.findall(".//{*}title")]
        self.assertIn("a<b>", labels)
        self.assertIn("p & q", labels)

    def test_invalid_position_and_weight_are_rejected(self):
        raw = fixture()
        for overwrite in ({"positions": [*raw["positions"], row("a", "major", "against")]},
                          {"positions": [row("unknown", "major", "for")]},
                          {"issues": [{**raw["issues"][0], "weight": True}]}):
            with self.subTest(overwrite=overwrite), self.assertRaises(disagreement.MapError):
                disagreement.compare({**raw, **overwrite})

    def test_stable_under_reordering_and_cli_svg_matches_api(self):
        raw = fixture()
        target = disagreement.render_svg(disagreement.compare(raw))
        for key in raw:
            raw[key].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "positions.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(disagreement.main([str(path), "--format", "svg"]), 0)
        self.assertEqual(output.getvalue(), target)

    def test_issue_profiles_report_missing_separately_from_absent_opposition(self):
        report = disagreement.compare(fixture())
        major, minor = report["issue_profiles"]
        self.assertEqual(major, {"id": "major", "weight": 4, "source_ref": "fixture/major", "opposing_pairs": 1,
                                 "stances": {"for": 1, "against": 1, "abstain": 1, "missing": 0}})
        self.assertEqual(minor["opposing_pairs"], 0)
        self.assertEqual(minor["stances"], {"for": 2, "against": 0, "abstain": 0, "missing": 1})

    def test_red_maximum_and_overlapping_coverage_can_be_tied(self):
        raw = fixture()
        raw["positions"] = [row("a", "major", "for"), row("b", "major", "against"),
                            row("c", "major", "for")]
        report = disagreement.compare(raw)
        self.assertEqual(report["highest_disagreement"], [["a", "b"], ["b", "c"]])
        self.assertEqual(report["issue_profiles"][0]["opposing_pairs"], 2)
        svg = disagreement.render_svg(report)
        self.assertIn("#e4e8ef", svg)
        self.assertIn("100%", svg)

    def test_empty_opinions_are_reported_without_presumed_agreement(self):
        raw = {**fixture(), "positions": []}
        report = disagreement.compare(raw)
        self.assertTrue(all(row["distance"] is None for row in report["pairs"]))
        self.assertEqual(report["issue_profiles"][0]["stances"]["missing"], 3)

    def test_invalid_xml_controls_in_participant_labels_are_refused(self):
        raw = {**fixture(), "participants": ["normal", "unsafe\x01label"], "positions": []}
        with self.assertRaises(disagreement.MapError):
            disagreement.compare(raw)
