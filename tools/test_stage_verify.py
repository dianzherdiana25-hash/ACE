"""Uji unit untuk verifikator direktori staging tools/stage_verify.py."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.stage_verify import StageVerifyError, verify_stage

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "stage_verify.py"


def _write_staged_files(stage_dir: Path, files: dict[str, bytes]) -> Path:
    manifest_entries = []
    for rel, content in sorted(files.items()):
        target = stage_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest_entries.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    manifest_path = stage_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "stage-manifest.v1", "files": manifest_entries}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


class StageVerifyTests(unittest.TestCase):
    """Pengujian kondisi utuh serta tiga kelas deviasi: missing, extra, dan modified."""

    def test_intact_stage_passes_with_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            _write_staged_files(
                stage,
                {
                    "corpus/w2.jsonl": b'{"id": "1"}\n',
                    "notes/readme.txt": b"siap uji\n",
                },
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(stage)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["valid"])
            self.assertEqual(report["expected_count"], 2)
            self.assertEqual(report["actual_count"], 2)
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["extra"], [])
            self.assertEqual(report["modified"], [])

    def test_missing_file_reported_and_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            _write_staged_files(
                stage,
                {
                    "a.txt": b"alpha",
                    "sub/b.txt": b"bravo",
                },
            )
            (stage / "sub" / "b.txt").unlink()
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(stage)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing"], ["sub/b.txt"])
            self.assertEqual(report["extra"], [])
            self.assertEqual(report["modified"], [])

    def test_extra_file_reported_and_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            _write_staged_files(stage, {"a.txt": b"alpha"})
            (stage / "stray.log").write_bytes(b"unexpected")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(stage)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["extra"], ["stray.log"])
            self.assertEqual(report["modified"], [])

    def test_modified_file_reported_and_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            _write_staged_files(
                stage,
                {
                    "payload.bin": b"0123456789",
                    "same_len.txt": b"abc",
                },
            )
            # Ubah ukuran dan isi pada payload.bin, dan ubah isi saja (ukuran tetap) pada same_len.txt.
            (stage / "payload.bin").write_bytes(b"012345")
            (stage / "same_len.txt").write_bytes(b"abX")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(stage)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing"], [])
            self.assertEqual(report["extra"], [])
            by_path = {m["path"]: m for m in report["modified"]}
            self.assertEqual(set(by_path), {"payload.bin", "same_len.txt"})
            self.assertIn("size_mismatch", by_path["payload.bin"]["reasons"])
            self.assertIn("sha256_mismatch", by_path["payload.bin"]["reasons"])
            self.assertEqual(by_path["same_len.txt"]["reasons"], ["sha256_mismatch"])

    def test_invalid_manifest_or_traversal_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            stage.mkdir()
            bad_manifest = Path(tmp) / "bad_manifest.json"
            bad_manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {"path": "../escape.txt", "sha256": "0" * 64, "size": 1},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(StageVerifyError):
                verify_stage(stage, bad_manifest)

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(stage), "--manifest", str(bad_manifest)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)

    def test_fuzz_hardening_null_byte_path_and_huge_int_rejected_with_stage_verify_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            stage.mkdir()
            (stage / "a.txt").write_bytes(b"ok")
            m = Path(tmp) / "m.json"

            m.write_text(json.dumps({"files": [{"path": "a\x00b.txt", "sha256": "0" * 64}]}), encoding="utf-8")
            with self.assertRaises(StageVerifyError):
                verify_stage(stage, m)

            m.write_text(
                '{"files": [{"path": "a.txt", "sha256": "' + ("0" * 64) + '", "size": ' + ("9" * 5000) + "}]}",
                encoding="utf-8",
            )
            with self.assertRaises(StageVerifyError):
                verify_stage(stage, m)


if __name__ == "__main__":
    unittest.main()
