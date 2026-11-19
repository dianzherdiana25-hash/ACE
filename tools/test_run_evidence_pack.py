"""Unit & adversarial tests untuk tools/run_evidence_pack.py (G4)."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import socket
import tarfile
import tempfile
import unittest
from unittest import mock

from tools import run_evidence_pack as rep


class TestRunEvidencePack(unittest.TestCase):
    def test_01_missing_run_dir_arg_fails_closed_no_default_stage_probe(self) -> None:
        # Tidak pernah boleh menebak direktori staging default -> wajib --run-dir
        rc = rep.main([])
        self.assertEqual(rc, 2)

    def test_02_pack_and_verify_deterministic_archive_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_dir = base / "run_001"
            (run_dir / "logs").mkdir(parents=True)
            (run_dir / "summary.json").write_text('{"run":"sample","ok":true}\n', encoding="utf-8")
            (run_dir / "events.jsonl").write_text('{"step":1}\n', encoding="utf-8")
            (run_dir / "logs" / "worker.log").write_text("started clean\n", encoding="utf-8")

            stage_manifest = base / "stage_manifest.json"
            stage_manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "summary.json",
                                "sha256": hashlib.sha256((run_dir / "summary.json").read_bytes()).hexdigest(),
                            },
                            {
                                "path": "events.jsonl",
                                "sha256": hashlib.sha256((run_dir / "events.jsonl").read_bytes()).hexdigest(),
                            },
                            {
                                "path": "logs/worker.log",
                                "sha256": hashlib.sha256((run_dir / "logs" / "worker.log").read_bytes()).hexdigest(),
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            tar_a = base / "pack_a.tar.gz"
            tar_b = base / "pack_b.tar.gz"
            meta_out = base / "pack_meta.json"

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rc1 = rep.main(
                    [
                        "--run-dir",
                        str(run_dir),
                        "--stage-manifest",
                        str(stage_manifest),
                        "--archive",
                        str(tar_a),
                        "--meta-out",
                        str(meta_out),
                    ]
                )
            self.assertEqual(rc1, 0)
            self.assertTrue((run_dir / "manifest.json").is_file())
            self.assertTrue(tar_a.is_file())
            meta = json.loads(meta_out.read_text(encoding="utf-8"))
            self.assertEqual(meta["schema"], rep.RUN_PACK_SCHEMA)
            self.assertEqual(meta["secret_scan"]["status"], "CLEAN")
            self.assertEqual(meta["categories"], {"json": 1, "jsonl": 1, "logs": 1})

            # Pack ulang deterministik pada berkas sama harus menghasilkan SHA tar.gz identik
            rc2 = rep.main(["--run-dir", str(run_dir), "--archive", str(tar_b)])
            self.assertEqual(rc2, 0)
            self.assertEqual(
                hashlib.sha256(tar_a.read_bytes()).hexdigest(),
                hashlib.sha256(tar_b.read_bytes()).hexdigest(),
            )

            # --verify bersih -> exit 0
            self.assertEqual(
                rep.main(["--run-dir", str(run_dir), "--archive", str(tar_a), "--verify"]),
                0,
            )

            # Tamper isi direktori -> --verify wajib exit 2
            (run_dir / "logs" / "worker.log").write_text("tampered\n", encoding="utf-8")
            self.assertEqual(
                rep.main(["--run-dir", str(run_dir), "--archive", str(tar_a), "--verify"]),
                2,
            )

    def test_03_secret_leak_scan_blocks_pack_and_symlink_and_tar_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_dir = base / "run_secret"
            run_dir.mkdir()
            fake_token = "AIza" + "B" * 30
            (run_dir / "debug.log").write_text(f"KEY={fake_token}\n", encoding="utf-8")

            # Fail-closed bila ada indikasi token tanpa --allow-unredacted
            rc_blocked = rep.main(["--run-dir", str(run_dir)])
            self.assertEqual(rc_blocked, 2)
            self.assertFalse((run_dir / "manifest.json").exists())

            # Dapat diizinkan secara eksplisit dengan --allow-unredacted tetapi preview tetap termask
            res = rep.pack_run_evidence(run_dir, allow_unredacted=True)
            self.assertEqual(res["secret_scan"]["status"], "WARN_UNREDACTED")
            self.assertEqual(res["secret_scan"]["finding_count"], 1)
            self.assertNotIn(fake_token, json.dumps(res))

            # Uji tar traversal di arsip jahat saat verify
            evil_tar = base / "evil.tar.gz"
            with tarfile.open(evil_tar, "w:gz") as tf:
                ti = tarfile.TarInfo(name="../escape.txt")
                ti.size = 3
                tf.addfile(ti, io.BytesIO(b"bad"))
            with self.assertRaises(rep.RunEvidencePackError):
                rep.verify_run_evidence(run_dir, archive_path=evil_tar)

            # Symlink dalam run_dir wajib ditolak
            sym_dir = base / "run_sym"
            sym_dir.mkdir()
            outside = base / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            os.symlink(outside, sym_dir / "link.txt")
            with self.assertRaises(rep.RunEvidencePackError):
                rep.pack_run_evidence(sym_dir)


if __name__ == "__main__":
    unittest.main()
