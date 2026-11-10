"""M1 public development tests; disposable SQLite databases only (not sealed)."""
from __future__ import annotations
import multiprocessing as mp
import os
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from .fenced_store import EventConflict, FencedStore, LeaseRejected


def contest_worker(db: str, barrier: mp.Barrier, q: mp.Queue, i: int) -> None:
    store = FencedStore(db)
    barrier.wait(timeout=15)
    try:
        lease = store.acquire("same-job", f"w{i}", ttl=60)
        q.put(("win", lease.epoch))
    except LeaseRejected:
        q.put(("blocked", 0))


def kill_in_transaction(db: str) -> None:
    con = sqlite3.connect(db, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    con.execute("UPDATE counter SET epoch=epoch+1000 WHERE id=1")
    os._exit(23)  # intentional hard crash in disposable child process


class FencedStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ace-m1-")
        self.db = Path(self.temp.name) / "state.sqlite"
        self.store = FencedStore(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_acquisition_and_exclusion(self):
        lease = self.store.acquire("j", "a", now=100)
        with self.assertRaises(LeaseRejected):
            self.store.acquire("j", "b", now=105)
        self.store.release(lease, now=105)

    def test_epoch_survives_release_and_reopen(self):
        first = self.store.acquire("j", "a", now=100)
        self.store.release(first, now=105)
        second = FencedStore(self.db).acquire("j", "b", now=106)
        self.assertGreater(second.epoch, first.epoch)
        self.assertNotEqual(first.token, second.token)

    def test_expired_lease_rejects_stale_writes(self):
        old = self.store.acquire("j", "a", ttl=10, now=100)
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(old, "x", {"ok":True}, now=111)
        fresh = self.store.acquire("j", "b", now=112)
        with self.assertRaises(LeaseRejected):
            self.store.release(old, now=113)
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(old, "x", {"ok":True}, now=113)
        self.assertEqual(self.store.append_receipt(fresh, "x", {"ok":True}, now=113), 1)

    def test_renew_cannot_revive_expired_lease(self):
        old = self.store.acquire("j", "a", ttl=10, now=100)
        new = self.store.renew(old, ttl=20, now=105)
        self.assertEqual(new.epoch, old.epoch)
        self.assertGreater(new.expires_at, old.expires_at)
        with self.assertRaises(LeaseRejected):
            self.store.renew(new, ttl=20, now=126)

    def test_receipt_checkpoint_outbox_are_transactional_and_replayable(self):
        lease = self.store.acquire("j", "a", now=100)
        seq = self.store.append_receipt(lease, "event1", {"x": 1}, now=101)
        self.assertEqual(seq, self.store.append_receipt(lease, "event1", {"x": 1}, now=102))
        self.assertEqual(len(self.store.pending_outbox("j")), 1)
        self.assertEqual(FencedStore(self.db).snapshot("j")[:2], (seq, lease.epoch))
        FencedStore(self.db).ack_outbox(lease, "event1", now=103)
        self.assertEqual(FencedStore(self.db).pending_outbox("j"), [])

    def test_conflicting_event_id_is_rejected_without_mutation(self):
        lease = self.store.acquire("j", "a", now=100)
        self.store.append_receipt(lease, "e", {"x": 1}, now=101)
        old = self.store.snapshot("j")
        with self.assertRaises(EventConflict):
            self.store.append_receipt(lease, "e", {"x": 2}, now=102)
        self.assertEqual(old, self.store.snapshot("j"))
        self.assertEqual(len(self.store.pending_outbox("j")), 1)

    def test_invalid_id_and_ttl_fail_closed(self):
        for job in ("", "  ", "x"*257):
            with self.assertRaises(ValueError):
                self.store.acquire(job, "a")
        with self.assertRaises(ValueError):
            self.store.acquire("j", "a", ttl=0)

    def test_multiprocess_race_single_winner(self):
        ctx = mp.get_context("spawn")
        workers = 10
        barrier = ctx.Barrier(workers)
        q = ctx.Queue()
        processes = [ctx.Process(target=contest_worker, args=(str(self.db), barrier, q, i))
                     for i in range(workers)]
        for p in processes: p.start()
        for p in processes: p.join(timeout=25)
        for p in processes:
            if p.is_alive(): p.terminate(); p.join(timeout=3)
        self.assertTrue(all(p.exitcode == 0 for p in processes), [p.exitcode for p in processes])
        outcomes = [q.get(timeout=5) for _ in processes]
        self.assertEqual([x[0] for x in outcomes].count("win"), 1, outcomes)

    def test_process_crash_rolls_back_counter(self):
        ctx = mp.get_context("spawn")
        before = self.store.acquire("j1", "a", now=100)
        p = ctx.Process(target=kill_in_transaction, args=(str(self.db),))
        p.start(); p.join(timeout=20)
        self.assertEqual(p.exitcode, 23)
        next_lease = FencedStore(self.db).acquire("j2", "b", now=102)
        self.assertEqual(next_lease.epoch, before.epoch + 1)

    def test_corrupt_database_not_silently_reset(self):
        # Corrupt in place with no open connections; never recreate silently.
        self.db.write_bytes(b"NOT A DATABASE: CORRUPT")
        with self.assertRaises(sqlite3.DatabaseError):
            FencedStore(self.db)

    def test_failed_outbox_insert_rolls_back_event_and_checkpoint(self):
        lease = self.store.acquire("j", "a", now=100)
        with closing(sqlite3.connect(str(self.db))) as con:
            con.execute("""CREATE TRIGGER inject_abort BEFORE INSERT ON outbox
                           BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
            con.commit()
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.append_receipt(lease, "e", {"data": 1}, now=101)
        self.assertIsNone(self.store.snapshot("j"))
        self.assertEqual(self.store.pending_outbox("j"), [])

    def test_old_epoch_stays_rejected_even_with_clock_rollback(self):
        old = self.store.acquire("j", "a", ttl=10, now=100)
        new = self.store.acquire("j", "b", ttl=100, now=120)
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(old, "e", {}, now=101)
        self.store.append_receipt(new, "e", {}, now=121)

    def test_stale_worker_cannot_ack_outbox(self):
        old = self.store.acquire("j", "a", ttl=10, now=100)
        self.store.append_receipt(old, "e", {"ok": True}, now=101)
        _ = self.store.acquire("j", "b", now=111)
        with self.assertRaises(LeaseRejected):
            self.store.ack_outbox(old, "e", now=112)
        self.assertEqual(len(self.store.pending_outbox("j")), 1)


if __name__ == "__main__":
    unittest.main()
