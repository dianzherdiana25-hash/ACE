"""Tes integrasi wiring F3: kbm_pipeline <-> cover_check, pack_evidence, portability_pack <-> instance_kit."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools import (
    instance_kit,
    kbm_pipeline,
    pack_evidence,
    portability_pack,
)


def _valid_png_bytes(width: int = 800, height: int = 1200, pad_bytes: int = 1200) -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_len = struct.pack(">I", 13)
    ihdr_tag = b"IHDR"
    ihdr_body = struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"
    return header + ihdr_len + ihdr_tag + ihdr_body + (b"\x00" * pad_bytes)


def _words(n: int, prefix: str = "kata") -> str:
    return " ".join(f"{prefix}{i}" for i in range(1, n + 1))


class TestF3KbmPortabilityWiring(unittest.TestCase):
    def test_kbm_pipeline_strict_cover_seal_and_portable_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manuscript = base / "naskah.md"
            manuscript.write_text(
                "# Bab 1: Permulaan\n" + _words(110, "awal") + "\n\n# Bab 2: Klimaks\n" + _words(120, "tengah") + "\n",
                encoding="utf-8",
            )
            cover_src = base / "cover_valid.png"
            cover_src.write_bytes(_valid_png_bytes(800, 1200, pad_bytes=1200))

            out_dir = base / "pkg"
            bundle_dir = base / "upload_bundle"
            tar_out = base / "portable.tar.gz"

            rc = kbm_pipeline.main(
                [
                    str(manuscript),
                    "--output-dir",
                    str(out_dir),
                    "--cover-file",
                    str(cover_src),
                    "--bundle-dir",
                    str(bundle_dir),
                    "--min-words",
                    "100",
                    "--min-bytes",
                    "400",
                    "--strict-cover",
                    "--seal-bundle",
                    "--portable-bundle",
                    str(tar_out),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue((bundle_dir / "upload_manifest.json").is_file())
            self.assertTrue((bundle_dir / "manifest.json").is_file())
            ev = pack_evidence.verify_evidence(bundle_dir)
            self.assertTrue(ev["valid"])

            ver_tar, _ = portability_pack.verify_bundle(tar_out)
            self.assertTrue(ver_tar["ok"])

            restored = base / "restored"
            portability_pack.unpack_bundle(bundle_path=tar_out, dest_dir=restored)
            self.assertTrue((restored / "manifest.json").is_file())
            self.assertTrue((restored / "ch_001_permulaan.md").is_file())
            self.assertTrue(pack_evidence.verify_evidence(restored)["valid"])

    def test_strict_cover_rejects_bad_dimensions_before_staging_and_seal_requires_bundle_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manuscript = base / "naskah.md"
            manuscript.write_text("# Bab 1: Satu\n" + _words(110, "kata") + "\n", encoding="utf-8")
            bad_cover = base / "bad_cover.png"
            # Lebar 100px < min_width default (600px) -> ditolak cover_check
            bad_cover.write_bytes(_valid_png_bytes(100, 200, pad_bytes=1200))

            bundle_dir = base / "blocked_bundle"
            report = kbm_pipeline.run_pipeline(
                manuscript,
                base / "out_bad",
                cover_source=bad_cover,
                bundle_dir=bundle_dir,
                min_words=100,
                min_bytes=400,
                strict_cover=True,
                seal_bundle=True,
            )
            self.assertFalse(report["passed"])
            self.assertFalse(report["cover_valid"])
            self.assertEqual(report["failed_stage"], "cover")
            self.assertFalse(report["bundle"]["staged"])
            self.assertFalse((bundle_dir / "manifest.json").exists())

            with self.assertRaises(kbm_pipeline.KbmPipelineError):
                kbm_pipeline.run_pipeline(
                    manuscript,
                    base / "out_no_bundle",
                    seal_bundle=True,
                )

    def test_portability_pack_enforces_instance_kit_isolation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "src"
            src.mkdir()
            (src / "state.json").write_text('{"ok": true}\n', encoding="utf-8")

            cfg1 = instance_kit.build_instance_config(instance_id="inst-a", base_dir=base / "runs", port_base=8100)
            cfg2 = instance_kit.build_instance_config(instance_id="inst-b", base_dir=base / "runs", port_base=8200)
            p1 = base / "inst-a.json"
            p2 = base / "inst-b.json"
            p1.write_text(json.dumps(cfg1), encoding="utf-8")
            p2.write_text(json.dumps(cfg2), encoding="utf-8")

            tar_ok = base / "inst.tar.gz"
            rc_ok = portability_pack.main(
                [
                    "--pack",
                    "--source-dir",
                    str(src),
                    "--bundle",
                    str(tar_ok),
                    "--paths",
                    "state.json",
                    "--instance-configs",
                    str(p1),
                    str(p2),
                ]
            )
            self.assertEqual(rc_ok, 0)

            rc_unpack = portability_pack.main(
                [
                    "--unpack",
                    "--bundle",
                    str(tar_ok),
                    "--dest-dir",
                    str(base / "dest_ok"),
                    "--instance-configs",
                    str(p1),
                    str(p2),
                ]
            )
            self.assertEqual(rc_unpack, 0)

            # Tabrakan port memaksa pack/unpack batal fail-closed (exit 2)
            cfg_collide = instance_kit.build_instance_config(instance_id="inst-c", base_dir=base / "runs", port_base=8100)
            pc = base / "inst-c.json"
            pc.write_text(json.dumps(cfg_collide), encoding="utf-8")

            rc_bad = portability_pack.main(
                [
                    "--unpack",
                    "--bundle",
                    str(tar_ok),
                    "--dest-dir",
                    str(base / "dest_blocked"),
                    "--instance-configs",
                    str(p1),
                    str(pc),
                ]
            )
            self.assertEqual(rc_bad, 2)
            self.assertFalse((base / "dest_blocked").exists())


if __name__ == "__main__":
    unittest.main()
