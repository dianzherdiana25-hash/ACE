#!/usr/bin/env python3
"""Unit tests untuk tools/corpus_tag.py (WS-B #6)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.corpus_tag import CorpusTagError, TAG_SCHEMA, main, tag_corpus


class TestCorpusTag(unittest.TestCase):
    def test_tagging_tiers_and_candidate_immutability(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corpus_path = tmp / "candidates.jsonl"
            corpus_bytes = (
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "w2_code_001",
                                "kind": "episode",
                                "task_kind": "code",
                                "instruction": "Buat penjadwalan interval rapat berbobot. Sertakan docstring Bahasa Indonesia.",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "fresh_lang_001",
                                "kind": "episode",
                                "task_kind": "language",
                                "instruction": "Ringkas log pendingin kontainer pelabuhan dengan segel termal rapat.",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "novel_code_001",
                                "kind": "episode",
                                "task_kind": "code",
                                "instruction": "Implementasikan encoder Huffman statis unik. Sertakan docstring Bahasa Indonesia.",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "brandnew_001",
                                "kind": "episode",
                                "task_kind": "other_kind",
                                "instruction": "Instruksi eksperimental tanpa riwayat sama sekali.",
                            }
                        ),
                    ]
                )
                + "\n"
            ).encode("utf-8")
            corpus_path.write_bytes(corpus_bytes)
            expected_sha = hashlib.sha256(corpus_bytes).hexdigest()

            history_path = tmp / "history.jsonl"
            history_lines = [
                json.dumps({"id": "w2_code_010", "task_kind": "code", "score": 55.0, "instruction": "Penjadwalan rapat."}),
                json.dumps({"id": "w2_code_011", "task_kind": "code", "score": 60.0, "instruction": "Interval rapat."}),
                json.dumps({"id": "w2_code_012", "task_kind": "code", "score": 65.0, "instruction": "Kapasitas ruang."}),
                json.dumps(
                    {
                        "id": "old_lang_099",
                        "task_kind": "language",
                        "score": 42.0,
                        "instruction": "Log pendingin kontainer pelabuhan dengan segel termal rapat harian.",
                    }
                ),
            ]
            history_path.write_text("\n".join(history_lines) + "\n", encoding="utf-8")

            report = tag_corpus(corpus_path=corpus_path, history_paths=[history_path])
            self.assertEqual(report["schema"], TAG_SCHEMA)
            self.assertEqual(report["corpus_sha256"], expected_sha)
            # Pastikan berkas kandidat tidak berubah sama sekali.
            self.assertEqual(hashlib.sha256(corpus_path.read_bytes()).hexdigest(), expected_sha)

            by_id = {row["episode_id"]: row for row in report["tags"]}
            self.assertEqual(by_id["w2_code_001"]["match_source"], "prefix_family")
            self.assertEqual(by_id["w2_code_001"]["predicted_band"], "45-75")
            self.assertEqual(by_id["w2_code_001"]["confidence"], "high")
            self.assertEqual(by_id["w2_code_001"]["band_label"], "mid_band_target")

            self.assertEqual(by_id["fresh_lang_001"]["match_source"], "keyword_overlap")
            self.assertEqual(by_id["fresh_lang_001"]["predicted_band"], "40-44")

            self.assertEqual(by_id["novel_code_001"]["match_source"], "task_kind_fallback")
            self.assertEqual(by_id["novel_code_001"]["predicted_band"], "45-75")
            self.assertEqual(by_id["novel_code_001"]["confidence"], "low")

            self.assertEqual(by_id["brandnew_001"]["match_source"], "none")
            self.assertEqual(by_id["brandnew_001"]["predicted_band"], "unknown")

    def test_census_aggregate_fallback_and_cli_jsonl_and_same_file_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corpus_path = tmp / "cands.jsonl"
            corpus_path.write_text(
                json.dumps(
                    {
                        "id": "x_001",
                        "kind": "episode",
                        "task_kind": "language",
                        "instruction": "Tulis ringkasan tepat tiga kalimat.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            census_json = tmp / "census.json"
            census_json.write_text(
                json.dumps(
                    {
                        "by_task_kind": {
                            "language": {
                                "score_bands": {
                                    "0-39": 1,
                                    "40-44": 1,
                                    "45-75": 8,
                                    "76-100": 2,
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            out_jsonl = tmp / "tags.jsonl"
            rc = main(
                [
                    "--corpus",
                    str(corpus_path),
                    "--history",
                    str(census_json),
                    "--out",
                    str(out_jsonl),
                    "--format",
                    "jsonl",
                ]
            )
            self.assertEqual(rc, 0)
            lines = out_jsonl.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["match_source"], "census_aggregate_fallback")
            self.assertEqual(row["predicted_band"], "45-75")

            # Tidak boleh menimpa berkas kandidat.
            bad_rc = main(
                [
                    "--corpus",
                    str(corpus_path),
                    "--history",
                    str(census_json),
                    "--out",
                    str(corpus_path),
                ]
            )
            self.assertEqual(bad_rc, 2)

            with self.assertRaises(CorpusTagError):
                tag_corpus(corpus_path=tmp / "missing.jsonl", history_paths=[census_json])


if __name__ == "__main__":
    unittest.main()
