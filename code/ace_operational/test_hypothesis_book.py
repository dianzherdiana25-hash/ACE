"""Tes unit untuk code/ace_operational/hypothesis_book.py (AG94)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from ace_operational.hypothesis_book import (
    ExperimentRecord,
    HypothesisBook,
    HypothesisBookError,
    SCHEMA,
)


class HypothesisBookTests(unittest.TestCase):
    def test_no_engine_imports(self) -> None:
        src_path = Path(__file__).with_name("hypothesis_book.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("autonomous_engine" in name for name in imported))

    def test_full_lifecycle_including_retest_from_belum_tentu(self) -> None:
        book = HypothesisBook()
        book.register(
            "hyp-recall-01",
            cause="Ambang skor penyaring kandidat terlalu tinggi",
            measurable_prediction="Recall turun menjadi 0 meski ada tetangga di toko memori",
            falsification_condition="Recall >= 7/8 saat ambang diturunkan tetap tidak berubah",
            confidence=0.72,
            domain="recall",
        )
        book.register(
            "hyp-cache-02",
            cause="Indeks leksikal basi sesudah rotasi segmen",
            measurable_prediction="Peningkatan hit-rate minimal 15% setelah rebuild indeks",
            falsification_condition="Selisih hit-rate < 2% pada 50 kueri terukur",
            confidence=0.60,
            domain="memory",
        )
        book.register(
            "hyp-backoff-03",
            cause="Jeda awal relay memicu timeout prematur",
            measurable_prediction="Tingkat kegagalan 503 turun di bawah 5%",
            falsification_condition="Tingkat kegagalan tetap > 20%",
            confidence=0.55,
            domain="bridge",
        )

        # 1. terdaftar -> diuji -> didukung
        book.start_test("hyp-recall-01", experiment_id="exp-001")
        row1 = book.record_outcome(
            "hyp-recall-01",
            verdict="didukung",
            experiment=ExperimentRecord(
                experiment_id="exp-001",
                observed_outcome="7/7 tugas bertetangga terkirim sesudah penyesuaian",
                evidence_ref="reports/exp-001.json",
            ),
            updated_confidence=0.92,
        )
        self.assertEqual(row1["status"], "didukung")
        self.assertEqual(row1["confidence"], 0.92)

        # 2. terdaftar -> diuji -> gugur
        book.start_test("hyp-backoff-03", experiment_id="exp-002")
        row3 = book.record_outcome(
            "hyp-backoff-03",
            verdict="gugur",
            experiment={
                "experiment_id": "exp-002",
                "observed_outcome": "Tingkat kegagalan masih 28%",
                "evidence_ref": "reports/exp-002.json",
            },
            updated_confidence=0.12,
        )
        self.assertEqual(row3["status"], "gugur")

        # 3. terdaftar -> diuji -> belum_tentu -> diuji ulang -> didukung
        book.start_test("hyp-cache-02", experiment_id="exp-003a")
        row2a = book.record_outcome(
            "hyp-cache-02",
            verdict="belum_tentu",
            experiment={
                "experiment_id": "exp-003a",
                "observed_outcome": "Sampel terlalu kecil (3 kueri)",
                "evidence_ref": "reports/exp-003a.json",
            },
        )
        self.assertEqual(row2a["status"], "belum_tentu")
        book.start_test("hyp-cache-02", experiment_id="exp-003b")
        row2b = book.record_outcome(
            "hyp-cache-02",
            verdict="didukung",
            experiment={
                "experiment_id": "exp-003b",
                "observed_outcome": "Hit-rate naik +21% pada 50 kueri",
                "evidence_ref": "reports/exp-003b.json",
            },
        )
        self.assertEqual(row2b["status"], "didukung")

        exported = book.export_book()
        self.assertEqual(exported["schema"], SCHEMA)
        self.assertEqual(exported["by_status"]["didukung"], 2)
        self.assertEqual(exported["by_status"]["gugur"], 1)

    def test_rejects_wild_transitions_and_missing_experiment_records(self) -> None:
        book = HypothesisBook()
        book.register(
            "hyp-wild",
            cause="Sebab uji",
            measurable_prediction="Prediksi uji",
            falsification_condition="Syarat gugur uji",
            confidence=0.5,
        )

        # Lompatan langsung terdaftar -> didukung / gugur / belum_tentu wajib ditolak.
        for jump_status in ("didukung", "gugur", "belum_tentu"):
            with self.assertRaises(HypothesisBookError):
                book.transition(
                    "hyp-wild",
                    target_status=jump_status,
                    experiment={
                        "experiment_id": "exp-skip",
                        "observed_outcome": "Lompat",
                        "evidence_ref": "x.json",
                    },
                )

        # Mulai pengujian tanpa experiment_id juga ditolak.
        with self.assertRaises(HypothesisBookError):
            book.transition("hyp-wild", target_status="diuji", experiment_id=None)

        book.start_test("hyp-wild", experiment_id="exp-valid")

        # Verdict tanpa catatan eksperimen atau mismatch ID eksperimen ditolak.
        with self.assertRaises(HypothesisBookError):
            book.record_outcome("hyp-wild", verdict="didukung", experiment=None)
        with self.assertRaises(HypothesisBookError):
            book.record_outcome(
                "hyp-wild",
                verdict="didukung",
                experiment={
                    "experiment_id": "exp-lain",
                    "observed_outcome": "Cocok sebagian",
                    "evidence_ref": "e.json",
                },
            )

        book.record_outcome(
            "hyp-wild",
            verdict="gugur",
            experiment={
                "experiment_id": "exp-valid",
                "observed_outcome": "Terbantahkan",
                "evidence_ref": "e.json",
            },
        )
        # Status terminal gugur/didukung tidak bisa melompat mundur.
        with self.assertRaises(HypothesisBookError):
            book.start_test("hyp-wild", experiment_id="exp-retry")
        with self.assertRaises(HypothesisBookError):
            book.transition("hyp-wild", target_status="terdaftar")


if __name__ == "__main__":
    unittest.main()
