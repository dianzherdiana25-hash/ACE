"""Tes korupsi berkas state anggaran brain_bridge (AG15).

Kenapa: ketika berkas state anggaran rusak (terpotong, JSON tidak sah, skema
salah, atau hitungan negatif), bridge wajib mulai dari state bersih dengan
catatan peringatan di log, tidak crash, dan tidak melipatgandakan anggaran
diam-diam (mis. lewat hitungan negatif).
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
        root = Path(d.name)
        self.state = root / "state.json"
        self.log = root / "bridge_calls.jsonl"
        for p in (
            mock.patch.object(bridge, "STATE", self.state),
            mock.patch.object(bridge, "LOG", self.log),
            mock.patch.object(bridge, "_today", return_value=DAY),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _assert_clean_reset_with_warning(self, raw, *, role="front"):
        self.state.write_text(raw, encoding="utf-8")
        if self.log.exists():
            self.log.unlink()
        ok, used = bridge._budget_check(role)
        self.assertTrue(ok)
        self.assertEqual(used, 1)
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"day": DAY, "counts": {role: 1}})
        self.assertTrue(self.log.is_file(), "Log peringatan wajib ditulis saat state rusak.")
        entries = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["level"], "warning")
        self.assertEqual(entries[0]["warning"], "corrupt_budget_state_reset")
        self.assertEqual(entries[0]["role"], role)

    def test_truncated_json_resets_clean_and_logs_warning(self):
        self._assert_clean_reset_with_warning('{"day": "2026-01-18", "counts": {"front": 1')

    def test_invalid_json_resets_clean_and_logs_warning(self):
        self._assert_clean_reset_with_warning("{not valid json")

    def test_empty_file_resets_clean_and_logs_warning(self):
        self._assert_clean_reset_with_warning("")

    def test_wrong_schema_non_dict_root(self):
        self._assert_clean_reset_with_warning("[1, 2, 3]")

    def test_wrong_schema_counts_not_dict(self):
        self._assert_clean_reset_with_warning(json.dumps({"day": DAY, "counts": []}))

    def test_wrong_schema_count_string_or_bool(self):
        self._assert_clean_reset_with_warning(json.dumps({"day": DAY, "counts": {"front": "3"}}))
        self._assert_clean_reset_with_warning(json.dumps({"day": DAY, "counts": {"front": True}}))

    def test_negative_count_does_not_multiply_budget(self):
        with mock.patch.dict(bridge.BUDGETS, {"judge": 2}):
            self._assert_clean_reset_with_warning(
                json.dumps({"day": DAY, "counts": {"judge": -100}}),
                role="judge",
            )
            # Panggilan ke-2 menghabiskan batas (2), panggilan ke-3 ditolak (tidak berlipat menjadi 102)
            self.assertEqual(bridge._budget_check("judge"), (True, 2))
            self.assertEqual(bridge._budget_check("judge"), (False, 2))

    def test_healthy_path_and_rollover_unchanged(self):
        self.assertEqual(bridge._budget_check("front"), (True, 1))
        self.assertEqual(bridge._budget_check("front"), (True, 2))
        self.assertFalse(self.log.exists())
        self.state.write_text(json.dumps({"day": "2025-12-31", "counts": {"judge": 999}}), encoding="utf-8")
        self.assertEqual(bridge._budget_check("judge"), (True, 1))


if __name__ == "__main__":
    unittest.main()
