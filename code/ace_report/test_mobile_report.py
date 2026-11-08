"""Tests for Indonesian mobile report generator (W5 / FR-09 / FR-14)."""
from __future__ import annotations

import unittest
from ace_report.mobile_report import generate_indonesian_mobile_report


class TestMobileReport(unittest.TestCase):
    def test_report_generation_structure(self):
        sample_data = {
            "scientific_claim_status": "CONFIRMED_SEALED",
            "graph_results": {
                "A": {"mean": 0.925},
                "B": {"mean": 0.858},
                "C": {"mean": 1.000},
            },
            "ratio4_results": {
                "A": {"mean": 0.774},
                "B": {"mean": 0.890},
                "C": {"mean": 1.000},
            },
            "hypotheses_evaluation": {
                "H_graph": "CONFIRMED",
                "H_ratio4": "CONFIRMED",
            },
        }

        report = generate_indonesian_mobile_report(sample_data)
        self.assertIn("# 📱 Laporan Hasil Riset ACE", report)
        self.assertIn("Rp0 ($0.00)", report)
        self.assertIn("CONFIRMED_SEALED", report)
        self.assertIn("100.0%", report)
        self.assertIn("CONFIRMED", report)
        self.assertIn("bukan bukti kemunculan AGI atau OAIE umum", report)


if __name__ == "__main__":
    unittest.main()
