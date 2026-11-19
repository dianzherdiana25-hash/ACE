#!/usr/bin/env python3
"""Tes unit untuk `tools/second_home.py` (Gelombang C4).

Memastikan generator checklist rumah kedua membaca seluruh langkah, prasyarat,
aset sumber, dan verifikasi murni dari berkas inventaris + kebutuhan fixture
serta menangkap aset yang hilang dari inventaris.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.second_home import (
    SECOND_HOME_SCHEMA,
    SecondHomeError,
    build_checklist,
    load_inventory,
    load_requirements,
    render_markdown,
)


class SecondHomeTests(unittest.TestCase):
    def _write_fixtures(self, tmp_dir: Path, *, include_missing_asset: bool = False) -> tuple[Path, Path]:
        inv_path = tmp_dir / "REPO_INDEX.md"
        inv_path.write_text(
            "\n".join(
                [
                    "# Indeks Repositori — Fixture",
                    "",
                    "### `.` (2 berkas)",
                    "- `pyproject.toml` (data)",
                    "- `README.md` (docs)",
                    "",
                    "### `tools` (3 berkas)",
                    "- `instance_kit.py` (python)",
                    "- `portability_pack.py` (python)",
                    "- `migration_rehearsal.py` (python)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        req_assets_2 = ["tools/portability_pack.py", "tools/migration_rehearsal.py"]
        if include_missing_asset:
            req_assets_2.append("tools/nonexistent_bootstrap.py")

        req_path = tmp_dir / "requirements.json"
        req_path.write_text(
            json.dumps(
                {
                    "target_name": "mesin-cadangan-02",
                    "requirements": [
                        {
                            "id": "isolasi-instans",
                            "name": "Siapkan Konfigurasi Isolasi Instans",
                            "prerequisites": ["Python 3.11+ terpasang", "Direktori kerja kosong tersedia"],
                            "required_assets": ["tools/instance_kit.py", "pyproject.toml"],
                            "steps": [
                                "Bangun konfigurasi instans baru non-aktif dengan instance_kit --init",
                                "Validasi tidak ada tabrakan direktori atau port dengan instance_kit --validate",
                            ],
                            "verification": "python3 tools/instance_kit.py --validate source.json target.json",
                        },
                        {
                            "id": "bor-migrasi",
                            "name": "Jalankan Bor Pemulihan Bundel Portabilitas",
                            "depends_on": ["isolasi-instans"],
                            "prerequisites": ["SHA-256 manifest sumber telah diverifikasi"],
                            "required_assets": req_assets_2,
                            "steps": [
                                "Verifikasi integritas bundel dengan portability_pack --verify",
                                "Jalankan migration_rehearsal ke target sementara",
                            ],
                            "verification": "python3 tools/migration_rehearsal.py bundle.tar.gz source.json target.json --manifest-sha256 <sha>",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return inv_path, req_path

    def test_checklist_contains_all_fixture_steps_prerequisites_and_verifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_path, req_path = self._write_fixtures(Path(tmp))
            inv_paths = load_inventory(inv_path)
            req_doc = load_requirements(req_path)
            plan = build_checklist(
                inv_paths,
                req_doc,
                inventory_source=str(inv_path),
                requirements_source=str(req_path),
            )

            self.assertEqual(plan["schema"], SECOND_HOME_SCHEMA)
            self.assertTrue(plan["foundation_only"])
            self.assertFalse(plan["activation_authorized"])
            self.assertEqual(plan["summary"]["requirement_count"], 2)
            self.assertEqual(plan["summary"]["total_steps"], 4)
            self.assertEqual(plan["summary"]["missing_asset_count"], 0)

            md = render_markdown(plan)
            # Semua langkah kebutuhan fixture dan prasyaratnya hadir dalam checklist Markdown
            self.assertIn("mesin-cadangan-02", md)
            self.assertIn("Python 3.11+ terpasang", md)
            self.assertIn("Direktori kerja kosong tersedia", md)
            self.assertIn("isolasi-instans (Siapkan Konfigurasi Isolasi Instans)", md)
            self.assertIn("SHA-256 manifest sumber telah diverifikasi", md)
            self.assertIn("- [ ] Bangun konfigurasi instans baru non-aktif dengan instance_kit --init", md)
            self.assertIn("- [ ] Jalankan migration_rehearsal ke target sementara", md)
            self.assertIn("python3 tools/instance_kit.py --validate source.json target.json", md)
            self.assertIn("[ADA] `tools/migration_rehearsal.py`", md)

    def test_strict_cli_flags_missing_inventory_asset_and_supports_json_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _, req_path = self._write_fixtures(tmp_dir, include_missing_asset=True)
            json_inv = tmp_dir / "inventory.json"
            json_inv.write_text(
                json.dumps(
                    {
                        "files": [
                            "pyproject.toml",
                            "tools/instance_kit.py",
                            "tools/portability_pack.py",
                            "tools/migration_rehearsal.py",
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_md = tmp_dir / "checklist.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.second_home",
                    "--inventory",
                    str(json_inv),
                    "--requirements",
                    str(req_path),
                    "--output",
                    str(out_md),
                    "--strict",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            md_text = out_md.read_text(encoding="utf-8")
            self.assertIn("[HILANG_DI_INVENTARIS] `tools/nonexistent_bootstrap.py`", md_text)

    def test_rejects_unknown_depends_on_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "bad_req.json"
            req_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "step-a",
                            "name": "Langkah A",
                            "depends_on": ["tidak-ada"],
                            "steps": ["jalankan"],
                            "verification": "ok",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(SecondHomeError):
                load_requirements(req_path)


if __name__ == "__main__":
    unittest.main()
