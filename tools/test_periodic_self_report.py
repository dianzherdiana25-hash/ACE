#!/usr/bin/env python3
"""Unit tests for C5: Periodic Self-Report generator (strictly read-only)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.periodic_self_report import (
    SCHEMA,
    build_periodic_self_report,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PeriodicSelfReportTests(unittest.TestCase):
    def test_real_repo_report_structure_and_citations(self) -> None:
        rep = build_periodic_self_report(REPO_ROOT)
        self.assertEqual(rep["schema"], SCHEMA)
        self.assertTrue(rep["read_only"])

        gate_names = {g["gate"] for g in rep["gates"]}
        for required in ("G1", "G2", "G3", "G4", "G5", "round2-gate-01"):
            self.assertIn(required, gate_names)

        self.assertGreaterEqual(len(rep["latest_verdicts"]), 3)
        self.assertGreaterEqual(len(rep["queue"]), 2)
        debt_ids = {d["debt_id"] for d in rep["named_evidence_debt"]}
        self.assertIn("DEBT_G2_NOT_DEMONSTRATED", debt_ids)
        self.assertIn("DEBT_G5_NOT_ASSESSED", debt_ids)
        self.assertIn("DEBT_MEMORY_ZERO_EVIDENCE_RECORDS", debt_ids)

        # Pastikan berkas KBM yang tidak ada tidak ditebak-tebak
        kbm_q = [q for q in rep["queue"] if q["item_id"] == "kbm_serialization_queue"][0]
        self.assertEqual(kbm_q["status"], "SOURCE_NOT_PRESENT")

        md = render_markdown(rep)
        self.assertIn("Papan Gerbang", md)
        self.assertIn("Vonis Terbaru", md)
        self.assertIn("Antrean Aktif", md)
        self.assertIn("Utang Bukti Bernama", md)

    def test_accepts_c1_narrative_json_plus_custom_ledger_and_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            narrative_path = root / "c1.json"
            narrative_path.write_text(
                json.dumps(
                    {
                        "schema": "ace.narrative-self-model.v1",
                        "sections": {
                            "identity": [],
                            "proven": [
                                {
                                    "fact_key": "gate:G3",
                                    "fact_value": "MEASURED_SPECIALIZATION",
                                    "sources": [{"path": "docs/research/ACE_OMEGA_CHECKPOINT_20261112_ADDENDUM58.md", "sha256": "a" * 64, "line": 7}],
                                }
                            ],
                            "unproven": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            qfile = root / "queue.md"
            qfile.write_text("- Jalankan smoke bridge API\n- Verifikasi rail QRIS\n", encoding="utf-8")
            ledger = root / "LEDGER_PENGHASILAN.md"
            ledger.write_text("Total keseluruhan TUNAI terverifikasi: Rp 0\n", encoding="utf-8")

            rep = build_periodic_self_report(
                REPO_ROOT,
                narrative_json_path=narrative_path,
                queue_files=[qfile],
                ledger_paths=[ledger],
            )
            q_titles = [q["title"] for q in rep["queue"]]
            self.assertIn("Jalankan smoke bridge API", q_titles)
            self.assertIn("DEBT_REVENUE_BASELINE_RP0", {d["debt_id"] for d in rep["named_evidence_debt"]})

    def test_missing_memory_dir_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            absent = Path(td) / "absent_mem"
            rep = build_periodic_self_report(REPO_ROOT, memory_path=absent)
            self.assertFalse(absent.exists())
            self.assertFalse(rep["memory_overview"]["present"])


if __name__ == "__main__":
    unittest.main()
