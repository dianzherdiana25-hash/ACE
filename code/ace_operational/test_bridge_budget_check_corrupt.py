"""Tes regresi _budget_check: state governor rusak -> fail-closed, tanpa crash.

Kenapa: sebelum perbaikan, JSON rusak / bukan dict / count bukan int
menjatuhkan handler dengan exception. Jatah tidak boleh ter-reset diam-diam.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from ace_operational import brain_bridge as bridge

DAY = "2026-01-18"


class BudgetCheckCorruptState(unittest.TestCase):
    def setUp(self):
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.state = Path(d.name) / "state.json"
        for p in (mock.patch.object(bridge, "STATE", self.state),
                  mock.patch.object(bridge, "_today", return_value=DAY)):
            p.start()
            self.addCleanup(p.stop)

    def _denied(self, raw):
        self.state.write_text(raw, encoding="utf-8")
        ok, used = bridge._budget_check("front")
        self.assertFalse(ok)
        self.assertEqual(used, bridge.BUDGETS["front"])
        self.assertEqual(self.state.read_text(encoding="utf-8"), raw)

    def test_invalid_json(self):
        self._denied("{not json")

    def test_empty_file(self):
        self._denied("")

    def test_non_dict_root(self):
        self._denied("[1, 2]")

    def test_counts_not_dict(self):
        self._denied(json.dumps({"day": DAY, "counts": []}))

    def test_count_string(self):
        self._denied(json.dumps({"day": DAY, "counts": {"front": "3"}}))

    def test_count_bool(self):
        self._denied(json.dumps({"day": DAY, "counts": {"front": True}}))

    def test_count_negative(self):
        self._denied(json.dumps({"day": DAY, "counts": {"front": -1}}))

    def test_healthy_path_unchanged(self):
        ok, used = bridge._budget_check("front")
        self.assertEqual((ok, used), (True, 1))
        ok, used = bridge._budget_check("front")
        self.assertEqual((ok, used), (True, 2))

    def test_exhausted_and_rollover(self):
        self.state.write_text(json.dumps(
            {"day": DAY, "counts": {"judge": bridge.BUDGETS["judge"]}}))
        self.assertEqual(bridge._budget_check("judge"),
                         (False, bridge.BUDGETS["judge"]))
        self.state.write_text(json.dumps(
            {"day": "2025-12-31", "counts": {"judge": 999}}))
        self.assertEqual(bridge._budget_check("judge"), (True, 1))


if __name__ == "__main__":
    unittest.main()
