#!/usr/bin/env python3
"""Unit tests untuk tools/corpus_factory_lang.py (WS-B #5)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.corpus_factory_lang import (
    CONSTRAINT_SPEC_SCHEMA,
    CorpusFactoryLangError,
    FACTORY_LANG_SCHEMA,
    generate_lang_episodes,
    main,
    verify_constraint_spec,
)
from tools.corpus_lint import lint_lines


class TestCorpusFactoryLang(unittest.TestCase):
    def test_generate_determinism_specs_and_verified_samples(self) -> None:
        r1 = generate_lang_episodes(count=24, prefix="lang_gen_", seed=20261117)
        r2 = generate_lang_episodes(count=24, prefix="lang_gen_", seed=20261117)
        self.assertEqual(r1["schema"], FACTORY_LANG_SCHEMA)
        self.assertEqual(r1["lines"], r2["lines"])
        self.assertEqual(len(r1["lines"]), 24)
        self.assertTrue(r1["lint_ok"])
        self.assertTrue(r1["all_samples_verified"])

        lint = lint_lines(r1["lines"], prefixes=["lang_gen_"])
        self.assertTrue(lint["valid"])

        for ep_line, spec, sample in zip(r1["lines"], r1["specs"], r1["samples"]):
            ep = json.loads(ep_line)
            self.assertEqual(ep["kind"], "episode")
            self.assertEqual(ep["task_kind"], "language")
            self.assertEqual(spec["schema"], CONSTRAINT_SPEC_SCHEMA)
            self.assertEqual(ep["id"], spec["episode_id"])
            self.assertEqual(ep["id"], sample["episode_id"])
            self.assertTrue(verify_constraint_spec(sample["answer_text"], spec)["passed"])

    def test_constraint_verifier_detects_all_failure_modes(self) -> None:
        res = generate_lang_episodes(count=4, prefix="chk_", seed=10)
        spec = res["specs"][0]
        good_text = res["samples"][0]["answer_text"]
        self.assertTrue(verify_constraint_spec(good_text, spec)["passed"])

        # 1. Salah jumlah kata.
        bad_wc = verify_constraint_spec(good_text + " tambahan", spec)
        self.assertFalse(bad_wc["passed"])
        self.assertFalse(bad_wc["checks"]["word_count"]["passed"])

        # 2. Salah jumlah kalimat.
        bad_sc = verify_constraint_spec(good_text.rstrip(".") + ". Kalimat ekstra.", spec)
        self.assertFalse(bad_sc["passed"])
        self.assertFalse(bad_sc["checks"]["sentence_count"]["passed"])

        # 3. Frasa wajib hilang.
        p1 = spec["required_phrases"][0]
        bad_phrase = verify_constraint_spec(good_text.replace(p1, "frasa pengganti"), spec)
        self.assertFalse(bad_phrase["passed"])
        self.assertFalse(bad_phrase["checks"]["required_phrases"]["passed"])

        # 4. Kata terlarang berimbuhan Indonesia terdeteksi (mem-/di-/ter-/pe- + akar).
        forb_root = spec["forbidden_affix_roots"][0]
        affixed = f"di{forb_root}kan"
        injected_forb = good_text.split(" ", 1)[1] + f" {affixed}"
        bad_forb = verify_constraint_spec(injected_forb, spec)
        self.assertFalse(bad_forb["passed"])
        self.assertFalse(bad_forb["checks"]["forbidden_words"]["passed"])
        self.assertEqual(bad_forb["checks"]["forbidden_words"]["hits"][0]["matched_root"], forb_root)

        # 5. Urutan fakta terbalik.
        fa, fb = spec["required_order"]
        swapped = good_text.replace(fa, "__TMP_A__").replace(fb, fa).replace("__TMP_A__", fb)
        bad_order = verify_constraint_spec(swapped, spec)
        self.assertFalse(bad_order["passed"])
        self.assertFalse(bad_order["checks"]["required_order"]["passed"])

    def test_prefix60_uniqueness_and_frozen_collision_skip(self) -> None:
        res = generate_lang_episodes(count=80, prefix="u_", seed=55)
        self.assertEqual(len(res["lines"]), 80)
        p60 = {json.loads(line)["instruction"][:60] for line in res["lines"]}
        self.assertEqual(len(p60), 80)

        first_obj = json.loads(res["lines"][0])
        with tempfile.TemporaryDirectory() as tmp:
            frozen_path = Path(tmp) / "frozen_lang.jsonl"
            frozen_path.write_text(json.dumps(first_obj, ensure_ascii=False) + "\n", encoding="utf-8")
            res2 = generate_lang_episodes(count=40, prefix="u_", seed=55, frozen_paths=[frozen_path])
            self.assertGreaterEqual(res2["skipped_frozen_collisions"], 1)
            self.assertTrue(res2["lint_ok"])

    def test_invalid_inputs_and_cli_end_to_end(self) -> None:
        with self.assertRaises(CorpusFactoryLangError):
            generate_lang_episodes(count=0)
        with self.assertRaises(CorpusFactoryLangError):
            generate_lang_episodes(count=5, prefix="")
        with self.assertRaises(CorpusFactoryLangError):
            generate_lang_episodes(count=999, prefix="l_")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            out_jsonl = tmp / "lang_corpus.jsonl"
            spec_dir = tmp / "specs"
            sample_dir = tmp / "samples"
            summary_out = tmp / "summary.json"
            rc = main(
                [
                    "--count",
                    "12",
                    "--prefix",
                    "w5_",
                    "--seed",
                    "123",
                    "--out",
                    str(out_jsonl),
                    "--spec-dir",
                    str(spec_dir),
                    "--sample-dir",
                    str(sample_dir),
                    "--summary-out",
                    str(summary_out),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(out_jsonl.read_text(encoding="utf-8").splitlines()), 12)
            self.assertTrue((spec_dir / "w5_001.spec.json").is_file())
            self.assertTrue((sample_dir / "w5_001.txt").is_file())
            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertTrue(summary["all_samples_verified"])
            self.assertTrue(summary["lint_ok"])

            bad_rc = main(
                [
                    "--count",
                    "4",
                    "--frozen",
                    str(tmp / "nope.jsonl"),
                    "--out",
                    str(out_jsonl),
                    "--spec-dir",
                    str(spec_dir),
                ]
            )
            self.assertEqual(bad_rc, 2)

    def test_verify_constraint_spec_vacuous_gate_empty_and_foreign_keys(self) -> None:
        """Regresi D4: spec kosong dan spec kunci-asing-saja gagal dengan alasan eksplisit."""
        sample = "Kalimat pertama singkat. Kalimat kedua juga singkat."
        res_empty = verify_constraint_spec(sample, {})
        self.assertFalse(res_empty["passed"])
        self.assertIn("vacuous_spec", res_empty.get("reason", ""))

        res_foreign = verify_constraint_spec(sample, {"word_cunt": {"exact": 6}, "kunci_asing": True})
        self.assertFalse(res_foreign["passed"])
        self.assertIn("vacuous_spec", res_foreign.get("reason", ""))


if __name__ == "__main__":
    unittest.main()
