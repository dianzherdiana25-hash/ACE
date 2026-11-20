"""Tes regresi fixture-only untuk tools.memory_chain_compare (AG51)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import memory_chain_compare


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_chain(path: Path, payloads: list[dict]) -> list[dict]:
    prev = memory_chain_compare.GENESIS_PREV
    rows: list[dict] = []
    for seq, event in enumerate(payloads, 1):
        digest = hashlib.sha256(_canonical({"prev": prev, "event": event}).encode("utf-8")).hexdigest()
        row = {"seq": seq, "prev": prev, "event": event, "hash": digest}
        rows.append(row)
        prev = digest
    path.write_text("\n".join(_canonical(r) for r in rows) + "\n", encoding="utf-8")
    return rows


class MemoryChainCompareTest(unittest.TestCase):
    def test_identical_fast_forward_and_diverged_cases(self) -> None:
        ev1 = {"type": "record", "record": {"id": "r1", "kind": "semantic", "content": {"k": "v1"}}}
        ev2 = {"type": "record", "record": {"id": "r2", "kind": "semantic", "content": {"k": "v2"}}}
        ev3_a = {"type": "record", "record": {"id": "r3a", "kind": "semantic", "content": {"k": "a3"}}}
        ev3_b = {"type": "record", "record": {"id": "r3b", "kind": "semantic", "content": {"k": "b3"}}}
        ev4_b = {"type": "record", "record": {"id": "r4b", "kind": "semantic", "content": {"k": "b4"}}}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p_base = root / "base.jsonl"
            p_same = root / "same.jsonl"
            p_ff = root / "ff.jsonl"
            p_div_a = root / "div_a.jsonl"
            p_div_b = root / "div_b.jsonl"
            out_path = root / "cmp.json"

            base_rows = _write_chain(p_base, [ev1, ev2])
            _write_chain(p_same, [ev1, ev2])
            _write_chain(p_ff, [ev1, ev2, ev3_b, ev4_b])
            rows_a = _write_chain(p_div_a, [ev1, ev2, ev3_a])
            rows_b = _write_chain(p_div_b, [ev1, ev2, ev3_b])

            # 1. Identical
            rep_same = memory_chain_compare.compare_memory_chains(p_base, p_same)
            self.assertEqual(rep_same["schema"], memory_chain_compare.SCHEMA)
            self.assertEqual(rep_same["status"], "identical")
            self.assertFalse(rep_same["is_fork"])
            self.assertIsNone(rep_same["first_divergence"])
            self.assertEqual(rep_same["common_prefix_length"], 2)
            self.assertTrue(rep_same["left"]["integrity_valid"])
            self.assertTrue(rep_same["right"]["integrity_valid"])

            # 2. Fast-forward (kanan lebih panjang -> BUKAN fork!)
            rep_ff_right = memory_chain_compare.compare_memory_chains(p_base, p_ff)
            self.assertEqual(rep_ff_right["status"], "fast_forward")
            self.assertFalse(rep_ff_right["is_fork"])
            self.assertEqual(rep_ff_right["ahead_side"], "right")
            self.assertEqual(rep_ff_right["ahead_entries"], 2)
            self.assertEqual(rep_ff_right["last_common_seq"], 2)
            self.assertEqual(rep_ff_right["last_common_hash"], base_rows[-1]["hash"])
            self.assertIsNone(rep_ff_right["first_divergence"])

            # Fast-forward simetris (kiri lebih panjang -> BUKAN fork!)
            rep_ff_left = memory_chain_compare.compare_memory_chains(p_ff, p_base)
            self.assertEqual(rep_ff_left["status"], "fast_forward")
            self.assertFalse(rep_ff_left["is_fork"])
            self.assertEqual(rep_ff_left["ahead_side"], "left")
            self.assertEqual(rep_ff_left["ahead_entries"], 2)

            # 3. Diverged via CLI: bercabang tepat pada seq=3
            rc = memory_chain_compare.main(
                ["--left", str(p_div_a), "--right", str(p_div_b), "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            rep_div = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep_div["status"], "diverged")
        self.assertTrue(rep_div["is_fork"])
        self.assertEqual(rep_div["common_prefix_length"], 2)
        self.assertEqual(rep_div["last_common_seq"], 2)
        self.assertEqual(rep_div["last_common_hash"], base_rows[-1]["hash"])
        div = rep_div["first_divergence"]
        self.assertIsNotNone(div)
        self.assertEqual(div["seq_left"], 3)
        self.assertEqual(div["seq_right"], 3)
        self.assertEqual(div["hash_left"], rows_a[2]["hash"])
        self.assertEqual(div["hash_right"], rows_b[2]["hash"])
        self.assertNotEqual(div["hash_left"], div["hash_right"])


if __name__ == "__main__":
    unittest.main()
