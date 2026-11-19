#!/usr/bin/env python3
"""Tes unit & CLI untuk `tools/candidate_factory_v2.py` (Garis B1)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import candidate_factory_v2 as cf2
from tools.corpus_lint import lint_lines, load_frozen_prefixes


class TestCandidateFactoryV2(unittest.TestCase):
    def test_default_bundle_passes_lint_and_verifies_all_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "bundle"
            result = cf2.generate_candidate_v2_bundle(
                out_dir,
                id_lang_count=12,
                ml_lang_count=10,
                code_count=12,
                constraints_per_episode=6,
            )
            census = result["readiness_census"]
            self.assertEqual(census["total_written"], 34)
            self.assertEqual(census["total_rejected_not_written"], 0)
            self.assertTrue(census["multilingual_rule_satisfied"])
            self.assertGreaterEqual(census["multilingual_language_count"], 4)
            self.assertEqual(set(census["waves"]), {"id_layered", "multilingual_wave", "code_composite"})

            lines = (out_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 34)
            self.assertTrue(lint_lines(lines)["valid"])

            # Verifikasi seluruh sidecar bahasa & kode terhadap sampel & instruksi
            lang_specs = [json.loads(l) for l in (out_dir / "lang_specs.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lang_specs), 22)
            for spec in lang_specs:
                sample = (out_dir / "lang_samples" / f"{spec['episode_id']}.txt").read_text(encoding="utf-8").strip()
                ver = cf2.verify_layered_lang_spec(sample, spec)
                self.assertTrue(ver["passed"], f"{spec['episode_id']} gagal: {ver}")
                self.assertEqual(ver["constraint_count"], 6)

            code_specs = [json.loads(l) for l in (out_dir / "code_specs.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(code_specs), 12)
            ep_by_id = {json.loads(l)["id"]: json.loads(l) for l in lines}
            for cspec in code_specs:
                cver = cf2.verify_composite_code_spec(ep_by_id[cspec["episode_id"]], cspec)
                self.assertTrue(cver["passed"], f"{cspec['episode_id']} gagal: {cver}")

    def test_configurable_constraint_layer_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for level in (2, 3, 4, 5, 6):
                out_dir = Path(tmp) / f"lvl_{level}"
                cf2.generate_candidate_v2_bundle(
                    out_dir,
                    id_lang_count=4,
                    ml_lang_count=5,
                    code_count=3,
                    constraints_per_episode=level,
                )
                specs = [json.loads(l) for l in (out_dir / "lang_specs.jsonl").read_text(encoding="utf-8").splitlines()]
                for sp in specs:
                    self.assertEqual(sp["constraint_count"], level)
                    self.assertEqual(sp["active_layers"], list(cf2.CONSTRAINT_LAYERS[:level]))

    def test_multilingual_requires_at_least_four_languages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "too_few_langs"
            with self.assertRaises(cf2.CandidateFactoryV2Error):
                cf2.generate_candidate_v2_bundle(
                    out_dir,
                    id_lang_count=2,
                    ml_lang_count=6,
                    code_count=2,
                    languages=("id", "en", "es"),
                )
            self.assertFalse((out_dir / "episodes.jsonl").exists())

    def test_verifier_catches_multilingual_inflections_and_surface_hygiene(self) -> None:
        base_spec = {
            "episode_id": "ml_en_test",
            "language": "en",
            "active_layers": list(cf2.CONSTRAINT_LAYERS),
            "word_count": {"exact": 10},
            "sentence_count": {"exact": 2},
            "required_phrases": ["mirror dome balanced", "clean stream"],
            "forbidden_roots": ["crash", "blur"],
            "required_order": ["twilight check", "capture ready"],
            "surface_hygiene": {"forbid_digits": True, "max_word_len": 20, "closing_token": "ready."},
        }
        good = "First twilight check keeps mirror dome balanced. The clean stream capture ready."
        base_spec["word_count"]["exact"] = len(cf2.tokenize_words(good))
        self.assertTrue(cf2.verify_layered_lang_spec(good, base_spec)["passed"])

        bad_inflection = "First twilight check keeps mirror dome balanced. Crashing stream capture ready."
        base_spec_inf = dict(base_spec, word_count={"exact": len(cf2.tokenize_words(bad_inflection))})
        res_inf = cf2.verify_layered_lang_spec(bad_inflection, base_spec_inf)
        self.assertFalse(res_inf["passed"])
        self.assertFalse(res_inf["checks"]["forbidden_words"]["passed"])

        bad_digit = "First twilight check keeps 2 mirror dome balanced. The clean stream capture ready."
        base_spec_dig = dict(base_spec, word_count={"exact": len(cf2.tokenize_words(bad_digit))})
        res_dig = cf2.verify_layered_lang_spec(bad_digit, base_spec_dig)
        self.assertFalse(res_dig["passed"])
        self.assertFalse(res_dig["checks"]["surface_hygiene"]["passed"])

    def test_failed_candidate_never_written_strict_and_filter_modes(self) -> None:
        bad_candidate = {
            "episode": {
                "id": "grav_lang_id_999",
                "kind": "episode",
                "task_kind": "language",
                "instruction": "Contoh gagal cek mekanis.",
            },
            "spec": {
                "schema": cf2.LANG_SPEC_V2_SCHEMA,
                "episode_id": "grav_lang_id_999",
                "language": "id",
                "active_layers": ["word_count", "required_phrases"],
                "word_count": {"exact": 99},
                "required_phrases": ["frasa satu", "frasa dua"],
            },
            "sample": "Hanya empat kata saja.",
            "wave_id": "id_layered",
            "language": "id",
        }
        with tempfile.TemporaryDirectory() as tmp:
            strict_dir = Path(tmp) / "strict"
            with self.assertRaises(cf2.CandidateFactoryV2Error):
                cf2.generate_candidate_v2_bundle(
                    strict_dir,
                    id_lang_count=2,
                    ml_lang_count=5,
                    code_count=2,
                    injected_candidates=[bad_candidate],
                    strict_fail_closed=True,
                )
            self.assertFalse((strict_dir / "episodes.jsonl").exists())

            filter_dir = Path(tmp) / "filtered"
            out = cf2.generate_candidate_v2_bundle(
                filter_dir,
                id_lang_count=2,
                ml_lang_count=5,
                code_count=2,
                injected_candidates=[bad_candidate],
                strict_fail_closed=False,
            )
            census = out["readiness_census"]
            self.assertEqual(census["total_written"], 9)
            self.assertEqual(census["total_rejected_not_written"], 1)
            written_ids = {json.loads(l)["id"] for l in (filter_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines()}
            self.assertNotIn("grav_lang_id_999", written_ids)

    def test_frozen_collision_rejected_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dir1 = Path(tmp) / "b1"
            dir2 = Path(tmp) / "b2"
            r1 = cf2.generate_candidate_v2_bundle(dir1, id_lang_count=4, ml_lang_count=5, code_count=4)
            r2 = cf2.generate_candidate_v2_bundle(dir2, id_lang_count=4, ml_lang_count=5, code_count=4)
            self.assertEqual(
                r1["readiness_census"]["episodes_sha256"],
                r2["readiness_census"]["episodes_sha256"],
            )

            # Simulasi korpus beku dengan awalan 60 karakter identik -> wajib ditolak sebelum menulis
            first_ep = (dir1 / "episodes.jsonl").read_text(encoding="utf-8").splitlines()[0]
            frozen_file = Path(tmp) / "frozen_sim.jsonl"
            frozen_file.write_text(first_ep + "\n", encoding="utf-8")
            dir3 = Path(tmp) / "b3"
            with self.assertRaises(cf2.CandidateFactoryV2Error):
                cf2.generate_candidate_v2_bundle(
                    dir3,
                    id_lang_count=4,
                    ml_lang_count=5,
                    code_count=4,
                    frozen_paths=[frozen_file],
                )
            self.assertFalse((dir3 / "episodes.jsonl").exists())

    def test_no_overlap_with_repo_frozen_corpora_and_cli(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        handover_corpora = sorted((repo_root / "handover").glob("*CORPUS*.jsonl"))
        self.assertTrue(handover_corpora)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "cli_out"
            cmd = [
                sys.executable,
                "-m",
                "tools.candidate_factory_v2",
                "--output-dir",
                str(out_dir),
                "--id-lang-count",
                "6",
                "--ml-lang-count",
                "5",
                "--code-count",
                "6",
                "--constraints-per-episode",
                "5",
            ]
            for cp in handover_corpora:
                cmd.extend(["--frozen", str(cp)])
            proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["readiness_census"]["total_written"], 17)
            self.assertGreater(len(cf2._load_frozen_prefix_index(handover_corpora)), 0)

            bad = subprocess.run(
                [sys.executable, "-m", "tools.candidate_factory_v2", "--output-dir", str(out_dir), "--constraints-per-episode", "9"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad.returncode, 2)

    def test_vacuous_spec_gate_rejects_empty_and_foreign_keys_only(self) -> None:
        """Regresi D4: spec kosong & kunci asing/typo ditolak eksplisit; spec valid tetap lolos."""
        sample_text = "Operator memeriksa jalur cadangan pagi ini. Sensor stabil tanpa gangguan."
        # 1) Spec kosong -> gagal dengan alasan eksplisit di JSON
        res_empty = cf2.verify_layered_lang_spec(sample_text, {})
        self.assertFalse(res_empty["passed"])
        self.assertIn("vacuous_spec", res_empty.get("reason", ""))
        self.assertEqual(res_empty["checks"], {})

        # 2) Spec berisi kunci asing saja (baik tanpa active_layers maupun typo di active_layers) -> gagal
        res_foreign = cf2.verify_layered_lang_spec(sample_text, {"kunci_asing": 123, "typo_count": 9})
        self.assertFalse(res_foreign["passed"])
        self.assertIn("vacuous_spec", res_foreign.get("reason", ""))

        res_typo_layer = cf2.verify_layered_lang_spec(
            sample_text,
            {"active_layers": ["word_cunt_typo"], "word_cunt_typo": {"exact": 10}},
        )
        self.assertFalse(res_typo_layer["passed"])
        self.assertIn("vacuous_spec", res_typo_layer.get("reason", ""))

        # 3) Spec valid -> tetap lolos persis seperti sebelumnya tanpa field reason tambahan
        valid_spec = {
            "episode_id": "reg-ok",
            "language": "id",
            "active_layers": ["word_count", "sentence_count"],
            "word_count": {"exact": len(cf2.tokenize_words(sample_text))},
            "sentence_count": {"exact": len(cf2.split_sentences(sample_text))},
        }
        res_ok = cf2.verify_layered_lang_spec(sample_text, valid_spec)
        self.assertTrue(res_ok["passed"])
        self.assertNotIn("reason", res_ok)
        self.assertTrue(res_ok["checks"]["word_count"]["passed"])
        self.assertTrue(res_ok["checks"]["sentence_count"]["passed"])


if __name__ == "__main__":
    unittest.main()
