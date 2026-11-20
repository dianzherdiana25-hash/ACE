"""Tes distiler konsolidasi episode + snapshot rollback + tolak klaim tanpa sumber (AG61)."""

from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.memory_consolidation import (
    build_semantic_record,
    distill_memory_log,
    restore_pre_distillation_snapshot,
    validate_consolidated_claims,
)


class MemoryConsolidationTests(unittest.TestCase):
    def test_distills_episodes_preserves_source_log_and_supports_rollback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem_dir = root / "mem"
            snap_dir = root / "snapshots"
            mem = CognitiveMemory(mem_dir)
            d1 = mem.anchor_evidence(b"distill-ev")

            ep1 = mem.remember(
                kind="episodic",
                content={"topic": "spool_safety", "observation": "os.replace cegah half-write"},
                source_kind="evidence",
                source_ref=d1,
                confidence=0.9,
            )
            ep2 = mem.remember(
                kind="episodic",
                content={"topic": "spool_safety", "observation": "quarantine entri rusak menjaga antrean"},
                source_kind="evidence",
                source_ref=d1,
                confidence=0.88,
            )
            ep_solo = mem.remember(
                kind="episodic",
                content={"topic": "singleton_topic", "observation": "hanya satu kejadian"},
                source_kind="operator",
                source_ref="doc:solo",
                confidence=0.7,
            )

            log_path = mem_dir / "memory.jsonl"
            before_bytes = log_path.read_bytes()

            report = distill_memory_log(
                log_path, snapshot_dir=snap_dir, min_cluster_size=2
            )

            # Log asli tidak tersentuh sedikit pun.
            self.assertEqual(log_path.read_bytes(), before_bytes)
            self.assertEqual(report["total_active_episodes"], 3)
            self.assertEqual(report["consolidated_cluster_count"], 1)
            self.assertEqual(
                report["skipped_small_clusters"],
                [{"cluster": "singleton_topic", "episode_count": 1}],
            )

            sem_rec = report["semantic_records"][0]
            self.assertEqual(sem_rec["kind"], "semantic")
            self.assertEqual(sem_rec["source_episodes"], sorted([ep1, ep2]))
            for claim in sem_rec["content"]["claims"]:
                self.assertTrue(claim["source_episodes"])
                self.assertTrue(set(claim["source_episodes"]).issubset({ep1, ep2, ep_solo}))

            # Uji rollback dari snapshot pra-distilasi ke salinan target.
            restored_copy = root / "restored_memory.jsonl"
            restored_copy.write_bytes(b"corrupted-after-change\n")
            restore_pre_distillation_snapshot(snap_dir, restored_copy)
            self.assertEqual(restored_copy.read_bytes(), before_bytes)

    def test_rejects_claims_without_or_with_unknown_source_episodes(self) -> None:
        for bad_claims in (
            [],
            [{"statement": "klaim mengambang tanpa penunjuk"}],
            [{"statement": "penunjuk kosong", "source_episodes": []}],
            [{"statement": "episode palsu", "source_episodes": ["ep-tidak-ada"]}],
        ):
            with self.subTest(bad_claims=bad_claims), self.assertRaises(ValueError):
                validate_consolidated_claims(bad_claims, {"ep-sah-1"})
                build_semantic_record("cluster-a", bad_claims, {"ep-sah-1"})

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem = CognitiveMemory(root / "mem")
            mem.remember(
                kind="episodic",
                content={"topic": "x", "observation": "a"},
                source_kind="operator",
                source_ref="doc:a",
            )
            mem.remember(
                kind="episodic",
                content={"topic": "x", "observation": "b"},
                source_kind="operator",
                source_ref="doc:b",
            )
            with self.assertRaises(ValueError):
                distill_memory_log(
                    root / "mem" / "memory.jsonl",
                    snapshot_dir=root / "snap",
                    synthesizer=lambda _c, _eps: [{"statement": "tanpa sumber"}],
                )

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "memory_consolidation.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
