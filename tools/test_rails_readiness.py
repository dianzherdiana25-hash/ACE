"""Tes regresi fixture-only untuk tools.rails_readiness (AG54)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import rails_readiness


class RailsReadinessTest(unittest.TestCase):
    def test_staleness_threshold_flags_past_boundary_for_four_rails(self) -> None:
        rails = rails_readiness.default_fixture_rails()
        # Fixture default verified_date=2026-11-01.
        # Jadikan qris lebih tua agar stale pada as_of=2026-11-20 dengan max_age_days=30,
        # sementara seabank tepat pada batas 30 hari (2026-10-21) tetap fresh.
        for rail in rails:
            if rail["rail_id"] == "seabank":
                rail["verified_date"] = "2026-10-21"  # 30 hari sebelum 2026-11-20 -> tepat batas (fresh)
            elif rail["rail_id"] == "qris":
                rail["verified_date"] = "2026-10-20"  # 31 hari sebelum 2026-11-20 -> STALE!
            elif rail["rail_id"] == "gopay":
                rail["verified_date"] = ""  # unverified -> stale=True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rails_file = root / "rails.json"
            out_json = root / "readiness.json"
            out_md = root / "readiness.md"
            rails_file.write_text(json.dumps(rails), encoding="utf-8")

            rc = rails_readiness.main(
                [
                    "--rails",
                    str(rails_file),
                    "--as-of",
                    "2026-11-20",
                    "--max-age-days",
                    "30",
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            md = out_md.read_text(encoding="utf-8")

        self.assertEqual(rep["schema"], rails_readiness.SCHEMA)
        self.assertEqual(rep["summary"]["total_rails"], 4)
        self.assertEqual(rep["summary"]["missing_expected_rails"], [])
        self.assertEqual(rep["summary"]["stale_rails"], ["gopay", "qris"])
        self.assertFalse(rep["summary"]["all_ready"])

        by_id = {r["rail_id"]: r for r in rep["rails"]}
        self.assertEqual(by_id["kbm"]["staleness_status"], "fresh")
        self.assertFalse(by_id["kbm"]["stale"])
        self.assertTrue(by_id["kbm"]["ready"])

        self.assertEqual(by_id["seabank"]["age_days"], 30)
        self.assertEqual(by_id["seabank"]["staleness_status"], "fresh")
        self.assertFalse(by_id["seabank"]["stale"])

        self.assertEqual(by_id["qris"]["age_days"], 31)
        self.assertEqual(by_id["qris"]["staleness_status"], "stale")
        self.assertTrue(by_id["qris"]["stale"])
        self.assertFalse(by_id["qris"]["ready"])

        self.assertEqual(by_id["gopay"]["staleness_status"], "unverified")
        self.assertTrue(by_id["gopay"]["stale"])

        self.assertIn("# Checklist Kesiapan Rel Pembayaran", md)
        self.assertIn("| qris | QRIS Merchant | 2026-10-20 | 31 | stale | True | False |", md)

    def test_rejects_raw_account_numbers_in_fixture(self) -> None:
        rails = rails_readiness.default_fixture_rails()
        rails[1]["requirements"].append("Kirim ke rekening 901234567890")
        with self.assertRaises(ValueError):
            rails_readiness.evaluate_rails_readiness(rails, as_of="2026-11-20", max_age_days=30)


if __name__ == "__main__":
    unittest.main()
