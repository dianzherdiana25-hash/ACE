#!/usr/bin/env python3
"""Unit tests untuk tools/portability_pack.py (WS-H #20)."""

from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools import portability_pack


class TestPortabilityPack(unittest.TestCase):
    def test_pack_verify_and_unpack_roundtrip_dir_and_targz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "source"
            (src / "evidence").mkdir(parents=True)
            (src / "evidence" / "state.json").write_text('{"ok": true}\n', encoding="utf-8")
            (src / "notes.md").write_text("# Notes\n", encoding="utf-8")

            dir_bundle = tmp_path / "bundle_dir"
            pack_res = portability_pack.pack_bundle(
                source_dir=src,
                out_path=dir_bundle,
                include_paths=["evidence", "notes.md"],
            )
            self.assertEqual(pack_res["schema"], "ace.portability-pack.v1")
            self.assertIs(pack_res["foundation_only"], True)
            self.assertEqual(pack_res["file_count"], 2)

            ver_ok, _ = portability_pack.verify_bundle(dir_bundle)
            self.assertTrue(ver_ok["ok"])
            self.assertEqual(ver_ok["verified_count"], 2)

            dest_dir = tmp_path / "restored_from_dir"
            unpack_res = portability_pack.unpack_bundle(bundle_path=dir_bundle, dest_dir=dest_dir)
            self.assertEqual(unpack_res["restored_count"], 2)
            self.assertEqual(
                (dest_dir / "evidence" / "state.json").read_text(encoding="utf-8"),
                '{"ok": true}\n',
            )

            tar_bundle = tmp_path / "bundle.tar.gz"
            rc_pack = portability_pack.main(
                [
                    "--pack",
                    "--source-dir",
                    str(src),
                    "--bundle",
                    str(tar_bundle),
                    "--paths",
                    "evidence",
                    "notes.md",
                ]
            )
            self.assertEqual(rc_pack, 0)
            self.assertEqual(portability_pack.main(["--verify", "--bundle", str(tar_bundle)]), 0)
            dest_tar = tmp_path / "restored_from_tar"
            self.assertEqual(
                portability_pack.main(
                    ["--unpack", "--bundle", str(tar_bundle), "--dest-dir", str(dest_tar)]
                ),
                0,
            )
            self.assertEqual((dest_tar / "notes.md").read_text(encoding="utf-8"), "# Notes\n")

    def test_rejects_tampered_payload_and_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "source"
            src.mkdir()
            (src / "a.txt").write_text("hello", encoding="utf-8")

            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(
                    source_dir=src,
                    out_path=tmp_path / "bad_bundle",
                    include_paths=["../escape.txt"],
                )

            bundle = tmp_path / "bundle_dir"
            portability_pack.pack_bundle(source_dir=src, out_path=bundle, include_paths=["a.txt"])
            (bundle / "payload" / "a.txt").write_text("tampered!", encoding="utf-8")

            rc_ver = portability_pack.main(["--verify", "--bundle", str(bundle)])
            self.assertEqual(rc_ver, 1)

            rc_unpack = portability_pack.main(
                ["--unpack", "--bundle", str(bundle), "--dest-dir", str(tmp_path / "out")]
            )
            self.assertEqual(rc_unpack, 2)
            self.assertFalse((tmp_path / "out" / "a.txt").exists())

            # Pastikan arsip dengan path traversal ditolak saat verifikasi
            bad_tar = tmp_path / "evil.tar.gz"
            with tarfile.open(bad_tar, "w:gz") as tf:
                manifest_bytes = json.dumps(
                    {
                        "schema": "ace.portability-pack.v1",
                        "manifest_sha256": "deadbeef",
                        "files": [{"path": "../evil.txt", "bytes": 1, "sha256": "00"}],
                    }
                ).encode("utf-8")
                import io

                ti = tarfile.TarInfo("manifest.json")
                ti.size = len(manifest_bytes)
                tf.addfile(ti, io.BytesIO(manifest_bytes))

            ver_bad, _ = portability_pack.verify_bundle(bad_tar)
            self.assertFalse(ver_bad["ok"])


if __name__ == "__main__":
    unittest.main()
