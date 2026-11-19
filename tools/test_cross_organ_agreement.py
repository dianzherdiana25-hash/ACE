"""Unit & adversarial tests untuk tools/cross_organ_agreement.py (offline, 0 HTTP)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import cross_organ_agreement as coa


class TestCrossOrganAgreement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _write_jsonl(self, name: str, lines: list[object]) -> Path:
        p = self.root / name
        encoded = [ln if isinstance(ln, str) else json.dumps(ln) for ln in lines]
        p.write_text("\n".join(encoded) + "\n", encoding="utf-8")
        return p

    def test_01_answer_normalization_json_numeric_bool_and_whitespace(self):
        self.assertEqual(coa.normalize_answer({"b": 2, "a": 1}), coa.normalize_answer('{"a":1,"b":2}'))
        self.assertEqual(coa.normalize_answer(5.0), coa.normalize_answer(5))
        self.assertEqual(coa.normalize_answer("  Halo   ACE "), coa.normalize_answer("halo ace"))
        self.assertNotEqual(
            coa.normalize_answer("Halo", case_insensitive=False),
            coa.normalize_answer("halo", case_insensitive=False),
        )
        self.assertEqual(coa.normalize_answer(True), "bool:true")

    def test_02_unanimous_cross_provider_agreement_yields_kappa_one(self):
        rows = [
            {"task_id": "t1", "brain_of_origin": "groq/qwen/qwen3.8-27b", "status": "ok", "answer": "42"},
            {"task_id": "t1", "brain_of_origin": "gemini/gemini-3-flash-preview", "status": "ok", "answer": "42"},
            {"task_id": "t2", "brain_of_origin": "groq/qwen/qwen3.8-27b", "status": "ok", "answer": '{"x": 1, "y": 2}'},
            {"task_id": "t2", "brain_of_origin": "gemini/gemini-3-flash-preview", "status": "ok", "answer": {"y": 2, "x": 1}},
        ]
        mat, anom = coa.parse_fixture_records(rows)
        self.assertEqual(anom, [])
        rep = coa.evaluate_cross_organ_agreement(mat, anomalies=anom)
        self.assertEqual(rep["network_calls"], 0)
        self.assertEqual(rep["summary"]["unanimous_tasks"], 2)
        self.assertEqual(rep["summary"]["disagreement_count"], 0)
        self.assertEqual(rep["pairwise"][0]["cohen_kappa"], 1.0)
        self.assertTrue(rep["pairwise"][0]["cross_provider"])

    def test_03_partial_disagreement_majority_vs_split_and_exact_kappa(self):
        # 4 tasks across 3 organs:
        # t1: A agrees with B & C (all X)
        # t2: A & B say Y, C says X (majority Y)
        # t3: A says X, B says Y, C says Z (split)
        # t4: all say Z
        rows = [
            {"task_id": "t1", "organ": "groq/coder", "answer": "X"},
            {"task_id": "t1", "organ": "groq/validator", "answer": "X"},
            {"task_id": "t1", "organ": "gonka/judge", "answer": "X"},
            {"task_id": "t2", "organ": "groq/coder", "answer": "Y"},
            {"task_id": "t2", "organ": "groq/validator", "answer": "Y"},
            {"task_id": "t2", "organ": "gonka/judge", "answer": "X"},
            {"task_id": "t3", "organ": "groq/coder", "answer": "X"},
            {"task_id": "t3", "organ": "groq/validator", "answer": "Y"},
            {"task_id": "t3", "organ": "gonka/judge", "answer": "Z"},
            {"task_id": "t4", "organ": "groq/coder", "answer": "Z"},
            {"task_id": "t4", "organ": "groq/validator", "answer": "Z"},
            {"task_id": "t4", "organ": "gonka/judge", "answer": "Z"},
        ]
        mat, anom = coa.parse_fixture_records(rows)
        rep = coa.evaluate_cross_organ_agreement(mat, anomalies=anom)
        self.assertEqual(rep["summary"]["unanimous_tasks"], 2)
        self.assertEqual(rep["summary"]["majority_tasks"], 1)
        self.assertEqual(rep["summary"]["split_tasks"], 1)
        self.assertEqual(len(rep["pairwise"]), 3)
        by_pair = {(p["organ_a"], p["organ_b"]): p for p in rep["pairwise"]}
        self.assertFalse(by_pair[("groq/coder", "groq/validator")]["cross_provider"])
        self.assertTrue(by_pair[("gonka/judge", "groq/coder")]["cross_provider"])
        self.assertEqual(by_pair[("groq/coder", "groq/validator")]["raw_agreement"], 0.75)

    def test_04_handles_pe_equals_one_constant_label_without_zero_division(self):
        raw_ag, kappa = coa.compute_cohen_kappa([("same", "same"), ("same", "same")])
        self.assertEqual(raw_ag, 1.0)
        self.assertEqual(kappa, 1.0)

        raw_ag2, kappa2 = coa.compute_cohen_kappa([])
        self.assertEqual(raw_ag2, 0.0)
        self.assertIsNone(kappa2)

    def test_05_separates_abstain_error_and_incomplete_tasks(self):
        rows = [
            {"task_id": "t1", "brain_of_origin": "groq/a", "status": "ok", "answer": "yes"},
            {"task_id": "t1", "brain_of_origin": "gemini/b", "status": "abstain"},
            {"task_id": "t2", "brain_of_origin": "groq/a", "status": "unavailable"},
            {"task_id": "t2", "brain_of_origin": "gemini/b", "status": "error"},
            {"task_id": "t3", "brain_of_origin": "groq/a", "status": "ok", "answer": "no"},
        ]
        mat, _ = coa.parse_fixture_records(rows)
        rep = coa.evaluate_cross_organ_agreement(mat)
        self.assertEqual(rep["summary"]["all_abstained_tasks"], 1)
        self.assertEqual(rep["incomplete_tasks"], ["t3"])
        self.assertEqual(rep["pairwise"][0]["shared_ok_tasks"], 0)
        self.assertIsNone(rep["pairwise"][0]["cohen_kappa"])
        self.assertAlmostEqual(rep["organs"]["gemini/b"]["abstention_rate"], 1.0)

    def test_06_tolerates_corrupt_and_duplicate_jsonl_rows(self):
        fpath = self._write_jsonl(
            "mixed.jsonl",
            [
                "{not valid json",
                [1, 2, 3],
                {"task_id": "", "brain_of_origin": "groq/a"},
                {"task_id": "t1", "brain_of_origin": "groq/a", "status": "bogus"},
                {"task_id": "t1", "brain_of_origin": "groq/a", "status": "ok", "answer": "1"},
                {"task_id": "t1", "brain_of_origin": "groq/a", "status": "ok", "answer": "2"},
                {"task_id": "t1", "brain_of_origin": "gemini/b", "status": "ok", "answer": "1"},
            ],
        )
        mat, anom = coa.load_fixture_jsonl(fpath)
        self.assertEqual(len(anom), 5)
        rep = coa.evaluate_cross_organ_agreement(mat, anomalies=anom)
        self.assertEqual(rep["summary"]["unanimous_tasks"], 1)
        self.assertEqual(rep["summary"]["anomaly_count"], 5)

    def test_07_rejects_single_organ_or_missing_input_file(self):
        with self.assertRaises(ValueError):
            coa.load_fixture_jsonl(self.root / "nonexistent.jsonl")
        mat, _ = coa.parse_fixture_records(
            [{"task_id": "t1", "brain_of_origin": "groq/a", "status": "ok", "answer": "yes"}]
        )
        with self.assertRaises(ValueError):
            coa.evaluate_cross_organ_agreement(mat)

    def test_08_cli_markdown_and_json_output(self):
        fpath = self._write_jsonl(
            "bench.jsonl",
            [
                {"task_id": "t1", "brain_of_origin": "groq/qwen/qwen3.8-27b", "status": "ok", "answer": "ok"},
                {"task_id": "t1", "brain_of_origin": "gonka/deepseek-v4", "status": "ok", "answer": "ok"},
                {"task_id": "t2", "brain_of_origin": "groq/qwen/qwen3.8-27b", "status": "ok", "answer": "A"},
                {"task_id": "t2", "brain_of_origin": "gonka/deepseek-v4", "status": "ok", "answer": "B"},
            ],
        )
        md_out = self.root / "bench.md"
        rc = coa.main(["--input", str(fpath), "--format", "markdown", "--output", str(md_out)])
        self.assertEqual(rc, 0)
        text = md_out.read_text(encoding="utf-8")
        self.assertIn("Bench Kesepakatan Silang Multi-Organ", text)
        self.assertIn("`groq/qwen/qwen3.8-27b`", text)

        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc2 = coa.main(["--input", str(fpath)])
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(out_buf.getvalue())["summary"]["disagreement_count"], 1)

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc3 = coa.main(["--input", str(self.root / "missing.jsonl")])
        self.assertEqual(rc3, 1)


if __name__ == "__main__":
    unittest.main()
