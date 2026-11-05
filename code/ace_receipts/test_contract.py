"""Offline adversarial tests for evaluator-owned receipt contract."""
import tempfile
import unittest
from pathlib import Path
from ace_receipts.contract import ReceiptBook, ReceiptError, UncertainAction

def trusted(key, payload, receipt):
    return receipt.get("trusted") is True and receipt.get("key") == key and payload == {"cost": 7}

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "receipts.db"
        self.book = ReceiptBook(self.path)

    def tearDown(self):
        self.book.close()
        self.tmp.cleanup()

    def test_reserve_before_dispatch(self):
        with self.assertRaises(ReceiptError):
            self.book.dispatch("x")

    def test_idempotent_reserve_and_payload_conflict(self):
        self.assertEqual(self.book.reserve("x", {"cost": 7}), "RESERVED")
        self.assertEqual(self.book.reserve("x", {"cost": 7}), "RESERVED")
        with self.assertRaises(ReceiptError):
            self.book.reserve("x", {"cost": 8})

    def test_no_duplicate_dispatch(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        with self.assertRaises(UncertainAction):
            self.book.dispatch("x")

    def test_crash_restart_halts_uncertain(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        self.book.close()
        self.book = ReceiptBook(self.path)
        self.assertEqual(self.book.recover(), [("x", "HALT_UNCERTAIN")])
        with self.assertRaises(UncertainAction):
            self.book.dispatch("x")

    def test_reserved_restart_also_halts(self):
        self.book.reserve("x", {"cost": 7})
        self.assertEqual(self.book.recover(), [("x", "HALT_UNCERTAIN")])

    def test_unverified_receipt_rejected(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        with self.assertRaises(ReceiptError):
            self.book.reconcile("x", {"key":"x","outcome":"SUCCEEDED"}, trusted)
        self.assertEqual(self.book.status("x"), "DISPATCHED")

    def test_verified_receipt_recovers_and_is_idempotent(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        self.book.recover()
        receipt = {"key":"x","outcome":"SUCCEEDED","trusted":True}
        self.assertEqual(self.book.reconcile("x", receipt, trusted), "SUCCEEDED")
        self.assertEqual(self.book.reconcile("x", receipt, trusted), "SUCCEEDED")
        with self.assertRaises(ReceiptError):
            self.book.reconcile("x", {**receipt, "outcome":"FAILED"}, trusted)

    def test_forged_binding_rejected(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        with self.assertRaises(ReceiptError):
            self.book.reconcile("x", {"key":"y","outcome":"SUCCEEDED","trusted":True}, trusted)

    def test_terminal_survives_restart(self):
        self.book.reserve("x", {"cost": 7})
        self.book.dispatch("x")
        self.book.reconcile("x", {"key":"x","outcome":"FAILED","trusted":True}, trusted)
        self.book.close()
        self.book = ReceiptBook(self.path)
        self.assertEqual(self.book.recover(), [("x", "FAILED")])

    def test_symlink_db_rejected(self):
        target = Path(self.tmp.name) / "target"
        target.write_text("")
        link = Path(self.tmp.name) / "link"
        link.symlink_to(target)
        with self.assertRaises(ReceiptError):
            ReceiptBook(link)

if __name__ == "__main__":
    unittest.main()
