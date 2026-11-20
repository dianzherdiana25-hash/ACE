"""Periksa kombinasi panel, masa berlaku bukti, dan batas kepentingan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import expert_panel as panel


def expert(identifier, org, cost, topics, *, conflicts=None, expiry="2026-11-21"):
    return {"id": identifier, "organization": org, "cost_units": cost,
            "conflict_topics": conflicts or [],
            "credentials": [{"topic": topic, "score": score, "source_ref": f"fixture/{identifier}/{topic}",
                             "valid_from": "2026-11-01", "expires_on": expiry} for topic, score in topics]}


def fixture():
    return {"request": {"as_of": "2026-11-20", "topics": {"audit": 1, "stats": 1},
                        "max_size": 2, "max_cost_units": 8, "min_organizations": 2, "excluded_orgs": []},
            "candidates": [
                expert("a", "org1", 5, [("audit", 99)]),
                expert("b", "org1", 4, [("stats", 98)]),
                expert("c", "org2", 4, [("audit", 85), ("stats", 81)]),
                expert("d", "org3", 5, [("stats", 100)], conflicts=["stats"]),
                expert("e", "org3", 1, [("stats", 100)], expiry="2026-11-20"),
            ]}


class PanelTests(unittest.TestCase):
    def test_joint_constraints_beat_independent_best_per_topic(self):
        raw = fixture()
        result = panel.form_panel(raw)
        self.assertEqual(result["status"], "selected")
        self.assertEqual([member["id"] for member in result["members"]], ["b", "c"])
        self.assertEqual(result["organizations"], ["org1", "org2"])
        self.assertEqual(result["quality"], 183)
        self.assertEqual(result["cost_units"], 8)
        self.assertEqual(result["coverage"], {"audit": 1, "stats": 2})
        self.assertEqual(result["members"][0]["topic_evidence"][0]["source_ref"], "fixture/b/stats")
        self.assertEqual(result["excluded"], [
            {"id": "d", "reasons": ["conflicting_topic"], "conflicting_topics": ["stats"]},
            {"id": "e", "reasons": ["no_current_credential"], "conflicting_topics": []},
        ])

    def test_organization_exclusion_is_computed_before_search(self):
        raw = fixture()
        raw["request"]["excluded_orgs"] = ["org2"]
        result = panel.form_panel(raw)
        self.assertEqual(result["status"], "infeasible")
        self.assertEqual(result["members"], [])
        by_id = {row["id"]: row["reasons"] for row in result["excluded"]}
        self.assertEqual(by_id["c"], ["organization_excluded"])

    def test_prefer_lower_cost_then_id_when_both_qualify_equally(self):
        raw = fixture()
        raw["request"]["min_organizations"] = 1
        raw["candidates"] = [
            expert("first-in", "org", 5, [("audit", 50), ("stats", 50)]),
            expert("z", "org", 4, [("audit", 50), ("stats", 50)]),
            expert("a", "org", 4, [("audit", 50), ("stats", 50)]),
        ]
        self.assertEqual([row["id"] for row in panel.form_panel(raw)["members"]], ["a"])
        raw["candidates"].reverse()
        self.assertEqual([row["id"] for row in panel.form_panel(raw)["members"]], ["a"])

    def test_infeasible_second_expert_reports_no_partial_panel(self):
        raw = fixture()
        raw["request"]["topics"]["audit"] = 2
        result = panel.form_panel(raw)
        self.assertEqual(result["coverage"], {"audit": 0, "stats": 0})
        self.assertIsNone(result["quality"])

    def test_rejects_duplicate_or_future_invalid_credential_and_policy_booleans(self):
        raw = fixture()
        dupe = {**raw["candidates"][0], "id": "other"}
        for patch in ({"candidates": [raw["candidates"][0], dupe]},
                      {"candidates": [expert("x", "org", 1, [("audit", 1)], expiry="2026-11-01")]},
                      {"request": {**raw["request"], "max_size": True}}):
            with self.subTest(patch=patch), self.assertRaises(panel.PanelError):
                panel.form_panel({**raw, **patch})

    def test_cli_explicitly_marks_infeasibility(self):
        raw = fixture()
        raw["request"]["max_cost_units"] = 1
        path = Path(self.enterContext(TemporaryDirectory())) / "panel.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(panel.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "infeasible")
