#!/usr/bin/env python3
"""Unit tests untuk tools/evo_scaffold.py (WS-F #16)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import evo_scaffold


class TestEvoScaffold(unittest.TestCase):
    def test_creates_three_scaffold_artifacts_and_prevents_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "evo_0008"
            report = evo_scaffold.scaffold_evo(
                evo_id="EVO_0008",
                out_dir=out_dir,
                title="Uji distilasi pola multi-lengan",
                author="Ian",
                date_str="2026-11-17",
                claim="Lengan ter-distilasi mengungguli baseline pada korpus probe.",
            )

            self.assertEqual(report["schema"], "ace.evo-scaffold.v1")
            prereg = Path(report["files"]["preregistration_md"])
            manifest = Path(report["files"]["stage_manifest_json"])
            hook = Path(report["files"]["census_hook_json"])

            self.assertTrue(prereg.is_file())
            self.assertTrue(manifest.is_file())
            self.assertTrue(hook.is_file())

            md_text = prereg.read_text(encoding="utf-8")
            self.assertIn("# PREREGISTRASI EVO_0008 — DRAF", md_text)
            self.assertIn("## §1 Klaim yang diuji", md_text)
            self.assertIn("## §5 Ikatan tetap", md_text)

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_data["schema"], "ace.stage-verify.v1")
            self.assertEqual(manifest_data["files"], [])

            hook_data = json.loads(hook.read_text(encoding="utf-8"))
            self.assertEqual(hook_data["schema"], "ace.evo-census-hook.v1")
            self.assertIs(hook_data["enabled"], False)
            self.assertIs(hook_data["fail_closed"], True)
            self.assertIs(hook_data["writeback_during_probe"], False)

            with self.assertRaises(evo_scaffold.EvoScaffoldError):
                evo_scaffold.scaffold_evo(evo_id="EVO_0008", out_dir=out_dir)

            report_forced = evo_scaffold.scaffold_evo(
                evo_id="EVO_0008",
                out_dir=out_dir,
                date_str="2026-11-18",
                force=True,
            )
            self.assertEqual(report_forced["created_date"], "2026-11-18")

    def test_cli_validation_and_bad_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "evo_0009"
            rc = evo_scaffold.main(
                [
                    "--evo-id",
                    "EVO_0009",
                    "--out-dir",
                    str(out_dir),
                    "--date",
                    "2026-11-17",
                    "--arms",
                    "SEEDED",
                    "KOSONG",
                    "RANDOM",
                ]
            )
            self.assertEqual(rc, 0)
            hook = json.loads((out_dir / "census_hook.json").read_text(encoding="utf-8"))
            self.assertEqual(hook["arms"], ["SEEDED", "KOSONG", "RANDOM"])

            rc_bad_id = evo_scaffold.main(["--evo-id", "../bad", "--out-dir", tmp])
            self.assertEqual(rc_bad_id, 2)

            rc_bad_band = evo_scaffold.main(
                ["--evo-id", "EVO_0010", "--out-dir", tmp, "--min-score", "80", "--max-score", "40"]
            )
            self.assertEqual(rc_bad_band, 2)

    def test_deterministic_byte_identical_two_runs_api_and_cli(self) -> None:
        """Dua kali pemanggilan dengan parameter sama menghasilkan output byte-identik."""
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as tmp:
            dir_a = Path(tmp) / "run_a"
            dir_b = Path(tmp) / "run_b"

            rep_a = evo_scaffold.scaffold_evo(
                evo_id="EVO_0001",
                out_dir=dir_a,
                title="Uji deterministik",
                author="Ian",
                date_str="2026-11-19",
                claim="Klaim deterministik",
                min_score=40,
                max_score=70,
                arms=("SEEDED", "KOSONG"),
                delivery_gate=0.8,
                min_probe_episodes=12,
                max_waves=3,
            )
            rep_b = evo_scaffold.scaffold_evo(
                evo_id="EVO_0001",
                out_dir=dir_b,
                title="Uji deterministik",
                author="Ian",
                date_str="2026-11-19",
                claim="Klaim deterministik",
                min_score=40,
                max_score=70,
                arms=("SEEDED", "KOSONG"),
                delivery_gate=0.8,
                min_probe_episodes=12,
                max_waves=3,
            )

            self.assertEqual(rep_a["summary"], rep_b["summary"])
            for key in ("preregistration_md", "stage_manifest_json", "census_hook_json"):
                bytes_a = Path(rep_a["files"][key]).read_bytes()
                bytes_b = Path(rep_b["files"][key]).read_bytes()
                self.assertEqual(bytes_a, bytes_b, f"Non-deterministic bytes for {key}")

            # Verifikasi CLI stdout & file output juga byte-identik antar dua run
            cli_a = Path(tmp) / "cli_a"
            cli_b = Path(tmp) / "cli_b"
            buf_a, buf_b = io.StringIO(), io.StringIO()
            args_tpl = [
                "--evo-id",
                "EVO_9999",
                "--date",
                "2026-11-19",
                "--title",
                "Uji batas atas 9999",
            ]
            with contextlib.redirect_stdout(buf_a):
                rc_a = evo_scaffold.main(args_tpl + ["--out-dir", str(cli_a)])
            with contextlib.redirect_stdout(buf_b):
                rc_b = evo_scaffold.main(args_tpl + ["--out-dir", str(cli_b)])
            self.assertEqual(rc_a, 0)
            self.assertEqual(rc_b, 0)
            for fname in ("PREREGISTRASI_EVO_9999_DRAF.md", "manifest.json", "census_hook.json"):
                self.assertEqual((cli_a / fname).read_bytes(), (cli_b / fname).read_bytes())

    def test_four_digit_boundaries_0001_to_9999_and_parameter_range_rejection(self) -> None:
        """Batas nomor evo 4-digit 0001 dan 9999 diterima; parameter di luar rentang ditolak."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for valid_id in ("EVO_0001", "EVO_0008", "EVO_9999", "evo_0042"):
                out_dir = tmp_path / valid_id.lower()
                rep = evo_scaffold.scaffold_evo(evo_id=valid_id, out_dir=out_dir, date_str="2026-11-19")
                self.assertEqual(rep["evo_id"], valid_id)
                self.assertTrue((out_dir / f"PREREGISTRASI_{valid_id.upper()}_DRAF.md").is_file())

            # ID sintaks invalid & panjang melampaui batas
            for bad_id in ("", "   ", "A", "../escape", "EVO 0008", "X" * 65, 123):
                with self.assertRaises(evo_scaffold.EvoScaffoldError):
                    evo_scaffold.normalize_evo_id(bad_id)  # type: ignore[arg-type]

            # Rentang parameter numerik dan arms tidak valid
            invalid_kwargs_list = [
                {"min_score": -1, "max_score": 50},
                {"min_score": 10, "max_score": 101},
                {"min_score": 70, "max_score": 60},
                {"delivery_gate": -0.01},
                {"delivery_gate": 1.01},
                {"min_probe_episodes": 0},
                {"max_waves": 0},
                {"arms": ("ONLY_ONE",)},
                {"arms": ("SEEDED", "   ")},
            ]
            for idx, kwargs in enumerate(invalid_kwargs_list):
                with self.assertRaises(evo_scaffold.EvoScaffoldError):
                    evo_scaffold.scaffold_evo(
                        evo_id="EVO_0100",
                        out_dir=tmp_path / f"bad_param_{idx}",
                        date_str="2026-11-19",
                        **kwargs,
                    )

    def test_does_not_overwrite_existing_full_or_partial_scaffold(self) -> None:
        """Menolak menimpa scaffold yang sudah ada (penuh maupun parsial) tanpa --force."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 1) Full collision: semua berkas tetap utuh byte-identik
            full_dir = tmp_path / "full"
            evo_scaffold.scaffold_evo(evo_id="EVO_0011", out_dir=full_dir, date_str="2026-11-19", title="Asli")
            sentinel_prereg = (full_dir / "PREREGISTRASI_EVO_0011_DRAF.md").read_bytes()
            sentinel_manifest = (full_dir / "manifest.json").read_bytes()
            sentinel_hook = (full_dir / "census_hook.json").read_bytes()

            with self.assertRaises(evo_scaffold.EvoScaffoldError):
                evo_scaffold.scaffold_evo(evo_id="EVO_0011", out_dir=full_dir, date_str="2026-11-20", title="Timpa")
            self.assertEqual((full_dir / "PREREGISTRASI_EVO_0011_DRAF.md").read_bytes(), sentinel_prereg)
            self.assertEqual((full_dir / "manifest.json").read_bytes(), sentinel_manifest)
            self.assertEqual((full_dir / "census_hook.json").read_bytes(), sentinel_hook)
            self.assertEqual(
                evo_scaffold.main(["--evo-id", "EVO_0011", "--out-dir", str(full_dir), "--date", "2026-11-20"]),
                2,
            )

            # 2) Partial collision: hanya manifest.json atau hanya census_hook.json sudah ada ->
            # gagal atomik dan tidak menulis dua berkas lainnya.
            for existing_name in ("manifest.json", "census_hook.json", "PREREGISTRASI_EVO_0012_DRAF.md"):
                partial_dir = tmp_path / f"partial_{existing_name}"
                partial_dir.mkdir(parents=True)
                marker = b"DO-NOT-OVERWRITE\n"
                (partial_dir / existing_name).write_bytes(marker)

                with self.assertRaises(evo_scaffold.EvoScaffoldError):
                    evo_scaffold.scaffold_evo(evo_id="EVO_0012", out_dir=partial_dir, date_str="2026-11-19")
                self.assertEqual((partial_dir / existing_name).read_bytes(), marker)
                for other in ("manifest.json", "census_hook.json", "PREREGISTRASI_EVO_0012_DRAF.md"):
                    if other != existing_name:
                        self.assertFalse((partial_dir / other).exists(), f"{other} should not be created")

    def test_expected_failure_rejects_out_of_range_evo_numbers_and_non_4digit_ids(self) -> None:
        """Bug D3 yang sudah diperbaiki (2026-11-20): `normalize_evo_id` dulu
        memakai regex bebas sehingga menerima `EVO_0000`, `EVO_10000`,
        `EVO_8`, dan `EVO_123`. Kini formatnya ketat EVO_NNNN, 0001..9999.
        """
        for invalid_evo in ("EVO_0000", "EVO_10000", "EVO_8", "EVO_123"):
            with self.assertRaises(evo_scaffold.EvoScaffoldError, msg=f"Harusnya ditolak: {invalid_evo}"):
                evo_scaffold.normalize_evo_id(invalid_evo)

    def test_expected_failure_rejects_duplicate_arms(self) -> None:
        """Bug D3 yang sudah diperbaiki (2026-11-20): `scaffold_evo` kini
        menolak daftar `--arms` duplikat seperti `('SEEDED', 'SEEDED')`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(evo_scaffold.EvoScaffoldError):
                evo_scaffold.scaffold_evo(
                    evo_id="EVO_0015",
                    out_dir=Path(tmp) / "dup_arms",
                    arms=("SEEDED", "SEEDED"),
                    date_str="2026-11-19",
                )


if __name__ == "__main__":
    unittest.main()
