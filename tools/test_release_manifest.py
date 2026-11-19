#!/usr/bin/env python3
"""Tes unit untuk `tools/release_manifest.py` (Gelombang C5).

Menggunakan repositori Git sementara untuk memverifikasi daftar berkas berubah
terhadap `main`, kecocokan `sha256` & ukuran byte, klasifikasi jalur
(`handover` / `evidence` / `lainnya`), serta peringatan berkas di luar allowlist
atau menyentuh pola terlarang.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.release_manifest import (
    RELEASE_MANIFEST_SCHEMA,
    build_release_manifest,
    classify_path,
)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


class ReleaseManifestTests(unittest.TestCase):
    def _init_temp_repo(self, root: Path) -> None:
        _git(root, "init", "-b", "main")
        _git(root, "config", "user.name", "Test Builder")
        _git(root, "config", "user.email", "builder@example.invalid")
        (root / "README.md").write_text("# Fixture Repo\n", encoding="utf-8")
        _git(root, "add", "README.md")
        _git(root, "commit", "-m", "init main")

    def test_temp_git_repo_manifest_sha256_classification_and_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._init_temp_repo(repo)

            _git(repo, "checkout", "-b", "gravity/demo-release")

            # 1) Berkas sah dalam allowlist handover/
            handover_bytes = b"Catatan serah terima aman.\n"
            (repo / "handover").mkdir()
            (repo / "handover" / "CATATAN_BARU.md").write_bytes(handover_bytes)

            # 2) Berkas sah dalam allowlist evidence/
            evidence_bytes = b'{"ok": true}\n'
            (repo / "evidence").mkdir()
            (repo / "evidence" / "drill.json").write_bytes(evidence_bytes)

            # 3) Berkas di luar allowlist (lainnya) -> wajib jadi peringatan
            other_bytes = b"print('hi')\n"
            (repo / "tools").mkdir()
            (repo / "tools" / "extra.py").write_bytes(other_bytes)

            # 4) Berkas terlarang di dalam handover/ -> wajib kena warning forbidden_rule
            (repo / "handover" / "LEDGER_PENGHASILAN.md").write_text("private\n", encoding="utf-8")

            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "add fixture files")

            manifest = build_release_manifest(repo, base_ref="main", head_ref="HEAD")
            self.assertEqual(manifest["schema"], RELEASE_MANIFEST_SCHEMA)
            self.assertEqual(manifest["branch"], "gravity/demo-release")
            self.assertEqual(manifest["summary"]["changed_file_count"], 4)
            self.assertEqual(
                manifest["summary"]["classification_counts"],
                {"handover": 2, "evidence": 1, "lainnya": 1},
            )
            self.assertEqual(manifest["summary"]["outside_allowlist_count"], 2)
            self.assertEqual(manifest["summary"]["warning_count"], 2)

            by_path = {entry["path"]: entry for entry in manifest["files"]}
            self.assertEqual(by_path["handover/CATATAN_BARU.md"]["sha256"], hashlib.sha256(handover_bytes).hexdigest())
            self.assertEqual(by_path["handover/CATATAN_BARU.md"]["size_bytes"], len(handover_bytes))
            self.assertTrue(by_path["handover/CATATAN_BARU.md"]["in_allowlist"])
            self.assertEqual(by_path["handover/CATATAN_BARU.md"]["classification"], "handover")

            self.assertEqual(by_path["evidence/drill.json"]["sha256"], hashlib.sha256(evidence_bytes).hexdigest())
            self.assertTrue(by_path["evidence/drill.json"]["in_allowlist"])
            self.assertEqual(by_path["evidence/drill.json"]["classification"], "evidence")

            self.assertEqual(by_path["tools/extra.py"]["classification"], "lainnya")
            self.assertFalse(by_path["tools/extra.py"]["in_allowlist"])
            self.assertTrue(by_path["tools/extra.py"]["warnings"])

            self.assertEqual(by_path["handover/LEDGER_PENGHASILAN.md"]["forbidden_rule"], "private_income_ledger")
            self.assertFalse(by_path["handover/LEDGER_PENGHASILAN.md"]["in_allowlist"])

            # Deterministik antar dua pemanggilan
            manifest_again = build_release_manifest(repo, base_ref="main", head_ref="HEAD")
            self.assertEqual(manifest["manifest_sha256"], manifest_again["manifest_sha256"])

    def test_cli_fail_on_warnings_and_clean_allowlist_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._init_temp_repo(repo)
            _git(repo, "checkout", "-b", "gravity/clean-only")
            (repo / "evidence").mkdir()
            (repo / "evidence" / "ok.txt").write_text("clean\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "clean evidence")

            out_json = Path(tmp) / "manifest.json"
            p_ok = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.release_manifest",
                    "--repo",
                    str(repo),
                    "--base",
                    "main",
                    "--head",
                    "HEAD",
                    "--out",
                    str(out_json),
                    "--fail-on-warnings",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["summary"]["warning_count"], 0)
            self.assertEqual(classify_path("handover/a.md"), "handover")
            self.assertEqual(classify_path("evidence/b.json"), "evidence")
            self.assertEqual(classify_path("code/x.py"), "lainnya")

            # Tambahkan berkas di luar allowlist -> --fail-on-warnings harus keluar dengan kode 1
            (repo / "outside.txt").write_text("warn\n", encoding="utf-8")
            _git(repo, "add", "outside.txt")
            _git(repo, "commit", "-m", "outside")
            p_warn = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.release_manifest",
                    "--repo",
                    str(repo),
                    "--fail-on-warnings",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p_warn.returncode, 1, p_warn.stderr)


if __name__ == "__main__":
    unittest.main()
