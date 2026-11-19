#!/usr/bin/env python3
"""Tes unit & CLI untuk perkakas tata kelola korpus B3:
- `tools/frozen_corpus_registry.py`
- `tools/corpus_lint_v2.py`
- `tools/corpus_freeze_packer.py`
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import corpus_freeze_packer as cfp
from tools import corpus_lint_v2 as cl2
from tools import frozen_corpus_registry as fcr


class TestCorpusGovernanceB3(unittest.TestCase):
    def test_frozen_registry_write_and_check_drift_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "frozen"
            root.mkdir()
            c1 = root / "EVO_01_CORPUS.jsonl"
            c1.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "c-1", "kind": "episode", "task_kind": "code", "instruction": "Tulis a. Sertakan docstring Bahasa Indonesia."}),
                        json.dumps({"id": "l-1", "kind": "episode", "task_kind": "language", "instruction": "Ringkas log aman dalam dua kalimat persis."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            idx_path = Path(tmp) / "registry.json"
            index = fcr.scan_corpus_directory(root)
            fcr.atomic_write_text(idx_path, json.dumps(index, indent=2) + "\n")

            self.assertEqual(index["corpus_count"], 1)
            self.assertEqual(index["total_lines"], 2)
            self.assertEqual(index["task_kind_distribution"], {"code": 1, "language": 1})

            # Bersih sebelum perubahan
            clean_res = fcr.check_registry_drift(idx_path, root)
            self.assertTrue(clean_res["clean"])

            # Modifikasi + penambahan berkas baru wajib terdeteksi
            c1.write_text(c1.read_text(encoding="utf-8") + json.dumps({"id": "c-2", "kind": "episode", "task_kind": "code", "instruction": "Tulis b. Sertakan docstring Bahasa Indonesia."}) + "\n", encoding="utf-8")
            c2 = root / "EVO_02_CORPUS.jsonl"
            c2.write_text(json.dumps({"id": "l-2", "kind": "episode", "task_kind": "language", "instruction": "Uji kalimat bebas angka."}) + "\n", encoding="utf-8")
            drift_mod = fcr.check_registry_drift(idx_path, root)
            self.assertFalse(drift_mod["clean"])
            kinds = {d["name"]: d["drift_type"] for d in drift_mod["drifts"]}
            self.assertEqual(kinds, {"EVO_01_CORPUS.jsonl": "MODIFIED", "EVO_02_CORPUS.jsonl": "ADDED"})

            # Hapus c1 -> REMOVED terdeteksi
            c1.unlink()
            drift_rem = fcr.check_registry_drift(idx_path, root)
            kinds_rem = {d["name"]: d["drift_type"] for d in drift_rem["drifts"]}
            self.assertEqual(kinds_rem["EVO_01_CORPUS.jsonl"], "REMOVED")

    def test_frozen_registry_reads_repo_handover_corpora(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        handover = repo_root / "handover"
        index = fcr.scan_corpus_directory(handover)
        self.assertGreaterEqual(index["corpus_count"], 2)
        self.assertGreater(index["total_lines"], 10)

    def test_linter_v2_schema_mechanical_and_cross_file_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            samples = root / "samples"
            samples.mkdir()
            ep_a = root / "batch_a.jsonl"
            ep_b = root / "batch_b.jsonl"
            frozen = root / "frozen_ref.jsonl"
            lspecs = root / "lang_specs.jsonl"
            cspecs = root / "code_specs.jsonl"

            frozen.write_text(
                json.dumps(
                    {
                        "id": "old-1",
                        "kind": "episode",
                        "task_kind": "language",
                        "instruction": "Protokol standar menara timur dalam empat kalimat persis tanpa angka.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sample_ok = "Operator menara timur memeriksa jalur sinyal cadangan pagi ini. Sensor tetap stabil tanpa gangguan apa pun."
            (samples / "lang-ok.txt").write_text(sample_ok + "\n", encoding="utf-8")

            ep_a.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "lang-ok",
                                "kind": "episode",
                                "task_kind": "language",
                                "instruction": "Laporan Menara Timur A: tulis ringkasan dua kalimat memuat frasa persis \"jalur sinyal cadangan\" dan \"tetap stabil\".",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "code-bad-spec",
                                "kind": "episode",
                                "task_kind": "code",
                                "instruction": "Tulis `urut_ok(x)` dengan algoritma Merge Sort kompleksitas O(n log n) ruang O(n). Sertakan docstring Bahasa Indonesia.",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            # File kedua sengaja memuat ID duplikat, benturan frozen 60 karakter, & near-duplicate
            ep_b.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "lang-ok",
                                "kind": "episode",
                                "task_kind": "language",
                                "instruction": "Protokol standar menara timur dalam empat kalimat persis tanpa angka tambahan sedikit pun.",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "lang-contra",
                                "kind": "episode",
                                "task_kind": "language",
                                "instruction": "Tugas kontradiktif unik tidak menyertakan frasa terlarang di sini namun gagal spec.",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (samples / "lang-contra.txt").write_text("Sampel acak.", encoding="utf-8")

            lspecs.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "episode_id": "lang-ok",
                                "language": "id",
                                "active_layers": ["word_count", "sentence_count", "required_phrases", "forbidden_words", "required_order"],
                                "word_count": {"exact": 17},
                                "sentence_count": {"exact": 2},
                                "required_phrases": ["jalur sinyal cadangan", "tetap stabil"],
                                "forbidden_roots": ["rusak"],
                                "required_order": ["memeriksa jalur sinyal", "tanpa gangguan"],
                            }
                        ),
                        json.dumps(
                            {
                                "episode_id": "lang-contra",
                                "language": "id",
                                "active_layers": ["required_phrases", "forbidden_words", "required_order"],
                                "required_phrases": ["panel rusak berat"],
                                "forbidden_roots": ["rusak"],
                                "required_order": ["fakta sama", "fakta sama"],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            cspecs.write_text(
                json.dumps(
                    {
                        "episode_id": "code-bad-spec",
                        "algorithm": "Merge Sort",
                        "complexity_time": "O(n log n)",
                        "complexity_space": "O(n)",
                        "forbidden_tools": ["sorted"],  # hilang di instruksi -> gagal mekanis
                        "exact_signature": "urut_ok(x)",
                        "exact_return_format": "list[int]",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            res = cl2.lint_corpus_files_v2(
                [ep_a, ep_b],
                lang_specs_path=lspecs,
                lang_samples_dir=samples,
                code_specs_path=cspecs,
                frozen_paths=[frozen],
                near_dup_threshold=0.75,
            )
            self.assertFalse(res["valid"])
            codes = {v["code"] for v in res["violations"]}
            self.assertIn("cross_file_duplicate_id", codes)
            self.assertIn("frozen_corpus_collision", codes)
            self.assertIn("code_composite_constraint_mismatch", codes)
            self.assertIn("contradictory_phrase_forbidden_root", codes)
            self.assertIn("contradictory_order_constraint", codes)
            self.assertIn("instruction_missing_required_phrase", codes)
            self.assertIn("sample_constraint_failed", codes)

    def test_freeze_packer_roundtrip_and_fail_closed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cand = root / "candidates.jsonl"
            cand.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "g-1", "kind": "episode", "task_kind": "code", "instruction": "[ALPHA #01] Implementasikan `f1(a)` bersih. Sertakan docstring Bahasa Indonesia."}),
                        json.dumps({"id": "g-2", "kind": "episode", "task_kind": "language", "instruction": "[BETA #02] Ringkas log harian dalam tiga kalimat baku Bahasa Indonesia."}),
                        json.dumps({"id": "g-bad", "kind": "episode", "task_kind": "code", "instruction": "Kode tanpa docstring wajib"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            freeze_dir = root / "freeze_store"
            registry = freeze_dir / "REGISTRY.json"
            note = freeze_dir / "FREEZE_NOTE_EVO08.md"

            # Kandidat buruk wajib gagal & tidak menulis target beku
            with self.assertRaises(cfp.FreezePackError):
                cfp.freeze_candidates(
                    cand,
                    freeze_dir=freeze_dir,
                    freeze_name="EVO_08_CORPUS_V1.jsonl",
                    registry_path=registry,
                    note_path=note,
                    selected_ids=["g-1", "g-bad"],
                )
            self.assertFalse((freeze_dir / "EVO_08_CORPUS_V1.jsonl").exists())
            self.assertFalse(registry.exists())

            # Bekukan hanya g-1 & g-2 yang valid lewat CLI
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.corpus_freeze_packer",
                    "--candidates", str(cand),
                    "--freeze-dir", str(freeze_dir),
                    "--freeze-name", "EVO_08_CORPUS_V1.jsonl",
                    "--registry", str(registry),
                    "--note", str(note),
                    "--select-id", "g-1,g-2",
                    "--source-ref", "gravity/b3-test",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out_json = json.loads(proc.stdout)
            self.assertEqual(out_json["registry_entry"]["line_count"], 2)
            self.assertEqual(out_json["registry_entry"]["task_kind_distribution"], {"code": 1, "language": 1})
            self.assertIn("# Catatan Pembekuan Korpus: `EVO_08_CORPUS_V1.jsonl`", note.read_text(encoding="utf-8"))

            # Verifikasi CLI registry --check bersih atas direktori pembekuan hasil packer
            chk = subprocess.run(
                [sys.executable, "-m", "tools.frozen_corpus_registry", "--dir", str(freeze_dir), "--check", str(registry)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(chk.returncode, 0, chk.stdout + chk.stderr)
            self.assertTrue(json.loads(chk.stdout)["clean"])

    def test_linter_v2_rejects_vacuous_and_foreign_key_lang_specs(self) -> None:
        """Regresi D4: corpus_lint_v2 menolak spec kosong dan spec kunci-asing-saja."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            samples = root / "samples"
            samples.mkdir()
            ep_path = root / "ep.jsonl"
            ep_path.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "ep-empty", "kind": "episode", "task_kind": "language", "instruction": "Uji satu."}),
                        json.dumps({"id": "ep-foreign", "kind": "episode", "task_kind": "language", "instruction": "Uji dua yang cukup berbeda jauh."}),
                        json.dumps({"id": "ep-valid", "kind": "episode", "task_kind": "language", "instruction": "Uji tiga valid dengan kalimat baku berbeda."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            for eid in ("ep-empty", "ep-foreign", "ep-valid"):
                (samples / f"{eid}.txt").write_text("Satu dua tiga. Empat lima enam.\n", encoding="utf-8")

            lspecs = root / "lang_specs.jsonl"
            lspecs.write_text(
                "\n".join(
                    [
                        json.dumps({"episode_id": "ep-empty"}),
                        json.dumps({"episode_id": "ep-foreign", "word_cunt": {"exact": 6}, "active_layers": ["typo_layer"]}),
                        json.dumps({
                            "episode_id": "ep-valid",
                            "active_layers": ["word_count", "sentence_count"],
                            "word_count": {"exact": 6},
                            "sentence_count": {"exact": 2},
                        }),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            res = cl2.lint_corpus_files_v2([ep_path], lang_specs_path=lspecs, lang_samples_dir=samples)
            self.assertFalse(res["valid"])
            by_id = {v["id"]: v for v in res["violations"]}
            self.assertIn("ep-empty", by_id)
            self.assertIn("vacuous_spec", by_id["ep-empty"]["message"])
            self.assertIn("ep-foreign", by_id)
            self.assertIn("vacuous_spec", by_id["ep-foreign"]["message"])
            self.assertNotIn("ep-valid", by_id)


if __name__ == "__main__":
    unittest.main()
