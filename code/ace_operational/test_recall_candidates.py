"""Tes kandidat retrieval hibrida (leksikal, embedding, provenance) (AG58)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from ace_operational.recall_candidates import (
    embedding_candidates,
    lexical_candidates,
    merge_candidates,
    provenance_candidates,
)


class _FixtureStore:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def list_records(self):
        return list(self._records)


def _toy_embedder(text: str) -> list[float]:
    low = text.lower()
    return [
        float("spool" in low or "antrean" in low or "relay" in low),
        float("sinonim_memori" in low or "episodik" in low or "ingatan" in low),
        float("watchdog" in low or "pid" in low),
    ]


class RecallCandidatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _FixtureStore(
            [
                {
                    "id": "r-lex",
                    "kind": "semantic",
                    "content": {"fact": "bridge relay memakai spool antrean aman"},
                    "source": {"kind": "evidence", "ref": "ev-spool-1"},
                },
                {
                    "id": "r-emb",
                    "kind": "semantic",
                    "content": {"fact": "sinonim_memori menyimpan pengalaman lampau"},
                    "source": {"kind": "evidence", "ref": "ev-other-9"},
                },
                {
                    "id": "r-prov-hop0",
                    "kind": "episodic",
                    "content": {"note": "catatan verifikasi langkah awal"},
                    "source": {"kind": "evidence", "ref": "ev-spool-1"},
                    "evidence_refs": ["ev-link-2"],
                },
                {
                    "id": "r-prov-hop1",
                    "kind": "procedural",
                    "content": {"step": "prosedur pemulihan lanjutan"},
                    "source": {"kind": "evidence", "ref": "ev-link-2"},
                },
                {
                    "id": "r-irrelevant",
                    "kind": "semantic",
                    "content": {"fact": "watchdog memeriksa pid"},
                    "source": {"kind": "operator", "ref": "ev-unrelated"},
                },
            ]
        )

    def test_three_channels_and_deterministic_merge(self) -> None:
        lex = lexical_candidates("spool relay", self.store)
        self.assertEqual([c["id"] for c in lex], ["r-lex"])

        emb = embedding_candidates("ingatan episodik", self.store, _toy_embedder)
        self.assertEqual([c["id"] for c in emb], ["r-emb"])

        prov = provenance_candidates("cek ev-spool-1", self.store)
        prov_map = {c["id"]: c["hop"] for c in prov}
        self.assertEqual(prov_map["r-lex"], 0)
        self.assertEqual(prov_map["r-prov-hop0"], 0)
        self.assertEqual(prov_map["r-prov-hop1"], 1)
        self.assertNotIn("r-irrelevant", prov_map)

        merged_1 = merge_candidates(
            {"lexical": lex, "embedding": emb, "provenance": prov}
        )
        merged_2 = merge_candidates(
            {"provenance": prov, "embedding": emb, "lexical": lex}
        )
        # Urutan terdeterministik independen dari urutan kunci input.
        self.assertEqual(merged_1, merged_2)
        # r-lex muncul di dua jalur (lexical + provenance) sehingga menduduki puncak.
        self.assertEqual(merged_1[0]["id"], "r-lex")
        self.assertEqual(merged_1[0]["channels"], ["lexical", "provenance"])

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "recall_candidates.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
