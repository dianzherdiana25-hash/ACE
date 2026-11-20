"""Tes verifikasi manifes kustodi: lengkap, kurang satu, satu berubah isi (AG38)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.custody_manifest_check import SCHEMA, verify_custody_manifest


SCRIPT = Path(__file__).with_name("custody_manifest_check.py")


class CustodyManifestCheckTests(unittest.TestCase):
    def _seed_custody(self, root: Path) -> Path:
        (root / "sub").mkdir(parents=True)
        f1 = root / "state.json"
        f2 = root / "sub" / "memory.jsonl"
        f3 = root / "sub" / "meta.json"
        f1.write_text('{"id":1}\n', encoding="utf-8")
        f2.write_text('{"seq":1}\n', encoding="utf-8")
        f3.write_text('{"v":1}\n', encoding="utf-8")

        manifest = root.parent / "custody_manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "files": [
                        {"path": "state.json", "sha256": hashlib.sha256(f1.read_bytes()).hexdigest()},
                        {"path": "sub/memory.jsonl", "sha256": hashlib.sha256(f2.read_bytes()).hexdigest()},
                        {"path": "sub/meta.json", "sha256": hashlib.sha256(f3.read_bytes()).hexdigest()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_complete_missing_one_and_modified_one(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            custody = base / "custody"
            custody.mkdir()
            manifest = self._seed_custody(custody)

            # 1. Lengkap -> semua ok, exit 0
            ok_rep = verify_custody_manifest(manifest, custody)
            self.assertEqual(ok_rep["schema"], SCHEMA)
            self.assertTrue(ok_rep["all_ok"])
            self.assertEqual(ok_rep["summary"], {"total_entries": 3, "ok": 3, "hilang": 0, "hash-berbeda": 0})
            self.assertEqual([f["status"] for f in ok_rep["files"]], ["ok", "ok", "ok"])

            # 2. Kurang satu -> hilang, exit 1
            (custody / "sub" / "meta.json").unlink()
            miss_proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--root", str(custody)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(miss_proc.returncode, 1)
            miss_rep = json.loads(miss_proc.stdout)
            self.assertFalse(miss_rep["all_ok"])
            self.assertEqual({f["path"]: f["status"] for f in miss_rep["files"]}, {
                "state.json": "ok",
                "sub/memory.jsonl": "ok",
                "sub/meta.json": "hilang",
            })

            # 3. Satu berubah isi -> hash-berbeda
            (custody / "sub" / "meta.json").write_text('{"v":1}\n', encoding="utf-8")
            (custody / "state.json").write_text('{"id":999}\n', encoding="utf-8")
            mod_proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--root", str(custody)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(mod_proc.returncode, 1)
            mod_rep = json.loads(mod_proc.stdout)
            self.assertEqual({f["path"]: f["status"] for f in mod_rep["files"]}, {
                "state.json": "hash-berbeda",
                "sub/memory.jsonl": "ok",
                "sub/meta.json": "ok",
            })


if __name__ == "__main__":
    unittest.main()
