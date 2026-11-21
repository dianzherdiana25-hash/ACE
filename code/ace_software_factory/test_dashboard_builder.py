"""Verifier agregasi waktu, data kosong, dan skala meter yang sama."""
import unittest

from ace_software_factory import dashboard_builder
from ace_software_factory._contracts import ContractError, identity


def label(key, title):
    return {"id": key, "label": title, "source_ref": "fixture/" + key}


def row(key, group, recorded, value):
    return {"id": key, "date": recorded, "metric": "units", "group": group,
            "value": value, "source_ref": "fixture/input/" + key}


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.data = {"schema": "ace.factory-dashboard-snapshot.v1", "source_ref": "fixture/sheet",
                     "observations": [row("e0", "north", "2026-01-01", 2), row("e1", "north", "2026-01-31", 7),
                                      row("e2", "north", "2025-12-31", 4), row("e3", "south", "2026-01-03", 0),
                                      row("outside", "south", "2026-02-01", 99)]}
        self.plan = {"schema": "ace.factory-dashboard-plan.v1", "title": "Kuantitas <alur>",
                     "target": {"start": "2026-01-01", "end": "2026-01-31"},
                     "baseline": {"start": "2025-12-01", "end": "2025-12-31"},
                     "metrics": [label("units", "Unit")], "groups": [label("north", "Utara"), label("south", "Selatan")]}

    def build(self):
        self.plan["snapshot_sha256"] = identity(self.data)
        return dashboard_builder.build(self.plan, self.data, identity(self.plan))

    def test_sum_exact_delta_missing_and_zero_have_different_values(self):
        files, report = self.build()
        item = report["metrics"][0]
        north, south = item["groups"]
        self.assertEqual((north["target"], north["baseline"], north["delta"]), (9, 4, 5))
        self.assertEqual((south["target"], south["baseline"], south["delta"]), (0, None, None))
        self.assertEqual(item["scale"], 9)
        self.assertEqual(north["evidence"]["target"][0]["source_ref"], "fixture/input/e0")
        html = files["index.html"].decode()
        self.assertEqual(html.count("max='9'"), 2)
        self.assertIn("TIDAK TAHU", html)
        self.assertIn("Kuantitas &lt;alur&gt;", html)

    def test_overlapping_periods_and_repeated_events_are_rejected(self):
        self.plan["baseline"]["end"] = "2026-01-01"
        with self.assertRaisesRegex(ContractError, "sebelum"):
            self.build()
        self.plan["baseline"]["end"] = "2025-12-31"
        self.data["observations"].append(self.data["observations"][0])
        with self.assertRaisesRegex(ContractError, "ganda"):
            self.build()
