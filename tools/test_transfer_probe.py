"""Tes validitas paket suite transfer dan skoring probe pada solver mainan (AG63)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import transfer_probe


class TransferProbeTest(unittest.TestCase):
    def test_default_suite_integrity_three_domain_pairs(self) -> None:
        suite = transfer_probe.load_transfer_suite()
        integrity = transfer_probe.validate_suite_integrity(suite)
        self.assertTrue(integrity["valid"])
        self.assertEqual(integrity["pair_count"], 3)
        self.assertEqual(
            integrity["pair_ids"],
            list(transfer_probe.REQUIRED_PAIR_IDS),
        )
        # Seed berbeda menghasilkan variasi tugas jembatan yang tetap deterministik.
        b0 = transfer_probe.generate_bridge_task(suite[0], seed=0)
        b1 = transfer_probe.generate_bridge_task(suite[0], seed=1)
        self.assertNotEqual(b0["input"], b1["input"])
        self.assertEqual(b0, transfer_probe.generate_bridge_task(suite[0], seed=0))

    def test_probe_distinguishes_structural_transfer_vs_source_only_solver(self) -> None:
        suite = transfer_probe.load_transfer_suite()

        rep_good = transfer_probe.run_transfer_probe(
            suite, transfer_probe.structural_toy_solver, seed=1
        )
        self.assertEqual(rep_good["schema"], transfer_probe.SCHEMA)
        self.assertEqual(rep_good["summary"]["source_score"], 1.0)
        self.assertEqual(rep_good["summary"]["bridge_score"], 1.0)
        self.assertEqual(rep_good["summary"]["target_score"], 1.0)
        self.assertEqual(rep_good["summary"]["transfer_gap"], 0.0)

        def source_only_memorizer(task: dict) -> object:
            # Hanya hapal tugas sumber, gagal pada target & jembatan.
            if "-src-" in task["id"]:
                return transfer_probe.structural_toy_solver(task)
            return "__wrong__"

        rep_memo = transfer_probe.run_transfer_probe(suite, source_only_memorizer, seed=1)
        self.assertEqual(rep_memo["summary"]["source_score"], 1.0)
        self.assertEqual(rep_memo["summary"]["bridge_score"], 0.0)
        self.assertEqual(rep_memo["summary"]["target_score"], 0.0)
        self.assertEqual(rep_memo["summary"]["transfer_gap"], -1.0)

    def test_cli_validate_and_probe(self) -> None:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe.json"
            self.assertEqual(transfer_probe.main(["--mode", "validate"]), 0)
            self.assertEqual(
                transfer_probe.main(["--mode", "probe", "--seed", "0", "--out", str(out)]),
                0,
            )
            rep = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(rep["summary"]["target_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
