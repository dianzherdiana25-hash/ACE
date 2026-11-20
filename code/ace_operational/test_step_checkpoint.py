"""Tes tulis/verifikasi/muat state step_checkpoint & tolak korupsi 1 byte atau lompatan seq (AG74)."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_operational.step_checkpoint import (
    StepCheckpointError,
    compute_checkpoint_hash,
    load_latest_checkpoint,
    save_step_checkpoint,
    verify_and_load_checkpoints,
)


class StepCheckpointTests(unittest.TestCase):
    def test_valid_checkpoints_roundtrip_exact_state(self) -> None:
        with TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "steps.ckpt.jsonl"
            self.assertIsNone(load_latest_checkpoint(ckpt))

            e1 = save_step_checkpoint(ckpt, step_id="step-1", state={"acc": 10, "done": ["s1"]})
            e2 = save_step_checkpoint(ckpt, step_id="step-2", state={"acc": 25, "done": ["s1", "s2"]})
            latest = load_latest_checkpoint(ckpt)
            all_rows = verify_and_load_checkpoints(ckpt)

        self.assertEqual(e1["seq"], 1)
        self.assertEqual(e2["seq"], 2)
        self.assertEqual(e2["prev"], e1["hash"])
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["step_id"], "step-2")
        self.assertEqual(latest["state"], {"acc": 25, "done": ["s1", "s2"]})
        self.assertEqual(len(all_rows), 2)

    def test_one_byte_tamper_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "steps.ckpt.jsonl"
            save_step_checkpoint(ckpt, step_id="step-1", state={"counter": 100})
            save_step_checkpoint(ckpt, step_id="step-2", state={"counter": 200})

            raw = bytearray(ckpt.read_bytes())
            idx = raw.index(b"200")
            raw[idx] = ord("9")  # ubah tepat satu byte: "200" -> "900"
            ckpt.write_bytes(bytes(raw))

            with self.assertRaises(StepCheckpointError):
                load_latest_checkpoint(ckpt)

    def test_sequence_jump_rejected_even_with_recomputed_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "steps.ckpt.jsonl"
            e1 = save_step_checkpoint(ckpt, step_id="step-1", state={"v": 1})
            lines = ckpt.read_text(encoding="utf-8").splitlines()
            # Sisipkan entri seq=3 langsung setelah seq=1 dengan hash dihitung ulang -> tetap ditolak karena melompat!
            jumped_hash = compute_checkpoint_hash(
                seq=3, prev=e1["hash"], step_id="step-3", state={"v": 3}
            )
            lines.append(
                json.dumps(
                    {
                        "schema": "ace.step-checkpoint.v1",
                        "seq": 3,
                        "prev": e1["hash"],
                        "step_id": "step-3",
                        "state": {"v": 3},
                        "hash": jumped_hash,
                    }
                )
            )
            ckpt.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with self.assertRaises(StepCheckpointError):
                verify_and_load_checkpoints(ckpt)

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "step_checkpoint.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
