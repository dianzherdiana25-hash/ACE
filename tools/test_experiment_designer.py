"""Tes unit untuk tools/experiment_designer.py (AG95)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.experiment_designer import (
    BATCH_SCHEMA,
    SCHEMA,
    design_batch,
    design_smallest_falsifying_experiment,
    main,
)


class ExperimentDesignerTests(unittest.TestCase):
    def test_three_hypotheses_yield_three_distinct_experiment_designs(self) -> None:
        hypotheses = [
            # 1. Dapat dibuktikan lewat replay trace historis read-only -> replay_audit
            {
                "hypothesis_id": "hyp-history-replay",
                "domain": "recall",
                "risk_level": "low",
                "historical_trace_available": True,
                "evidence_source": "heldout_trace",
                "compares_variants": False,
                "confidence": 0.75,
                "measurable_prediction": "Kasus 0-record muncul pada kueri bertetangga >= 5 kali",
                "falsification_criteria": "Semua 20 jejak historis sudah mengirim >= 1 tetangga",
            },
            # 2. Masalah fail-over / isolasi eksekusi berisiko tinggi -> fixture_arena
            {
                "hypothesis_id": "hyp-failover-race",
                "domain": "bridge",
                "risk_level": "high",
                "requires_synthetic_execution": True,
                "confidence": 0.65,
                "measurable_prediction": "Torn line di spool menghentikan antrean tanpa karantina",
                "falsification_criteria": "Semua 6 injeksi torn line terkarantina tanpa kehilangan antrean",
            },
            # 3. Pembandingan dua heuristik urutan berisiko rendah tanpa jejak replay -> ab_test
            {
                "hypothesis_id": "hyp-prompt-order",
                "domain": "curriculum",
                "risk_level": "low",
                "historical_trace_available": False,
                "compares_variants": True,
                "confidence": 0.60,
                "measurable_prediction": "Varian B meningkatkan ketuntasan >= 12%",
                "falsification_criteria": "Selisih ketuntasan A vs B < 3% pada 16 percobaan",
            },
        ]

        specs = [design_smallest_falsifying_experiment(h) for h in hypotheses]
        self.assertEqual(
            [s["experiment_type"] for s in specs],
            ["replay_audit", "fixture_arena", "ab_test"],
        )
        for s in specs:
            self.assertEqual(s["schema"], SCHEMA)
            self.assertGreaterEqual(s["estimated_cycles"], 1)
            self.assertTrue(s["early_stop_on_falsification"])

        # Biaya siklus replay_audit paling hemat dibanding ab_test berbatas sampel.
        self.assertLess(specs[0]["estimated_cycles"], specs[2]["estimated_cycles"])

        batch = design_batch(hypotheses)
        self.assertEqual(batch["schema"], BATCH_SCHEMA)
        self.assertEqual(batch["by_type"], {"replay_audit": 1, "fixture_arena": 1, "ab_test": 1})

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "hyps.json"
            p.write_text(json.dumps(hypotheses), encoding="utf-8")
            self.assertEqual(main(["--hypotheses", str(p)]), 0)


if __name__ == "__main__":
    unittest.main()
