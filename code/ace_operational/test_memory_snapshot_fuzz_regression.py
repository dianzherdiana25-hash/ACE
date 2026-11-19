"""Regression and fuzz tests for D6 non-dict root & malformed entry crashes in memory_snapshot."""
from __future__ import annotations

import json
from pathlib import Path
import random
import tempfile
import unittest

from ace_operational.memory_bridge import ConversationalMemoryManager
from ace_operational.memory_snapshot import export_snapshot, import_snapshot_if_needed
from ace_operational.speech_acquisition import SpeechDevelopmentEngine
from ace_operational.store import OperationalStore


class MemorySnapshotFuzzRegressionTests(unittest.TestCase):
    def test_missing_and_invalid_utf8_or_corrupt_json_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            store = OperationalStore(ws)
            missing = Path(tmp) / "missing.json"
            self.assertEqual(import_snapshot_if_needed(store, missing)["reason"], "snapshot_not_found")

            bad = Path(tmp) / "bad.json"
            bad.write_bytes(b"\xff\xfe\x00{bad")
            self.assertEqual(import_snapshot_if_needed(store, bad)["reason"], "snapshot_unreadable")

    def test_non_dict_json_root_does_not_crash_with_attribute_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            store = OperationalStore(ws)
            snap = Path(tmp) / "snap.json"
            for payload in ("[]", "null", "123", '"hello"', "true"):
                with self.subTest(payload=payload):
                    snap.write_text(payload, encoding="utf-8")
                    res = import_snapshot_if_needed(store, snap)
                    self.assertFalse(res["applied"])
                    self.assertEqual(res["reason"], "snapshot_unreadable")

    def test_malformed_containers_and_bad_confidence_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            store = OperationalStore(ws)
            snap = Path(tmp) / "snap.json"
            bad_doc = {
                "snapshot_version": ["not-a-str"],
                "lexicon": [123, None, {"word": "halo", "meaning_id": "greet.halo", "role": "greeting"}],
                "memories": [
                    "not-a-dict",
                    {"text": "catatan valid satu", "confidence": "not-a-float"},
                    {"text": "catatan valid dua", "confidence": True},
                ],
                "dialog_corpus": 999,
            }
            snap.write_text(json.dumps(bad_doc), encoding="utf-8")
            res = import_snapshot_if_needed(store, snap)
            self.assertTrue(res["applied"])
            self.assertEqual(res["corpus_added"], 0)

            bad_lists = {"lexicon": None, "memories": 42, "dialog_corpus": ["raw-str", {"u": "hi", "a": "ok"}]}
            snap.write_text(json.dumps(bad_lists), encoding="utf-8")
            res2 = import_snapshot_if_needed(store, snap)
            self.assertTrue(res2["applied"])
            self.assertEqual(res2["corpus_added"], 1)

    def test_export_and_idempotent_import_roundtrip_with_corrupt_corpus_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src_ws = Path(tmp) / "src"
            src_ws.mkdir()
            src_store = OperationalStore(src_ws)
            SpeechDevelopmentEngine(src_store).teach_word("selamat", "greet.selamat", role="greeting")
            ConversationalMemoryManager(src_store).remember_statement("Fakta publik valid", confidence=0.85, sensitivity="internal")
            corpus = src_ws / "projects" / "bahasa" / "dialog_corpus.jsonl"
            corpus.parent.mkdir(parents=True, exist_ok=True)
            corpus.write_bytes(b'{"u":"hai","a":"halo"}\n{broken\n123\n\xff\xfe\n')

            snap_file = Path(tmp) / "out.json"
            exp = export_snapshot(src_ws, snap_file)
            self.assertEqual(exp["dialog_corpus_count"], 1)
            self.assertEqual(exp["vocab_count"], 1)

            dst_ws = Path(tmp) / "dst"
            dst_ws.mkdir()
            dst_store = OperationalStore(dst_ws)
            first = import_snapshot_if_needed(dst_store, snap_file)
            self.assertTrue(first["applied"])
            self.assertEqual(first["words_added"], 1)
            self.assertEqual(first["dialog_corpus_count"] if "dialog_corpus_count" in first else first["corpus_added"], 1)
            second = import_snapshot_if_needed(dst_store, snap_file)
            self.assertFalse(second["applied"])
            self.assertEqual(second["reason"], "already_applied")

    def test_deterministic_fuzz_150_snapshots_no_unhandled_crash(self) -> None:
        rng = random.Random(20261119)
        atoms = [None, True, False, 0, -5, "nan", "inf", "x", [], {}, [1, "a"], {"word": "uji", "meaning_id": "m.uji"}]
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "fuzz.json"
            for i in range(150):
                ws = Path(tmp) / f"ws_{i}"
                ws.mkdir()
                store = OperationalStore(ws)
                mode = rng.randint(0, 2)
                if mode == 0:
                    payload = json.dumps(rng.choice(atoms))
                elif mode == 1:
                    payload = json.dumps({
                        "snapshot_version": rng.choice(atoms),
                        "lexicon": rng.choice(atoms),
                        "memories": rng.choice(atoms),
                        "dialog_corpus": rng.choice(atoms),
                    })
                else:
                    payload = "{corrupt"[: rng.randint(0, 8)]
                snap.write_text(payload, encoding="utf-8")
                res = import_snapshot_if_needed(store, snap)
                self.assertIn("applied", res)


if __name__ == "__main__":
    unittest.main()
