"""Tes fixture untuk tools/discriminating_candidate_factory.py (D9)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import corpus_lint
from tools import discriminating_candidate_factory as dcf
from tools.corpus_factory_lang import verify_constraint_spec


class DiscriminatingCandidateFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_01_fixture_candidates_pass_internal_checks_exact_constraints_and_schema(self) -> None:
        res = dcf.generate_discriminating_candidates(
            lang_count=8,
            code_count=8,
            seed=4242,
            lang_prefix="UJI_ID_",
            code_prefix="UJI_PY_",
        )
        self.assertEqual(res["total_episodes"], 16)
        self.assertEqual(res["language_count"], 8)
        self.assertEqual(res["code_count"], 8)
        self.assertEqual(len(res["episodes"]), 16)

        ids = [ep["id"] for ep in res["episodes"]]
        self.assertEqual(len(ids), len(set(ids)))

        for ep in res["episodes"]:
            self.assertEqual(set(ep.keys()), {"id", "kind", "task_kind", "instruction"})
            self.assertEqual(ep["kind"], "episode")
            self.assertIn(ep["task_kind"], ("language", "code"))
            if ep["task_kind"] == "language":
                self.assertTrue(ep["id"].startswith("UJI_ID_"))
            else:
                self.assertTrue(ep["id"].startswith("UJI_PY_"))

        # Language candidates must carry TEPAT 5 mechanical constraints and pass corpus_factory_lang check.
        for item in res["language_specs"]:
            spec = item["spec"]
            active = [k for k in dcf.LANGUAGE_CONSTRAINT_KEYS if spec.get(k) not in (None, {}, [], "")]
            self.assertEqual(len(active), 5)
            ver = verify_constraint_spec(item["reference_answer"], spec)
            self.assertTrue(ver["passed"], ver)

        # Code candidates must carry >=4 simultaneous hard constraints embedded in instruction.
        ep_by_id = {ep["id"]: ep for ep in res["episodes"]}
        for item in res["code_specs"]:
            self.assertGreaterEqual(item["constraint_count"], 4)
            cc = item["code_constraints"]
            present = [k for k in dcf.CODE_CONSTRAINT_KEYS if cc.get(k)]
            self.assertGreaterEqual(len(present), 4)
            instr = ep_by_id[item["id"]]["instruction"]
            self.assertIn(cc["exact_signature"], instr)
            self.assertIn(cc["complexity_bound"], instr)
            self.assertIn(cc["return_contract"], instr)
            for banned in cc["forbidden_constructs"]:
                self.assertIn(banned, instr)

        # Validate generated JSONL lines with corpus_lint structural validator too.
        lint_rep = corpus_lint.lint_lines(
            res["jsonl_text"].splitlines(),
            prefixes=["UJI_ID_", "UJI_PY_"],
        )
        self.assertTrue(lint_rep["valid"], lint_rep["violations"])

    def test_02_same_seed_two_runs_produce_byte_identical_jsonl(self) -> None:
        out_a = self.root / "run_a.jsonl"
        out_b = self.root / "run_b.jsonl"
        meta_a = self.root / "meta_a.json"
        meta_b = self.root / "meta_b.json"

        buf_a = io.StringIO()
        buf_b = io.StringIO()
        with contextlib.redirect_stdout(buf_a):
            rc_a = dcf.main([
                "--out", str(out_a),
                "--meta-out", str(meta_a),
                "--lang-count", "6",
                "--code-count", "6",
                "--seed", "991177",
            ])
        with contextlib.redirect_stdout(buf_b):
            rc_b = dcf.main([
                "--out", str(out_b),
                "--meta-out", str(meta_b),
                "--lang-count", "6",
                "--code-count", "6",
                "--seed", "991177",
            ])

        self.assertEqual(rc_a, 0)
        self.assertEqual(rc_b, 0)
        bytes_a = out_a.read_bytes()
        bytes_b = out_b.read_bytes()
        self.assertEqual(bytes_a, bytes_b)
        self.assertEqual(meta_a.read_bytes(), meta_b.read_bytes())

    def test_03_failing_internal_candidates_are_rejected_and_never_written(self) -> None:
        bad_lang_4_constraints = {
            "task_kind": "language",
            "domain": "bad_domain",
            "instruction": "Hanya empat kendala dengan frasa `alpha` dan `beta` serta dilarang `rusak`.",
            "reference_answer": "Alpha dan beta hadir utuh.",
            "constraint_spec": {
                "episode_id": "",
                "word_count": {"exact": 5},
                "sentence_count": {"exact": 1},
                "required_phrases": ["Alpha", "beta"],
                "forbidden_affix_roots": ["rusak"],
                # required_order omitted intentionally -> only 4 constraints!
            },
        }
        bad_code_forbidden_import = {
            "task_kind": "code",
            "family": "bad_code",
            "signature_name": "uji_larang",
            "instruction": (
                "def uji_larang(x): O(n) heapq return int docstring Bahasa Indonesia"
            ),
            "reference_code": "import heapq\ndef uji_larang(x):\n    '''Dokumentasi singkat tidak lengkap.'''\n    return 1\n",
            "smoke_check": lambda ns: True,
            "code_constraints": {
                "exact_signature": "def uji_larang(x):",
                "complexity_bound": "O(n)",
                "forbidden_constructs": ["heapq"],
                "return_contract": "return int",
                "indonesian_docstring": "docstring Bahasa Indonesia",
            },
        }

        res = dcf.generate_discriminating_candidates(
            lang_count=2,
            code_count=2,
            seed=1234,
            injected_bad_candidates=[bad_lang_4_constraints, bad_code_forbidden_import],
        )
        self.assertEqual(res["total_episodes"], 4)
        self.assertGreaterEqual(res["rejected_count"], 2)
        all_text = res["jsonl_text"]
        self.assertNotIn("Hanya empat kendala", all_text)
        self.assertNotIn("def uji_larang(x):", all_text)

    def test_04_output_is_always_new_file_refusing_overwrite(self) -> None:
        existing = self.root / "existing.jsonl"
        existing.write_text("KEEP_ME\n", encoding="utf-8")

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc = dcf.main([
                "--out", str(existing),
                "--lang-count", "2",
                "--code-count", "2",
            ])
        self.assertEqual(rc, 2)
        self.assertEqual(existing.read_text(encoding="utf-8"), "KEEP_ME\n")

    def test_05_validation_rejects_same_prefix_and_bad_counts(self) -> None:
        with self.assertRaises(dcf.DiscriminatingFactoryError):
            dcf.generate_discriminating_candidates(
                lang_count=2,
                code_count=2,
                lang_prefix="SAMA_",
                code_prefix="SAMA_",
            )
        with self.assertRaises(dcf.DiscriminatingFactoryError):
            dcf.generate_discriminating_candidates(lang_count=0, code_count=0)
        with self.assertRaises(dcf.DiscriminatingFactoryError):
            dcf.generate_discriminating_candidates(lang_count=-1, code_count=2)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
