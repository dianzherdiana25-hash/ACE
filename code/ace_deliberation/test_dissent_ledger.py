"""Uji append, pemisahan kasus, dan verifikasi kustodi dissent."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import dissent_ledger as ledger


def dissent(event_id="d1", case="case-a"):
    return {"event_id": event_id, "case_id": case, "kind": "dissent",
            "actor": "challenger", "statement": "Periksa bukti pembanding", "refs": ["turn-01"]}


def decision(refs):
    return {"event_id": "v1", "case_id": "case-a", "kind": "decision", "actor": "reviewer",
            "statement": "Tunda hingga bukti tersedia", "refs": refs, "outcome": "defer"}


class DissentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "dissent.jsonl"

    def test_putusan_hanya_boleh_menambah_dan_menyebut_semua_dissent(self):
        note = ledger.append_event(self.path, dissent())
        ledger.append_event(self.path, dissent("d2", "case-b"))
        prefix = self.path.read_bytes()
        for refs in ([], ["d2"], ["d1", "d2"]):
            with self.subTest(refs=refs), self.assertRaisesRegex(ledger.LedgerError, "semua"):
                ledger.append_event(self.path, decision(refs))
            self.assertEqual(self.path.read_bytes(), prefix)
        ledger.append_event(self.path, decision(["d1"]))
        self.assertTrue(self.path.read_bytes().startswith(prefix))
        output = ledger.audit(self.path, case_id="case-a")
        self.assertEqual((output["dissent_count"], output["decision_count"]), (1, 1))
        self.assertEqual(output["events"][0], note)

    def test_checkpoint_refuses_suffix_removal(self):
        ledger.append_event(self.path, dissent())
        prefix = self.path.read_bytes()
        ledger.append_event(self.path, decision(["d1"]))
        anchor = ledger.audit(self.path)["checkpoint"]
        self.assertTrue(ledger.audit(self.path, anchor=anchor)["anchor_checked"])
        self.path.write_bytes(prefix)
        with self.assertRaisesRegex(ledger.LedgerError, "terpotong"):
            ledger.audit(self.path, anchor=anchor)
        with self.assertRaisesRegex(ledger.LedgerError, "terpotong"):
            ledger.append_event(self.path, dissent("d3"), anchor=anchor)
        self.assertEqual(self.path.read_bytes(), prefix)

    def test_tampered_and_partial_records_refuse_further_append(self):
        ledger.append_event(self.path, dissent())
        original = self.path.read_bytes()
        for digest_damage in (original.replace(b'"sequence":1', b'"sequence":2'), original[:-1]):
            self.path.write_bytes(digest_damage)
            with self.assertRaises(ledger.LedgerError):
                ledger.append_event(self.path, dissent("d2"))
            self.assertEqual(self.path.read_bytes(), digest_damage)

    def test_parallel_writers_select_different_heads(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda i: ledger.append_event(self.path, dissent(f"d{i}")), range(12)))
        self.assertEqual(sorted(row["sequence"] for row in rows), list(range(1, 13)))
        audit = ledger.audit(self.path)
        self.assertEqual(audit["dissent_count"], 12)
        self.assertEqual(audit["checkpoint"]["sequence"], 12)
        self.assertEqual(len({json.loads(line)["sha256"] for line in self.path.read_bytes().splitlines()}), 12)

    def test_duplicate_id_and_symlink_do_not_modify_original(self):
        ledger.append_event(self.path, dissent())
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ledger.LedgerError, "ganda"):
            ledger.append_event(self.path, dissent())
        link = self.path.with_name("link")
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            ledger.append_event(link, dissent("d2"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_event_cannot_create_a_ledger(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.append_event(self.path, {**dissent(), "refs": []})
        self.assertFalse(self.path.exists())

    def test_missing_anchored_ledger_is_not_silently_recreated(self):
        anchor = {"sequence": 1, "sha256": "a" * 64}
        with self.assertRaises(FileNotFoundError):
            ledger.append_event(self.path, dissent(), anchor=anchor)
        self.assertFalse(self.path.exists())
        with self.assertRaises(ledger.LedgerError):
            ledger.append_event(self.path, dissent(), anchor={**anchor, "sequence": 0})
        self.assertFalse(self.path.exists())
