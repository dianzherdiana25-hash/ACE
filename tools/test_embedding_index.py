"""Tes indeks embedding sidecar inkremental + verify (AG60)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_operational.cognitive_memory import CognitiveMemory
from tools import embedding_index


class EmbeddingIndexTest(unittest.TestCase):
    def test_incremental_update_reuses_unchanged_and_verify_flags_missing_and_orphans(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem_dir = root / "mem"
            mem = CognitiveMemory(mem_dir)
            d1 = mem.anchor_evidence(b"e1")
            r1 = mem.remember(
                kind="semantic",
                content={"topic": "spool"},
                source_kind="evidence",
                source_ref=d1,
                confidence=0.9,
            )
            r2 = mem.remember(
                kind="procedural",
                content={"topic": "watchdog"},
                source_kind="operator",
                source_ref="doc:wd",
                confidence=0.85,
            )
            mem_jsonl = mem_dir / "memory.jsonl"
            index_jsonl = root / "embeddings.jsonl"
            calls: list[str] = []

            def spy_embedder(text: str) -> list[float]:
                calls.append(text)
                return [float(len(text)), 1.0, 0.5]

            # 1. Build awal: 2 record di-embed.
            res1 = embedding_index.build_or_update_index(mem_jsonl, index_jsonl, spy_embedder)
            self.assertEqual(res1["embedded_count"], 2)
            self.assertEqual(res1["reused_count"], 0)
            self.assertEqual(len(calls), 2)

            ver1 = embedding_index.verify_index(mem_jsonl, index_jsonl)
            self.assertTrue(ver1["valid"])
            self.assertEqual(ver1["missing_vectors"], [])
            self.assertEqual(ver1["orphan_vectors"], [])

            # 2. Tambah 1 record baru -> update inkremental hanya memanggil embedder 1 kali!
            calls.clear()
            r3 = mem.remember(
                kind="episodic",
                content={"topic": "rollover"},
                source_kind="evidence",
                source_ref=d1,
                confidence=0.8,
            )
            before_bytes = mem_jsonl.read_bytes()
            res2 = embedding_index.build_or_update_index(mem_jsonl, index_jsonl, spy_embedder)
            self.assertEqual(mem_jsonl.read_bytes(), before_bytes)
            self.assertEqual(res2["embedded_count"], 1)
            self.assertEqual(res2["reused_count"], 2)
            self.assertEqual(res2["embedded_ids"], [r3])
            self.assertEqual(sorted(res2["reused_ids"]), sorted([r1, r2]))
            self.assertEqual(len(calls), 1)

            # 3. Sisipkan vektor yatim dan tambah r4 belum terindeks -> CLI verify melaporkan keduanya (exit 1).
            r4 = mem.remember(
                kind="semantic",
                content={"topic": "unindexed"},
                source_kind="operator",
                source_ref="doc:u",
                confidence=0.7,
            )
            with index_jsonl.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "record_id": "rec-ghost-orphan",
                            "content_sha256": "deadbeef",
                            "model": "test",
                            "dim": 3,
                            "vector": [1.0, 0.0, 0.0],
                        }
                    )
                    + "\n"
                )

            out_report = root / "verify.json"
            rc = embedding_index.main(
                ["verify", "--memory", str(mem_jsonl), "--index", str(index_jsonl), "--out", str(out_report)]
            )
            self.assertEqual(rc, 1)
            rep = json.loads(out_report.read_text(encoding="utf-8"))
            self.assertFalse(rep["valid"])
            self.assertEqual(rep["missing_vectors"], [r4])
            self.assertEqual(rep["orphan_vectors"], ["rec-ghost-orphan"])


if __name__ == "__main__":
    unittest.main()
