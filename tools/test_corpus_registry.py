"""Uji unit untuk registri corpus beku tools/corpus_registry.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.corpus_registry import RegistryError, check_drift, scan_corpora

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_corpus(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


class CorpusRegistryTests(unittest.TestCase):
    """Pengujian pemindaian direktori corpus beku dan deteksi drift."""

    def test_scan_counts_lines_sha_and_task_kinds_ignoring_non_corpus_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "handover"
            root.mkdir()
            _write_corpus(
                root / "EVO_0005_CORPUS_V1.jsonl",
                [
                    {"id": "c-001", "kind": "episode", "task_kind": "code", "instruction": "A"},
                    {"id": "c-002", "kind": "episode", "task_kind": "code", "instruction": "B"},
                    {"id": "l-001", "kind": "episode", "task_kind": "language", "instruction": "C"},
                ],
            )
            _write_corpus(
                root / "nested" / "W2_CORPUS_FROZEN.jsonl",
                [
                    {"id": "l-002", "kind": "episode", "task_kind": "language", "instruction": "D"},
                ],
            )
            # Berkas non-corpus seperti queries.jsonl tidak boleh ikut terdaftar.
            _write_corpus(root / "sqlite-vec-trial" / "queries.jsonl", [{"query": "abc", "gold": 0}])

            reg = scan_corpora(root)
            self.assertEqual(reg["corpus_count"], 2)
            names = [c["name"] for c in reg["corpora"]]
            self.assertEqual(names, ["EVO_0005_CORPUS_V1.jsonl", "nested/W2_CORPUS_FROZEN.jsonl"])
            self.assertEqual(reg["corpora"][0]["line_count"], 3)
            self.assertEqual(reg["corpora"][0]["task_kind_counts"], {"code": 2, "language": 1})
            self.assertEqual(len(reg["corpora"][0]["sha256"]), 64)

    def test_check_detects_no_drift_then_added_changed_and_removed(self) -> None:
        script = REPO_ROOT / "tools" / "corpus_registry.py"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            handover = tmp_dir / "handover"
            index_path = tmp_dir / "registry.json"
            c1 = handover / "EVO_0005_CORPUS_V1.jsonl"
            _write_corpus(
                c1,
                [{"id": "c-001", "kind": "episode", "task_kind": "code", "instruction": "A"}],
            )

            # Bangun indeks awal via CLI.
            p_build = subprocess.run(
                [sys.executable, str(script), "--dir", str(handover), "--output", str(index_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_build.returncode, 0)

            # Tanpa perubahan -> exit 0, drift_detected=False.
            p_clean = subprocess.run(
                [sys.executable, str(script), "--dir", str(handover), "--check", str(index_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_clean.returncode, 0)
            self.assertFalse(json.loads(p_clean.stdout)["drift_detected"])

            # Tambah corpus baru & ubah isi corpus lama -> exit 1, added + changed tercatat.
            c2 = handover / "W2_CORPUS_FROZEN.jsonl"
            _write_corpus(c2, [{"id": "l-001", "kind": "episode", "task_kind": "language", "instruction": "B"}])
            _write_corpus(
                c1,
                [
                    {"id": "c-001", "kind": "episode", "task_kind": "code", "instruction": "A"},
                    {"id": "c-002", "kind": "episode", "task_kind": "code", "instruction": "Z"},
                ],
            )
            p_drift = subprocess.run(
                [sys.executable, str(script), "--dir", str(handover), "--check", str(index_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_drift.returncode, 1)
            drift = json.loads(p_drift.stdout)
            self.assertTrue(drift["drift_detected"])
            self.assertEqual(drift["added"], ["W2_CORPUS_FROZEN.jsonl"])
            self.assertEqual(drift["changed"][0]["name"], "EVO_0005_CORPUS_V1.jsonl")

            # Hapus corpus awal -> tercatat pada removed.
            c1.unlink()
            drift2 = check_drift(handover, index_path)
            self.assertEqual(drift2["removed"], ["EVO_0005_CORPUS_V1.jsonl"])

    def test_invalid_dir_or_missing_index_raises_exit_2(self) -> None:
        script = REPO_ROOT / "tools" / "corpus_registry.py"
        with self.assertRaises(RegistryError):
            scan_corpora(Path("/tmp/tidak_ada_handover_dir"))
        proc = subprocess.run(
            [sys.executable, str(script), "--dir", str(REPO_ROOT / "handover"), "--check", "/tmp/no_idx.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Error:", proc.stderr)

    def test_fuzz_hardening_huge_int_digit_limit_raises_registry_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handover = Path(tmp) / "handover"
            handover.mkdir()
            c_bad = handover / "HUGE_CORPUS.jsonl"
            c_bad.write_text('{"id": "1", "val": ' + ("9" * 5000) + "}\n", encoding="utf-8")
            with self.assertRaises(RegistryError):
                scan_corpora(handover)

            c_bad.write_text('{"id": "1", "task_kind": "code"}\n', encoding="utf-8")
            bad_idx = Path(tmp) / "bad_idx.json"
            bad_idx.write_text(
                '{"schema": "ace.frozen-corpus-registry.v1", "corpora": [{"name": "HUGE_CORPUS.jsonl", "line_count": '
                + ("9" * 5000)
                + "}]}",
                encoding="utf-8",
            )
            with self.assertRaises(RegistryError):
                check_drift(handover, bad_idx)


if __name__ == "__main__":
    unittest.main()
