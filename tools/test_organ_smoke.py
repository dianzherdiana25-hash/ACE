"""Tes harness smoke dua organ tiruan dengan profil berlawanan di keempat peran (AG83)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import organ_smoke


class OrganSmokeTest(unittest.TestCase):
    def test_two_contrasting_mock_organs_across_all_four_roles(self) -> None:
        pack = organ_smoke.default_smoke_pack() + [
            {
                "id": "smk-pen-2",
                "role": "penilai",
                "prompt": "Verifikasi bukti kedua.",
                "expected": "OK",
            }
        ]

        now_val = {"t": 100.0}

        def fake_clock() -> float:
            return now_val["t"]

        def mock_transport(organ: str, task: dict) -> dict:
            if organ == "organ-prima":
                now_val["t"] += 0.012  # 12 ms
                return {"ok": True, "output": task["expected"]}
            if organ == "organ-goyah":
                now_val["t"] += 0.450  # 450 ms
                # Hanya lulus 1 dari 5 tugas (bahasa); sisanya error/jawaban meleset.
                if task["role"] == "bahasa":
                    return {"ok": True, "output": task["expected"]}
                if task["role"] == "praktik":
                    return {"ok": True, "output": "jawaban_salah"}
                return {"ok": False, "output": ""}
            raise AssertionError(f"organ tidak dikenal: {organ}")

        report = organ_smoke.run_organ_smoke(
            ["organ-prima", "organ-goyah"],
            pack,
            mock_transport,
            clock=fake_clock,
        )
        self.assertEqual(report["schema"], organ_smoke.SCHEMA)
        self.assertEqual(set(report["roles_tested"]), set(organ_smoke.ROLES))
        self.assertEqual(
            report["summary"]["ranking_best_to_worst"],
            ["organ-prima", "organ-goyah"],
        )

        prima = report["by_organ"]["organ-prima"]
        goyah = report["by_organ"]["organ-goyah"]

        self.assertEqual(prima["overall"]["failure_rate"], 0.0)
        self.assertEqual(prima["overall"]["quality_score"], 1.0)
        self.assertAlmostEqual(prima["overall"]["avg_latency_ms"], 12.0, places=2)

        self.assertAlmostEqual(goyah["overall"]["failure_rate"], 0.6, places=6)
        self.assertAlmostEqual(goyah["overall"]["quality_score"], 0.2, places=6)
        self.assertAlmostEqual(goyah["overall"]["avg_latency_ms"], 450.0, places=2)

        # Verifikasi rincian per peran juga tersedia lengkap.
        self.assertEqual(goyah["by_role"]["bahasa"]["quality_score"], 1.0)
        self.assertEqual(goyah["by_role"]["director"]["failure_rate"], 1.0)
        self.assertEqual(goyah["by_role"]["praktik"]["failure_rate"], 0.0)
        self.assertEqual(goyah["by_role"]["praktik"]["quality_score"], 0.0)

    def test_cli_runs_cleanly_offline(self) -> None:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "smoke.json"
            self.assertEqual(organ_smoke.main(["--out", str(out)]), 0)
            rep = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"]["organ_count"], 2)


if __name__ == "__main__":
    unittest.main()
