#!/usr/bin/env python3
"""Unit tests untuk tools/corpus_factory_code.py (WS-B #4)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.corpus_factory_code import (
    CorpusFactoryCodeError,
    FACTORY_SCHEMA,
    generate_code_episodes,
    main,
)
from tools.corpus_lint import lint_lines, load_frozen_prefixes


class TestCorpusFactoryCode(unittest.TestCase):
    def test_generate_determinism_and_schema(self) -> None:
        r1 = generate_code_episodes(count=24, prefix="code_gen_", seed=20261117)
        r2 = generate_code_episodes(count=24, prefix="code_gen_", seed=20261117)
        self.assertEqual(r1["schema"], FACTORY_SCHEMA)
        self.assertEqual(r1["lines"], r2["lines"])
        self.assertEqual(len(r1["lines"]), 24)
        self.assertTrue(r1["lint_ok"])

        for idx, raw in enumerate(r1["lines"], start=1):
            obj = json.loads(raw)
            self.assertEqual(set(obj.keys()), {"id", "kind", "task_kind", "instruction"})
            self.assertEqual(obj["id"], f"code_gen_{idx:03d}")
            self.assertEqual(obj["kind"], "episode")
            self.assertEqual(obj["task_kind"], "code")
            self.assertIn("docstring Bahasa Indonesia", obj["instruction"])

        # Semua prefix 60 karakter unik dan mencakup beragam keluarga algoritma.
        prefixes60 = {json.loads(line)["instruction"][:60] for line in r1["lines"]}
        self.assertEqual(len(prefixes60), 24)
        self.assertGreaterEqual(len(r1["family_counts"]), 5)

    def test_large_batch_over_100_passes_corpus_lint(self) -> None:
        res = generate_code_episodes(count=120, prefix="batch_", seed=99)
        self.assertEqual(len(res["lines"]), 120)
        lint = lint_lines(res["lines"], prefixes=["batch_"])
        self.assertTrue(lint["valid"])
        first = json.loads(res["lines"][0])
        last = json.loads(res["lines"][-1])
        self.assertEqual(first["id"], "batch_001")
        self.assertEqual(last["id"], "batch_120")

    def test_frozen_collision_is_skipped_and_revalidated(self) -> None:
        base = generate_code_episodes(count=10, prefix="c_", seed=42)
        first_obj = json.loads(base["lines"][0])
        with tempfile.TemporaryDirectory() as tmp:
            frozen_path = Path(tmp) / "frozen.jsonl"
            frozen_path.write_text(json.dumps(first_obj, ensure_ascii=False) + "\n", encoding="utf-8")

            filtered = generate_code_episodes(
                count=10,
                prefix="c_",
                seed=42,
                frozen_paths=[frozen_path],
            )
            self.assertGreaterEqual(filtered["skipped_frozen_collisions"], 1)
            frozen_prefixes = load_frozen_prefixes([frozen_path])
            lint = lint_lines(
                filtered["lines"],
                prefixes=["c_"],
                frozen_prefixes=frozen_prefixes,
            )
            self.assertTrue(lint["valid"])

    def test_error_on_invalid_parameters_or_excessive_count(self) -> None:
        with self.assertRaises(CorpusFactoryCodeError):
            generate_code_episodes(count=0)
        with self.assertRaises(CorpusFactoryCodeError):
            generate_code_episodes(count=-5)
        with self.assertRaises(CorpusFactoryCodeError):
            generate_code_episodes(count=5, prefix=" ")
        with self.assertRaises(CorpusFactoryCodeError):
            generate_code_episodes(count=5, prefix="bad prefix")
        with self.assertRaises(CorpusFactoryCodeError):
            generate_code_episodes(count=5000, prefix="c_")

    def test_cli_end_to_end_with_frozen_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            out_path = tmp / "code_candidates.jsonl"
            summary_path = tmp / "summary.json"
            frozen_path = tmp / "frozen.jsonl"
            frozen_path.write_text(
                json.dumps(
                    {
                        "id": "fz_001",
                        "kind": "episode",
                        "task_kind": "code",
                        "instruction": "Instruksi beku yang tidak bertabrakan tetapi valid penuh dengan docstring Bahasa Indonesia.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rc = main(
                [
                    "--count",
                    "16",
                    "--prefix",
                    "w4_",
                    "--seed",
                    "7",
                    "--frozen",
                    str(frozen_path),
                    "--out",
                    str(out_path),
                    "--summary-out",
                    str(summary_path),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue(out_path.is_file())
            self.assertTrue(summary_path.is_file())
            lines = out_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 16)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["count"], 16)
            self.assertTrue(summary["lint_ok"])

            bad_rc = main(["--count", "4", "--frozen", str(tmp / "missing.jsonl"), "--out", str(out_path)])
            self.assertEqual(bad_rc, 2)


if __name__ == "__main__":
    unittest.main()
