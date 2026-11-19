"""Verifikasi integritas artefak sensus kandidat E1 (docs/SENSUS_KANDIDAT.*)."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


class SensusKandidatE1Tests(unittest.TestCase):
    def test_sensus_json_and_markdown_cover_all_handover_corpora(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        json_path = repo / "docs" / "SENSUS_KANDIDAT.json"
        md_path = repo / "docs" / "SENSUS_KANDIDAT.md"
        self.assertTrue(json_path.is_file())
        self.assertTrue(md_path.is_file())

        data = json.loads(json_path.read_text(encoding="utf-8"))
        md_text = md_path.read_text(encoding="utf-8")
        self.assertEqual(data["schema"], "ace.candidate-census.v1")
        self.assertEqual(data["file_count"], 5)
        self.assertEqual(data["ready_count"], 2)
        self.assertEqual(data["not_ready_count"], 3)

        expected = {
            "handover/EVO_0003_CORPUS_TAIL_V1.jsonl": (16, "BELUM_LAYAK"),
            "handover/EVO_0005_CORPUS_V1.jsonl": (16, "LAYAK"),
            "handover/EVO_0006_CORPUS_CANDIDATES_V1.jsonl": (24, "LAYAK"),
            "handover/EVO0007_KANDIDAT_PABRIK.jsonl": (24, "BELUM_LAYAK"),
            "handover/KANDIDAT_PABRIK_0007_BEKU.jsonl": (24, "BELUM_LAYAK"),
        }
        by_src = {entry["source"]: entry for entry in data["files"]}
        self.assertEqual(set(by_src.keys()), set(expected.keys()))

        for src, (exp_lines, exp_verdict) in expected.items():
            target_file = repo / src
            self.assertTrue(target_file.is_file())
            actual_lines = len(target_file.read_text(encoding="utf-8").splitlines())
            self.assertEqual(by_src[src]["total_lines"], exp_lines)
            self.assertEqual(actual_lines, exp_lines)
            self.assertEqual(by_src[src]["readiness"]["verdict"], exp_verdict)
            self.assertIn(src, md_text)


if __name__ == "__main__":
    unittest.main()
