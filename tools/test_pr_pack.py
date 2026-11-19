#!/usr/bin/env python3
"""Tes unit untuk `tools/pr_pack.py` (Gelombang C6).

Memastikan bundel deskripsi draft PR memuat seluruh bagian templat rumah
(`Apa yang dibangun`, `Kenapa`, `Cara menjalankan tes`, `Hasil tes terakhir`),
tabel berkas manifest C5, peringatan allowlist, serta berjalan murni dry-run.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.pr_pack import (
    PR_PACK_SCHEMA,
    REQUIRED_TEMPLATE_HEADINGS,
    PrPackError,
    pack_pr_description,
)


class PrPackTests(unittest.TestCase):
    def _sample_c5_manifest(self, *, with_warning: bool = True) -> dict:
        files = [
            {
                "path": "handover/CATATAN_UJI.md",
                "status": "A",
                "classification": "handover",
                "size_bytes": 128,
                "sha256": "a" * 64,
                "in_allowlist": True,
                "forbidden_rule": None,
                "warnings": [],
            },
            {
                "path": "evidence/hasil_uji.json",
                "status": "M",
                "classification": "evidence",
                "size_bytes": 512,
                "sha256": "b" * 64,
                "in_allowlist": True,
                "forbidden_rule": None,
                "warnings": [],
            },
        ]
        warnings = []
        if with_warning:
            files.append(
                {
                    "path": "tools/pr_pack.py",
                    "status": "A",
                    "classification": "lainnya",
                    "size_bytes": 2048,
                    "sha256": "c" * 64,
                    "in_allowlist": False,
                    "forbidden_rule": None,
                    "warnings": ["di luar allowlist program (handover/, evidence/)"],
                }
            )
            warnings.append(
                {
                    "path": "tools/pr_pack.py",
                    "status": "A",
                    "classification": "lainnya",
                    "forbidden_rule": None,
                    "reasons": ["di luar allowlist program (handover/, evidence/)"],
                }
            )
        return {
            "schema": "ace.release-manifest.v1",
            "base_ref": "main",
            "head_ref": "HEAD",
            "branch": "gravity/pr-pack",
            "base_sha": "1af87a6" + "0" * 33,
            "merge_base_sha": "1af87a6" + "0" * 33,
            "head_sha": "9988776" + "0" * 33,
            "manifest_sha256": "d" * 64,
            "summary": {
                "changed_file_count": len(files),
                "total_size_bytes": sum(f["size_bytes"] for f in files),
                "warning_count": len(warnings),
            },
            "warnings": warnings,
            "files": files,
        }

    def test_fixture_bundle_contains_all_house_template_sections_and_manifest_details(self) -> None:
        manifest = self._sample_c5_manifest(with_warning=True)
        bundle = pack_pr_description(
            manifest,
            title="[Gravity][C6] Pengemas Draft PR Dry-Run",
            what=["`tools/pr_pack.py`: pembungkus deskripsi draft PR dari manifest C5."],
            why=["Menyeragamkan deskripsi draft PR secara luring sebelum review manusia."],
            test_commands=["python3 -m unittest tools.test_pr_pack -v"],
            test_results=["Ran 3 tests — OK"],
            notes=["Mode murni dry-run tanpa panggilan jaringan."],
        )

        self.assertEqual(bundle["schema"], PR_PACK_SCHEMA)
        self.assertTrue(bundle["dry_run_only"])
        self.assertEqual(bundle["network_calls"], 0)
        self.assertFalse(bundle["git_push_executed"])
        self.assertFalse(bundle["pr_created"])
        self.assertTrue(bundle["required_headings_present"])

        md = bundle["markdown"]
        for heading in REQUIRED_TEMPLATE_HEADINGS:
            self.assertIn(heading, md)
        self.assertIn("## Catatan interpretasi", md)
        self.assertIn("DRY-RUN SAJA", md)
        self.assertIn("`handover/CATATAN_UJI.md`", md)
        self.assertIn("`evidence/hasil_uji.json`", md)
        self.assertIn("`tools/pr_pack.py`", md)
        self.assertIn("di luar allowlist program", md)

    def test_cli_bundles_markdown_and_json_from_manifest_and_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            manifest_path = tmp_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(self._sample_c5_manifest(with_warning=False)),
                encoding="utf-8",
            )
            meta_path = tmp_dir / "meta.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "title": "[Gravity] Paket Uji Bersih",
                        "apa": ["Tambah catatan handover"],
                        "kenapa": ["Dokumentasi serah terima"],
                        "tes": ["python3 -m unittest discover -s tools"],
                        "hasil": ["Semua tes lulus"],
                    }
                ),
                encoding="utf-8",
            )
            out_md = tmp_dir / "pr_body.md"
            out_json = tmp_dir / "pr_bundle.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.pr_pack",
                    "--manifest",
                    str(manifest_path),
                    "--meta",
                    str(meta_path),
                    "--out",
                    str(out_md),
                    "--json-out",
                    str(out_json),
                    "--strict",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            md_text = out_md.read_text(encoding="utf-8")
            for heading in REQUIRED_TEMPLATE_HEADINGS:
                self.assertIn(heading, md_text)
            self.assertIn("Tidak ada peringatan jalur", md_text)
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(loaded["dry_run_only"])
            self.assertEqual(loaded["warning_count"], 0)

    def test_rejects_missing_template_sections_or_empty_manifest(self) -> None:
        with self.assertRaises(PrPackError):
            pack_pr_description(
                {"files": []},
                title="Judul",
                what=["a"],
                why=["b"],
                test_commands=["c"],
                test_results=["d"],
            )
        with self.assertRaises(PrPackError):
            pack_pr_description(
                self._sample_c5_manifest(),
                title="Judul",
                what=[],
                why=["b"],
                test_commands=["c"],
                test_results=["d"],
            )


if __name__ == "__main__":
    unittest.main()
