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

    def test_byte_identical_roundtrip_binary_empty_and_weird_paths_dir_and_targz(self) -> None:
        """Bundel utuh (biner 256-byte, file kosong, spasi, unicode) lolos byte-identik."""
        all_bytes = bytes(range(256))
        weird_files = {
            "folder spasi/berkas uji satu.bin": all_bytes + b"\x00\xff\xfe",
            "arsip_unicode/naskah_éàü_日本語.md": "Halo dunia — catatan Unicode 🚀\n".encode("utf-8"),
            "kosong/empty_file.dat": b"",
            "dalam/sub satu/sub dua/data.json": b'{"k":"v","n":[1,2,3]}\n',
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "sumber spasi"
            for rel, content in weird_files.items():
                fp = src / rel
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(content)

            include_roots = ["folder spasi", "arsip_unicode", "kosong", "dalam"]

            # 1) Format direktori
            dir_bundle = tmp_path / "bundel spasi"
            pack_dir = portability_pack.pack_bundle(
                source_dir=src,
                out_path=dir_bundle,
                include_paths=include_roots,
                label="uji-unicode-spasi",
            )
            self.assertEqual(pack_dir["file_count"], len(weird_files))
            self.assertEqual(pack_dir["total_bytes"], sum(len(v) for v in weird_files.values()))

            ver_dir, _ = portability_pack.verify_bundle(dir_bundle)
            self.assertTrue(ver_dir["ok"], ver_dir)
            self.assertEqual(ver_dir["verified_count"], len(weird_files))
            self.assertEqual(ver_dir["missing"], [])
            self.assertEqual(ver_dir["extra"], [])
            self.assertEqual(ver_dir["corrupted"], [])

            dest_dir = tmp_path / "tujuan spasi"
            unpack_dir = portability_pack.unpack_bundle(bundle_path=dir_bundle, dest_dir=dest_dir)
            self.assertEqual(unpack_dir["restored_count"], len(weird_files))
            for rel, expected in weird_files.items():
                self.assertEqual((dest_dir / rel).read_bytes(), expected)

            # 2) Format .tar.gz
            tar_bundle = tmp_path / "bundel_unicode_é.tar.gz"
            pack_tar = portability_pack.pack_bundle(
                source_dir=src,
                out_path=tar_bundle,
                include_paths=include_roots,
            )
            self.assertEqual(pack_tar["manifest_sha256"], pack_dir["manifest_sha256"])

            ver_tar, _ = portability_pack.verify_bundle(tar_bundle)
            self.assertTrue(ver_tar["ok"], ver_tar)

            dest_tar = tmp_path / "tujuan_tar"
            unpack_tar = portability_pack.unpack_bundle(bundle_path=tar_bundle, dest_dir=dest_tar)
            self.assertEqual(unpack_tar["restored_count"], len(weird_files))
            for rel, expected in weird_files.items():
                self.assertEqual((dest_tar / rel).read_bytes(), expected)

    def test_single_byte_tampering_caught_with_same_size_in_dir_and_targz(self) -> None:
        """Satu byte diubah (ukuran tetap sama) tertangkap pada payload dan manifest."""
        import io

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            src.mkdir()
            (src / "alpha.bin").write_bytes(b"ABCDEFGH")
            (src / "beta.bin").write_bytes(b"12345678")

            # A) 1 byte flip di payload direktori (panjang tetap 8 byte)
            dir_bundle = tmp_path / "dir_bundle"
            portability_pack.pack_bundle(source_dir=src, out_path=dir_bundle, include_paths=["alpha.bin", "beta.bin"])
            (dir_bundle / "payload" / "alpha.bin").write_bytes(b"ABCDEPGH")  # F -> P

            rep_dir, _ = portability_pack.verify_bundle(dir_bundle)
            self.assertFalse(rep_dir["ok"])
            self.assertEqual(len(rep_dir["corrupted"]), 1)
            self.assertEqual(rep_dir["corrupted"][0]["path"], "alpha.bin")
            self.assertEqual(rep_dir["corrupted"][0]["expected_bytes"], 8)
            self.assertEqual(rep_dir["corrupted"][0]["actual_bytes"], 8)
            self.assertEqual(rep_dir["verified_count"], 1)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.unpack_bundle(bundle_path=dir_bundle, dest_dir=tmp_path / "out_fail_1")

            # B) 1 byte flip di manifest.json (manifest_sha256 tidak cocok)
            dir_bundle_man = tmp_path / "dir_bundle_man"
            portability_pack.pack_bundle(source_dir=src, out_path=dir_bundle_man, include_paths=["alpha.bin"])
            man_path = dir_bundle_man / "manifest.json"
            man_obj = json.loads(man_path.read_text(encoding="utf-8"))
            man_obj["files"][0]["bytes"] = 999
            man_path.write_text(json.dumps(man_obj), encoding="utf-8")
            rep_man, _ = portability_pack.verify_bundle(dir_bundle_man)
            self.assertFalse(rep_man["ok"])
            self.assertIn("manifest_sha256_mismatch", rep_man["errors"])

            # C) 1 byte flip di payload arsip .tar.gz
            tar_bundle = tmp_path / "orig.tar.gz"
            portability_pack.pack_bundle(source_dir=src, out_path=tar_bundle, include_paths=["alpha.bin", "beta.bin"])
            tampered_tar = tmp_path / "tampered.tar.gz"
            with tarfile.open(tar_bundle, "r:gz") as tf_in, tarfile.open(tampered_tar, "w:gz") as tf_out:
                for member in tf_in.getmembers():
                    data = tf_in.extractfile(member).read() if member.isfile() else b""
                    if member.name == "payload/beta.bin":
                        data = b"12345679"  # 8 -> 9 (1 byte diubah)
                    info = tarfile.TarInfo(name=member.name)
                    info.size = len(data)
                    info.mode = member.mode
                    tf_out.addfile(info, io.BytesIO(data))
            rep_tar, _ = portability_pack.verify_bundle(tampered_tar)
            self.assertFalse(rep_tar["ok"])
            self.assertEqual(len(rep_tar["corrupted"]), 1)
            self.assertEqual(rep_tar["corrupted"][0]["path"], "beta.bin")
            self.assertEqual(portability_pack.main(["--verify", "--bundle", str(tampered_tar)]), 1)

    def test_missing_and_extra_files_caught_in_dir_and_targz(self) -> None:
        """Berkas hilang dan berkas berlebih tertangkap pada bundel direktori dan .tar.gz."""
        import io

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            src.mkdir()
            (src / "satu.txt").write_text("1", encoding="utf-8")
            (src / "dua.txt").write_text("2", encoding="utf-8")

            # 1) Direktori: hapus 1 file + tambah 1 file ekstra
            dir_bundle = tmp_path / "dir_me"
            portability_pack.pack_bundle(source_dir=src, out_path=dir_bundle, include_paths=["satu.txt", "dua.txt"])
            (dir_bundle / "payload" / "dua.txt").unlink()
            (dir_bundle / "payload" / "penyusup.txt").write_text("extra", encoding="utf-8")

            rep_dir, _ = portability_pack.verify_bundle(dir_bundle)
            self.assertFalse(rep_dir["ok"])
            self.assertEqual(rep_dir["missing"], ["dua.txt"])
            self.assertEqual(rep_dir["extra"], ["penyusup.txt"])
            self.assertEqual(rep_dir["verified_count"], 1)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.unpack_bundle(bundle_path=dir_bundle, dest_dir=tmp_path / "dest_me")

            # 2) .tar.gz: hapus satu.txt, tambah payload/extra.txt dan anggota luar payload/
            tar_orig = tmp_path / "orig.tar.gz"
            portability_pack.pack_bundle(source_dir=src, out_path=tar_orig, include_paths=["satu.txt", "dua.txt"])
            tar_mod = tmp_path / "mod.tar.gz"
            with tarfile.open(tar_orig, "r:gz") as tf_in, tarfile.open(tar_mod, "w:gz") as tf_out:
                for member in tf_in.getmembers():
                    if member.name == "payload/satu.txt":
                        continue
                    data = tf_in.extractfile(member).read()
                    info = tarfile.TarInfo(name=member.name)
                    info.size = len(data)
                    tf_out.addfile(info, io.BytesIO(data))
                for extra_name in ("payload/extra.txt", "outside_payload.txt"):
                    edata = b"x"
                    info = tarfile.TarInfo(name=extra_name)
                    info.size = len(edata)
                    tf_out.addfile(info, io.BytesIO(edata))

            rep_tar, _ = portability_pack.verify_bundle(tar_mod)
            self.assertFalse(rep_tar["ok"])
            self.assertEqual(rep_tar["missing"], ["satu.txt"])
            self.assertEqual(rep_tar["extra"], ["extra.txt"])
            self.assertIn("unexpected_archive_member:outside_payload.txt", rep_tar["errors"])

    def test_symlinks_and_unsafe_paths_and_corrupt_bundles_handled_without_crash(self) -> None:
        """Symlink (sumber, dalam bundel, tujuan), path tak aman, dan arsip rusak ditangani bersih."""
        import io

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "src"
            (src / "sub").mkdir(parents=True)
            real_target = tmp_path / "outside_secret.txt"
            real_target.write_text("RAHASIA", encoding="utf-8")
            (src / "ok.txt").write_text("ok", encoding="utf-8")

            # A) Symlink file di source_dir
            sym_file = src / "sub" / "link.txt"
            sym_file.symlink_to(real_target)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=src, out_path=tmp_path / "b_sym1", include_paths=["sub"])
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=src, out_path=tmp_path / "b_sym2", include_paths=["sub/link.txt"])
            sym_file.unlink()

            # B) Symlink direktori + dangling symlink di source_dir
            sym_dir = src / "sub" / "dirlink"
            sym_dir.symlink_to(tmp_path)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=src, out_path=tmp_path / "b_sym3", include_paths=["sub"])
            sym_dir.unlink()

            dangling = src / "sub" / "dangling"
            dangling.symlink_to(tmp_path / "does_not_exist")
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=src, out_path=tmp_path / "b_sym4", include_paths=["sub"])
            dangling.unlink()

            # C) Symlink sebagai source_dir atau dest_dir
            sym_src = tmp_path / "sym_src"
            sym_src.symlink_to(src)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=sym_src, out_path=tmp_path / "b_sym5", include_paths=["ok.txt"])

            good_bundle = tmp_path / "good_bundle"
            portability_pack.pack_bundle(source_dir=src, out_path=good_bundle, include_paths=["ok.txt"])

            sym_dest = tmp_path / "sym_dest"
            sym_dest.symlink_to(tmp_path)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.unpack_bundle(bundle_path=good_bundle, dest_dir=sym_dest)

            # D) Symlink disuntikkan ke dalam bundel direktori -> verify_bundle tidak crash, ok=False
            evil_dir_bundle = tmp_path / "evil_dir_bundle"
            portability_pack.pack_bundle(source_dir=src, out_path=evil_dir_bundle, include_paths=["ok.txt"], force=True)
            (evil_dir_bundle / "payload" / "evil_sym").symlink_to(real_target)
            rep_evil_dir, _ = portability_pack.verify_bundle(evil_dir_bundle)
            self.assertFalse(rep_evil_dir["ok"])
            self.assertIn("symlink_in_bundle:evil_sym", rep_evil_dir["errors"])

            # E) Symlink disuntikkan ke dalam .tar.gz -> verify_bundle tidak crash, ok=False
            evil_tar = tmp_path / "evil_sym.tar.gz"
            with tarfile.open(evil_tar, "w:gz") as tf:
                man = json.dumps(
                    {"schema": "ace.portability-pack.v1", "manifest_sha256": "0", "files": []}
                ).encode("utf-8")
                ti_m = tarfile.TarInfo("manifest.json")
                ti_m.size = len(man)
                tf.addfile(ti_m, io.BytesIO(man))
                ti_s = tarfile.TarInfo("payload/link")
                ti_s.type = tarfile.SYMTYPE
                ti_s.linkname = "/etc/passwd"
                tf.addfile(ti_s)
            rep_evil_tar, _ = portability_pack.verify_bundle(evil_tar)
            self.assertFalse(rep_evil_tar["ok"])
            self.assertIn("symlink_in_archive:payload/link", rep_evil_tar["errors"])

            # F) Path tidak aman dan arsip korup -> error bersih tanpa crash
            for bad_rel in ("", "   ", "/abs/path", "C:\\win\\path", "a/../b", "a\x00b", "."):
                with self.assertRaises(portability_pack.PortabilityPackError):
                    portability_pack.normalize_rel_path(bad_rel)

            corrupt_tar = tmp_path / "corrupt.tar.gz"
            corrupt_tar.write_bytes(b"not-a-valid-gzip-or-tar-archive")
            self.assertEqual(portability_pack.main(["--verify", "--bundle", str(corrupt_tar)]), 2)

            # G) Penolakan overwrite tanpa --force dan keberhasilan dengan --force
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.pack_bundle(source_dir=src, out_path=good_bundle, include_paths=["ok.txt"], force=False)
            dest_once = tmp_path / "dest_once"
            portability_pack.unpack_bundle(bundle_path=good_bundle, dest_dir=dest_once, force=False)
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.unpack_bundle(bundle_path=good_bundle, dest_dir=dest_once, force=False)
            res_forced = portability_pack.unpack_bundle(bundle_path=good_bundle, dest_dir=dest_once, force=True)
            self.assertTrue(res_forced["ok"])


if __name__ == "__main__":
    unittest.main()
