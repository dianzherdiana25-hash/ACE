"""Uji unit untuk perakit dan pemverifikasi bundel evidence tools/pack_evidence.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.pack_evidence import EvidencePackError, pack_evidence, verify_evidence

REPO_ROOT = Path(__file__).resolve().parents[1]


class PackEvidenceTests(unittest.TestCase):
    """Kumpulan pengujian perakitan manifest, verifikasi utuh, dan deteksi tamper."""

    def _make_sample_run(self, root: Path) -> None:
        (root / "sub").mkdir(parents=True, exist_ok=True)
        (root / "verdict.json").write_text('{"status": "ok"}\n', encoding="utf-8")
        (root / "run.log").write_bytes(b"baris log 1\nbaris log 2\n")
        (root / "sub" / "trace.jsonl").write_text('{"step": 1}\n', encoding="utf-8")

    def test_pack_and_verify_intact_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_01"
            run_dir.mkdir()
            self._make_sample_run(run_dir)

            pack_res = pack_evidence(run_dir)
            self.assertEqual(pack_res["file_count"], 3)
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([f["path"] for f in manifest["files"]], ["run.log", "sub/trace.jsonl", "verdict.json"])

            verify_res = verify_evidence(run_dir)
            self.assertTrue(verify_res["valid"])
            self.assertEqual(verify_res["missing"], [])
            self.assertEqual(verify_res["modified"], [])

    def test_single_byte_modification_caught_and_cli_exits_2(self) -> None:
        script = REPO_ROOT / "tools" / "pack_evidence.py"
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_02"
            run_dir.mkdir()
            self._make_sample_run(run_dir)
            pack_evidence(run_dir)

            # Ubah tepat satu byte pada berkas biner/log.
            log_path = run_dir / "run.log"
            raw = bytearray(log_path.read_bytes())
            raw[0] ^= 0x01
            log_path.write_bytes(bytes(raw))

            proc = subprocess.run(
                [sys.executable, str(script), str(run_dir), "--verify"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            out = json.loads(proc.stdout)
            self.assertFalse(out["valid"])
            self.assertEqual(len(out["modified"]), 1)
            self.assertEqual(out["modified"][0]["path"], "run.log")

    def test_missing_file_caught_with_exit_2(self) -> None:
        script = REPO_ROOT / "tools" / "pack_evidence.py"
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_03"
            run_dir.mkdir()
            self._make_sample_run(run_dir)
            pack_evidence(run_dir)

            (run_dir / "sub" / "trace.jsonl").unlink()

            proc = subprocess.run(
                [sys.executable, str(script), str(run_dir), "--verify"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            out = json.loads(proc.stdout)
            self.assertFalse(out["valid"])
            self.assertEqual(out["missing"], ["sub/trace.jsonl"])

    def test_repack_excludes_manifest_itself_and_missing_manifest_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_04"
            run_dir.mkdir()
            self._make_sample_run(run_dir)
            with self.assertRaises(EvidencePackError):
                verify_evidence(run_dir)

            pack_evidence(run_dir)
            pack_res2 = pack_evidence(run_dir)
            self.assertEqual(pack_res2["file_count"], 3)
            self.assertTrue(verify_evidence(run_dir)["valid"])

    def test_fuzz_hardening_null_byte_path_and_huge_int_manifest_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_05"
            run_dir.mkdir()
            (run_dir / "a.txt").write_text("ok", encoding="utf-8")
            manifest = Path(tmp) / "bad_manifest.json"

            manifest.write_text(
                json.dumps(
                    {
                        "schema": "ace.evidence-bundle.v1",
                        "files": [{"path": "bad\x00path.txt", "size_bytes": 2, "sha256": "0" * 64}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(EvidencePackError):
                verify_evidence(run_dir, manifest_path=manifest)

            manifest.write_text(
                '{"schema": "ace.evidence-bundle.v1", "files": [{"path": "a.txt", "size_bytes": '
                + ("9" * 5000)
                + ', "sha256": "'
                + ("0" * 64)
                + '"}]}',
                encoding="utf-8",
            )
            with self.assertRaises(EvidencePackError):
                verify_evidence(run_dir, manifest_path=manifest)

    def test_extra_file_invalidates_bundle_and_exits_2(self) -> None:
        script = REPO_ROOT / "tools" / "pack_evidence.py"
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run_06"
            run_dir.mkdir()
            self._make_sample_run(run_dir)
            pack_evidence(run_dir)

            (run_dir / "unlisted_extra.txt").write_text("tamper", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(script), str(run_dir), "--verify"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            out = json.loads(proc.stdout)
            self.assertFalse(out["valid"])
            self.assertEqual(out["extra_files"], ["unlisted_extra.txt"])


if __name__ == "__main__":
    unittest.main()
