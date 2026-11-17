#!/usr/bin/env python3
"""Unit tests untuk tools/instance_kit.py (WS-H #21)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tools import instance_kit


class TestInstanceKit(unittest.TestCase):
    def test_two_generated_instances_pass_isolation_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "instances"
            cfg1_path = Path(tmp) / "inst1.json"
            cfg2_path = Path(tmp) / "inst2.json"

            rc1 = instance_kit.main(
                [
                    "--init",
                    "--instance-id",
                    "ace-primary",
                    "--base-dir",
                    str(base),
                    "--port-base",
                    "8100",
                    "--out",
                    str(cfg1_path),
                ]
            )
            rc2 = instance_kit.main(
                [
                    "--init",
                    "--instance-id",
                    "ace-shadow",
                    "--base-dir",
                    str(base),
                    "--port-base",
                    "8200",
                    "--out",
                    str(cfg2_path),
                ]
            )
            self.assertEqual(rc1, 0)
            self.assertEqual(rc2, 0)

            cfg2 = json.loads(cfg2_path.read_text(encoding="utf-8"))
            self.assertEqual(cfg2["schema"], "ace.instance-isolation.v1")
            self.assertIs(cfg2["foundation_only"], True)
            self.assertIs(cfg2["second_instance_active"], False)

            rc_val = instance_kit.main(["--validate", str(cfg1_path), str(cfg2_path)])
            self.assertEqual(rc_val, 0)

    def test_detects_nesting_symlink_port_lock_and_active_flag_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "instances"
            cfg1 = instance_kit.build_instance_config(
                instance_id="inst-a",
                base_dir=base,
                port_base=8300,
            )
            cfg2 = instance_kit.build_instance_config(
                instance_id="inst-b",
                base_dir=base,
                port_base=8300,  # tabrakan port dengan inst-a
                lock_namespace=cfg1["lock_namespace"],  # tabrakan lock
            )
            # Buat nesting direktori: store_dir inst-b diletakkan di dalam workspace_dir inst-a
            cfg2["directories"]["store_dir"] = str(Path(cfg1["directories"]["workspace_dir"]) / "nested_store")
            cfg2["second_instance_active"] = True  # dilarang pada tahap fondasi

            # Buat symlink di disk pada cache_dir inst-a
            real_target = Path(tmp) / "outside_cache"
            real_target.mkdir()
            cache_parent = Path(cfg1["directories"]["cache_dir"]).parent
            cache_parent.mkdir(parents=True, exist_ok=True)
            os.symlink(real_target, cfg1["directories"]["cache_dir"])

            report = instance_kit.validate_isolation([cfg1, cfg2])
            self.assertFalse(report["isolated"])
            kinds = {v["kind"] for v in report["violations"]}
            self.assertIn("port_collision", kinds)
            self.assertIn("lock_namespace_collision", kinds)
            self.assertIn("directory_overlap_cross_instance", kinds)
            self.assertIn("root_containment_escape", kinds)
            self.assertIn("active_flag_forbidden", kinds)
            self.assertIn("symlink_in_directory_path", kinds)

            bad_file = Path(tmp) / "bad.json"
            bad_file.write_text(json.dumps(cfg2), encoding="utf-8")
            self.assertEqual(instance_kit.main(["--validate", str(bad_file)]), 1)
            self.assertEqual(instance_kit.main(["--validate", str(Path(tmp) / "missing.json")]), 2)


if __name__ == "__main__":
    unittest.main()
