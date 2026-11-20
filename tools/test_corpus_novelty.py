"""Tes unit untuk tools/corpus_novelty.py (AG89)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.corpus_novelty import SCHEMA, main, score_corpus_novelty


class CorpusNoveltyTests(unittest.TestCase):
    def test_hand_computable_jaccard_and_structural_math(self) -> None:
        corpus = [
            {
                "work_id": "ref-alpha",
                "text": "kapal layar pergi jauh.\n\nombak tenang.",
            },
            {
                "work_id": "ref-beta",
                "text": "# Bab Satu\n\"Siapa datang?\" tanya nakhoda.\n\nBadai pecah.",
            },
        ]
        candidates = [
            # Identik dengan ref-alpha -> distance = 0.0 exact.
            {
                "work_id": "cand-clone",
                "text": "kapal layar pergi jauh.\n\nombak tenang.",
            },
            # Leksikal: union={kapal, layar, pergi, jauh, ombak, tenang, bintang, baru} (8 kata),
            # terhadap ref-alpha {kapal, layar, pergi, jauh, ombak, tenang} (6 kata):
            # intersection={ombak, tenang} (2 kata) -> lexical_distance = 1 - 2/8 = 0.75? Wait:
            # Kita pakai hanya {ombak, tenang, bintang, baru} -> union=8, irisan=2 -> 1 - 2/8 = 0.75.
            # Struktur ref-alpha: (paragraphs=2, sentences=2, dialogue_lines=0, section_markers=0).
            # Struktur cand-fresh: 1 paragraf, 1 kalimat, 0 dialog, 0 marker -> (1, 1, 0, 0).
            # L1 structural vs ref-alpha = ((1/2) + (1/2) + 0 + 0) / 4 = 0.25.
            # Combined (0.6 * 0.75) + (0.4 * 0.25) = 0.45 + 0.10 = 0.55.
            {
                "work_id": "cand-fresh",
                "text": "ombak tenang bintang baru.",
            },
            # Struktur tinggi terhadap semua referensi + kata tak beririsan.
            {
                "work_id": "cand-novel",
                "text": (
                    "# Pembuka\n\"Berangkat sekarang!\" seru kapten.\n\n"
                    "---\n\"Arah utara!\" sahut mualim.\n\n"
                    "Pelita padam."
                ),
            },
        ]

        report = score_corpus_novelty(corpus, candidates, lexical_weight=0.6)
        self.assertEqual(report["schema"], SCHEMA)
        by_id = {row["work_id"]: row for row in report["results"]}

        self.assertEqual(by_id["cand-clone"]["nearest_neighbor"], "ref-alpha")
        self.assertAlmostEqual(by_id["cand-clone"]["novelty_score"], 0.0, places=6)

        fresh = by_id["cand-fresh"]
        self.assertEqual(fresh["nearest_neighbor"], "ref-alpha")
        self.assertAlmostEqual(fresh["lexical_distance"], 0.75, places=6)
        self.assertAlmostEqual(fresh["structural_distance"], 0.25, places=6)
        self.assertAlmostEqual(fresh["novelty_score"], 0.55, places=6)

        self.assertGreater(by_id["cand-novel"]["novelty_score"], fresh["novelty_score"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            c_path = tmp / "corpus.json"
            k_path = tmp / "cands.jsonl"
            c_path.write_text(json.dumps(corpus), encoding="utf-8")
            k_path.write_text("\n".join(json.dumps(x) for x in candidates) + "\n", encoding="utf-8")
            self.assertEqual(main(["--corpus", str(c_path), "--candidates", str(k_path)]), 0)


if __name__ == "__main__":
    unittest.main()
