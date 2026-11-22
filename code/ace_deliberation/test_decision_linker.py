"""Uji revisi yang melewati ambang, rujukan lama, dan dampak lintas putusan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import decision_linker as linked


def forecast(reference, p, hour, question="q1", expires="2026-11-22T00:00:00Z"):
    return {"question_id": question, "forecast_ref": reference,
            "forecast_at": f"2026-11-20T{hour}:00:00Z", "expires_at": expires, "probability": p}


def decision(identifier, source, comparison, threshold, hour="08"):
    return {"id": identifier, "source_ref": f"fixture/decision/{identifier}", "decided_at": f"2026-11-20T{hour}:00:00Z",
            "dependencies": [{"forecast_ref": source, "comparison": comparison, "threshold": threshold}]}


def fixture():
    return {
        "as_of": "2026-11-20T13:00:00Z",
        "forecasts": [forecast("fixture/old", "0.8", "07"), forecast("fixture/new", "0.4", "12"),
                      forecast("fixture/other", "0.1", "07", question="q2")],
        "decisions": [decision("other", "fixture/other", "at_most", "0.2"),
                      decision("wait", "fixture/old", "at_least", "0.3"),
                      decision("adopt", "fixture/old", "at_least", "0.6")],
    }


class LinksTests(unittest.TestCase):
    def test_one_revision_can_cross_one_decision_threshold_but_not_another(self):
        report = linked.assess_links(fixture())
        adoption, other, wait = report["decisions"]
        self.assertEqual(adoption["status"], "review_required")
        self.assertEqual(adoption["links"][0]["status"], "threshold_crossed")
        self.assertEqual(adoption["links"][0]["current_forecast"]["forecast_ref"], "fixture/new")
        self.assertEqual(wait["links"][0]["status"], "updated_same_side")
        self.assertEqual(other["links"][0]["status"], "current")
        self.assertEqual(report["affected_by_forecast"], {"q1": ["adopt", "wait"], "q2": ["other"]})

    def test_dangling_citation_is_written_with_no_fabricated_probability(self):
        raw = fixture()
        raw["decisions"].append(decision("absent", "fixture/dangling", "at_most", "0.5"))
        row = linked.assess_links(raw)["decisions"][0]["links"][0]
        self.assertEqual(row["status"], "dangling_reference")
        self.assertIsNone(row["cited_forecast"])
        self.assertIsNone(row["current_forecast"])

    def test_future_expired_and_originally_unsupported_remain_different_faults(self):
        raw = fixture()
        raw["decisions"] = [decision("future", "fixture/new", "at_least", "0.3"),
                            decision("bad", "fixture/old", "at_most", "0.7"),
                            decision("expired", "fixture/other", "at_least", "0.1")]
        raw["forecasts"][-1]["expires_at"] = "2026-11-20T08:00:00Z"
        by_id = {row["id"]: row["links"][0]["status"] for row in linked.assess_links(raw)["decisions"]}
        self.assertEqual(by_id, {"future": "forecast_after_decision",
                                 "bad": "unsupported_at_decision", "expired": "expired_at_decision"})

    def test_latest_expiry_never_falls_back_to_retired_revision(self):
        raw = fixture()
        raw["forecasts"][1]["expires_at"] = raw["as_of"]
        rows = {row["id"]: row for row in linked.assess_links(raw)["decisions"]}
        self.assertEqual(rows["wait"]["links"][0]["status"], "forecast_expired")
        self.assertEqual(rows["wait"]["links"][0]["current_forecast"]["forecast_ref"], "fixture/new")

    def test_duplicate_instants_and_future_catalog_records_fail_closed(self):
        raw = fixture()
        for item in (forecast("different-ref", "0.2", "12"), forecast("future", "0.2", "14")):
            with self.subTest(item=item), self.assertRaises(linked.LinkError):
                linked.assess_links({**raw, "forecasts": [*raw["forecasts"], item]})

    def test_cli_exit_for_review_and_canonical_stability(self):
        raw = fixture()
        expected = linked.assess_links(raw)
        raw["forecasts"].reverse()
        raw["decisions"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "decisions.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(linked.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_obsolete_at_decision_is_not_treated_as_a_later_threshold_crossing(self):
        raw = fixture()
        raw["decisions"] = [decision("later", "fixture/old", "at_least", "0.3", hour="12")]
        row = linked.assess_links(raw)["decisions"][0]["links"][0]
        self.assertEqual(row["status"], "superseded_at_decision")
        self.assertEqual(row["latest_at_decision"]["forecast_ref"], "fixture/new")
        self.assertTrue(row["needs_review"])

    def test_all_predicates_on_distinct_questions_remain_visible(self):
        raw = fixture()
        selected = raw["decisions"][-1]
        selected["dependencies"].append({"forecast_ref": "fixture/other", "comparison": "at_most", "threshold": "0.2"})
        report = linked.assess_links({**raw, "decisions": [selected]})
        checked, = report["decisions"]
        self.assertEqual(checked["status"], "review_required")
        self.assertEqual([row["status"] for row in checked["links"]], ["threshold_crossed", "current"])
        self.assertEqual(report["affected_by_forecast"], {"q1": ["adopt"], "q2": ["adopt"]})

    def test_comparison_includes_exact_threshold_and_duplicate_link_is_rejected(self):
        raw = fixture()
        only = decision("threshold", "fixture/other", "at_most", "0.1")
        result = linked.assess_links({**raw, "decisions": [only]})
        self.assertEqual(result["decisions"][0]["status"], "supported")
        only["dependencies"] *= 2
        with self.assertRaises(linked.LinkError):
            linked.assess_links({**raw, "decisions": [only]})

    def test_forecast_risk_changes_leave_source_decision_intact(self):
        raw = fixture()
        before = json.dumps(raw, sort_keys=True)
        linked.assess_links(raw)
        self.assertEqual(json.dumps(raw, sort_keys=True), before)
