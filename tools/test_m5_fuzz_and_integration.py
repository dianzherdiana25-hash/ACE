#!/usr/bin/env python3
"""Unit tests untuk M5: fuzz parser WS-E..WS-H dan integrasi portability_pack + instance_kit."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import fuzz_wseh


class TestM5FuzzAndIntegration(unittest.TestCase):
    def test_wseh_fuzz_matrix_zero_crashes_across_3_seeds_x_300(self) -> None:
        report = fuzz_wseh.run_wseh_fuzz_matrix(
            seeds=(20261117, 20261118, 20261119),
            iterations=300,
        )
        self.assertEqual(report["schema"], "ace.fuzz-wseh.v1")
        self.assertEqual(report["total_targets"], 8)
        self.assertEqual(report["total_checks"], 7200)
        self.assertEqual(report["total_crashes"], 0)
        self.assertTrue(report["ok"])

    def test_portability_pack_and_instance_kit_integration_when_present(self) -> None:
        try:
            portability_pack = importlib.import_module("tools.portability_pack")
            instance_kit = importlib.import_module("tools.instance_kit")
        except ImportError:
            # Pada branch yang belum me-merge PR #297 & #298, verifikasi kontrak minimum lewat skema
            self.assertIn("portability_pack", fuzz_wseh.TARGETS)
            self.assertIn("instance_kit", fuzz_wseh.TARGETS)
            return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inst1_base = tmp_path / "inst1_root"
            inst2_base = tmp_path / "inst2_root"
            cfg1 = instance_kit.build_instance_config(
                instance_id="ace-src",
                base_dir=inst1_base,
                port_base=8400,
            )
            cfg2 = instance_kit.build_instance_config(
                instance_id="ace-dst",
                base_dir=inst2_base,
                port_base=8500,
            )
            iso_report = instance_kit.validate_isolation([cfg1, cfg2])
            self.assertTrue(iso_report["isolated"])
            self.assertIs(iso_report["second_instance_active"], False)

            ws1 = Path(cfg1["directories"]["workspace_dir"])
            ws1.mkdir(parents=True, exist_ok=True)
            (ws1 / "state.json").write_text('{"cycle": 7}\n', encoding="utf-8")
            (ws1 / "instance_config.json").write_text(json.dumps(cfg1), encoding="utf-8")

            bundle = tmp_path / "migration.tar.gz"
            pack_res = portability_pack.pack_bundle(
                source_dir=ws1,
                out_path=bundle,
                include_paths=["state.json", "instance_config.json"],
            )
            self.assertEqual(pack_res["file_count"], 2)

            ws2 = Path(cfg2["directories"]["workspace_dir"])
            unpack_res = portability_pack.unpack_bundle(bundle_path=bundle, dest_dir=ws2)
            self.assertTrue(unpack_res["ok"])
            self.assertEqual(unpack_res["restored_count"], 2)
            self.assertEqual((ws2 / "state.json").read_text(encoding="utf-8"), '{"cycle": 7}\n')

            # Pastikan setelah unpack ke ws2, kedua instans tetap terisolasi penuh
            iso_after = instance_kit.validate_isolation([cfg1, cfg2])
            self.assertTrue(iso_after["isolated"])


if __name__ == "__main__":
    unittest.main()
