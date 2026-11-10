"""Adversarial Concurrency, Fencing, and Crash Recovery Stress Suite for G11.

Milestone 1 Challenger 2: Fencing & Concurrency Adversarial Challenger.
Target: code/ace_operational/coding_loop.py:
- atomic_write_verified
- file_lock_guard
- Sibling lockfile protection (.{filename}.lock)
- Dynamic callable lease epoch fencing
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
import unittest

_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_operational.coding_loop import (
    FencingLeaseViolationError,
    StalePreimageError,
    atomic_write_verified,
    compute_file_sha256,
    file_lock_guard,
)


# ---------------------------------------------------------------------------
# Multiprocessing Worker Callbacks (Top-level for pickle / spawn compatibility)
# ---------------------------------------------------------------------------

def _mp_race_worker(
    target_path_str: str,
    orig_hash: str,
    worker_id: int,
    barrier: mp.Barrier,
    queue: mp.Queue,
) -> None:
    try:
        barrier.wait(timeout=10.0)
        atomic_write_verified(
            target_path_str,
            f"mp_worker_{worker_id}\n",
            expected_preimage_sha256=orig_hash,
            expected_lease_epoch=1,
            current_lease_epoch=1,
            timeout_sec=5.0,
        )
        queue.put(("SUCCESS", worker_id, None))
    except StalePreimageError as e:
        queue.put(("STALE", worker_id, str(e)))
    except Exception as e:
        queue.put(("ERROR", worker_id, f"{type(e).__name__}: {e}"))


def _mp_cas_counter_worker(
    target_path_str: str,
    worker_id: int,
    iterations: int,
    queue: mp.Queue,
) -> None:
    successes = 0
    failures = 0
    target = Path(target_path_str)
    for _ in range(iterations):
        for _retry in range(100):
            try:
                raw = target.read_bytes()
                curr_hash = hashlib.sha256(raw).hexdigest()
                curr_val = int(raw.decode("utf-8").strip())
                new_val = curr_val + 1
                atomic_write_verified(
                    target,
                    f"{new_val}\n",
                    expected_preimage_sha256=curr_hash,
                    timeout_sec=5.0,
                )
                successes += 1
                break
            except StalePreimageError:
                failures += 1
                time.sleep(0.005)
            except Exception as e:
                queue.put(("ERROR", worker_id, f"{type(e).__name__}: {e}"))
                return
    queue.put(("DONE", worker_id, (successes, failures)))


def _mp_lock_holder_and_crash(lock_path_str: str, ready_event: mp.Event) -> None:
    """Acquires lock and immediately waits to be killed via SIGKILL."""
    lock_path = Path(lock_path_str)
    # Open and lock directly or use file_lock_guard
    with file_lock_guard(lock_path, timeout_sec=5.0):
        ready_event.set()
        # Sleep until SIGKILL arrives
        time.sleep(60.0)


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestG11AdversarialConcurrencyAndFencing(unittest.TestCase):
    """Adversarial stress tests for atomic_write_verified and sibling file locking."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_adv_fencing_"))
        self.target = self.temp_dir / "protected_target.py"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # Dimension 1: Heavy Multithreaded Contention & CAS Chaining
    # =========================================================================

    def test_multithread_high_contention_single_winner(self):
        """Stress test: 30 concurrent threads race to update the same file with identical preimage."""
        initial_content = "initial_line\n"
        init_res = atomic_write_verified(self.target, initial_content)
        orig_hash = init_res["postimage_sha256"]

        num_threads = 30
        results = []

        def worker(idx: int) -> tuple[str, int]:
            try:
                atomic_write_verified(
                    self.target,
                    f"thread_update_{idx}\n",
                    expected_preimage_sha256=orig_hash,
                    timeout_sec=10.0,
                )
                return ("WIN", idx)
            except StalePreimageError:
                return ("STALE", idx)
            except Exception as e:
                return (f"ERROR:{type(e).__name__}", idx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        wins = [r for r in results if r[0] == "WIN"]
        stales = [r for r in results if r[0] == "STALE"]
        errors = [r for r in results if r[0].startswith("ERROR")]

        self.assertEqual(len(errors), 0, f"Unexpected errors during thread race: {errors}")
        self.assertEqual(len(wins), 1, f"Expected exactly 1 winner, got {len(wins)}")
        self.assertEqual(len(stales), num_threads - 1, f"Expected {num_threads - 1} stale errors, got {len(stales)}")

        # Verify no temporary files leaked
        tmp_files = list(self.target.parent.glob(".*.tmp.*"))
        self.assertEqual(len(tmp_files), 0, f"Leaked tmp files: {tmp_files}")

    def test_multithread_cas_counter_serializability(self):
        """Stress test: 15 threads perform 5 CAS updates each to verify complete serializability."""
        atomic_write_verified(self.target, "0\n")

        num_threads = 15
        increments_per_thread = 5

        def cas_increment(thread_id: int):
            for _ in range(increments_per_thread):
                while True:
                    try:
                        raw = self.target.read_bytes()
                        curr_hash = hashlib.sha256(raw).hexdigest()
                        val = int(raw.decode("utf-8").strip())
                        atomic_write_verified(
                            self.target,
                            f"{val + 1}\n",
                            expected_preimage_sha256=curr_hash,
                            timeout_sec=5.0,
                        )
                        break
                    except StalePreimageError:
                        time.sleep(0.002)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            list(executor.map(cas_increment, range(num_threads)))

        final_val = int(self.target.read_text(encoding="utf-8").strip())
        expected_total = num_threads * increments_per_thread
        self.assertEqual(final_val, expected_total, f"Expected final counter {expected_total}, got {final_val}")

    # =========================================================================
    # Dimension 2: Multiprocess Contention Across Independent OS Processes
    # =========================================================================

    def test_multiprocess_high_contention_single_winner(self):
        """Stress test: 10 independent OS processes race at exact same barrier moment."""
        init_res = atomic_write_verified(self.target, "mp_base\n")
        orig_hash = init_res["postimage_sha256"]

        num_procs = 10
        barrier = mp.Barrier(num_procs)
        queue = mp.Queue()

        processes = [
            mp.Process(
                target=_mp_race_worker,
                args=(str(self.target), orig_hash, i, barrier, queue),
            )
            for i in range(num_procs)
        ]

        for p in processes:
            p.start()

        for p in processes:
            p.join(timeout=15.0)

        results = []
        while not queue.empty():
            results.append(queue.get())

        wins = [r for r in results if r[0] == "SUCCESS"]
        stales = [r for r in results if r[0] == "STALE"]
        errors = [r for r in results if r[0] == "ERROR"]

        self.assertEqual(len(errors), 0, f"Process errors: {errors}")
        self.assertEqual(len(wins), 1, f"Expected exactly 1 multiprocess winner, got {len(wins)}")
        self.assertEqual(len(stales), num_procs - 1, f"Expected {num_procs - 1} stale rejections, got {len(stales)}")

        # Target file content must match the winning process
        winner_id = wins[0][1]
        self.assertEqual(self.target.read_text(encoding="utf-8"), f"mp_worker_{winner_id}\n")

    def test_multiprocess_cas_counter_serializability(self):
        """Stress test: 5 independent processes perform 4 CAS increments each."""
        atomic_write_verified(self.target, "0\n")
        num_procs = 5
        iterations = 4
        queue = mp.Queue()

        processes = [
            mp.Process(
                target=_mp_cas_counter_worker,
                args=(str(self.target), i, iterations, queue),
            )
            for i in range(num_procs)
        ]

        for p in processes:
            p.start()

        for p in processes:
            p.join(timeout=20.0)

        results = []
        while not queue.empty():
            results.append(queue.get())

        errors = [r for r in results if r[0] == "ERROR"]
        self.assertEqual(len(errors), 0, f"Process errors in CAS: {errors}")

        final_val = int(self.target.read_text(encoding="utf-8").strip())
        self.assertEqual(final_val, num_procs * iterations, f"Expected {num_procs * iterations}, got {final_val}")

    # =========================================================================
    # Dimension 3: Kernel Cleanup on Simulated Crash / SIGKILL
    # =========================================================================

    def test_sigkill_crash_lock_auto_cleanup(self):
        """Simulate hard crash (SIGKILL -9) of lock holder and verify OS immediately frees lock."""
        lock_path = self.target.parent / f".{self.target.name}.lock"
        ready_event = mp.Event()

        # Start a process that locks the sibling lockfile and then waits
        proc = mp.Process(target=_mp_lock_holder_and_crash, args=(str(lock_path), ready_event))
        proc.start()

        try:
            # Wait until process has acquired the lock
            self.assertTrue(ready_event.wait(timeout=5.0), "Child process failed to acquire lock in time")

            # Verify that another attempt to lock right now fails / times out quickly
            with self.assertRaises(TimeoutError):
                with file_lock_guard(lock_path, timeout_sec=0.1):
                    pass

            # Abruptly kill the process with SIGKILL (cannot run any cleanup handlers or finally blocks)
            os.kill(proc.pid, signal.SIGKILL)
            proc.join(timeout=3.0)

            # Sibling lock file still exists on disk
            self.assertTrue(lock_path.exists(), "Lockfile should still exist on filesystem")

            # CRITICAL VERIFICATION: Subsequent writer must succeed immediately without deadlock!
            t_start = time.time()
            atomic_write_verified(self.target, "post_crash_write\n", timeout_sec=2.0)
            elapsed = time.time() - t_start

            self.assertEqual(self.target.read_text(encoding="utf-8"), "post_crash_write\n")
            self.assertLess(elapsed, 1.0, f"Lock acquisition after crash took too long: {elapsed:.2f}s")
        finally:
            if proc.is_alive():
                proc.kill()
                proc.join()

    # =========================================================================
    # Dimension 4: Dynamic Callable Lease Epoch Rejection on Epoch Increment
    # =========================================================================

    def test_dynamic_lease_epoch_increment_rejection(self):
        """Verify dynamic callable lease epoch rejection when lease epoch is incremented.
        
        VULNERABILITY / ADVERSARIAL CHALLENGE:
        In distributed fencing tokens (Kleppmann / Lamport), when a lease epoch increments
        (e.g. from 1 to 2), any write carrying an older expected epoch (1) MUST be rejected.
        Current implementation in coding_loop.py:102:
            if cur_epoch < expected_lease_epoch:
                raise FencingLeaseViolationError(...)
        When epoch increments (cur_epoch = 2, expected_lease_epoch = 1):
        2 < 1 is FALSE, allowing the stale write through!
        """
        # Initialize target
        atomic_write_verified(self.target, "v = 1\n", expected_lease_epoch=1, current_lease_epoch=1)

        # System lease epoch starts at 1
        system_epoch = [1]

        def dynamic_system_epoch() -> int:
            return system_epoch[0]

        # Valid write under current epoch 1
        atomic_write_verified(
            self.target,
            "v = 2\n",
            expected_lease_epoch=1,
            current_lease_epoch=dynamic_system_epoch,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), "v = 2\n")

        # Now system lease epoch advances / increments to 2 (e.g. worker timed out, lease expired, new worker elected)
        system_epoch[0] = 2

        # A stalled / zombie worker attempts to commit with its stale expected epoch 1
        # It MUST be rejected with FencingLeaseViolationError!
        try:
            atomic_write_verified(
                self.target,
                "v = stale_zombie\n",
                expected_lease_epoch=1,
                current_lease_epoch=dynamic_system_epoch,
            )
            # If we reach here, the stale write was erroneously accepted!
            zombie_accepted = True
        except FencingLeaseViolationError:
            zombie_accepted = False

        self.assertFalse(
            zombie_accepted,
            "CRITICAL FENCING VULNERABILITY: Stale worker with epoch=1 was allowed to commit "
            "when current system epoch was incremented to 2! coding_loop.py:102 checks "
            "'cur_epoch < expected_lease_epoch' instead of 'cur_epoch > expected_lease_epoch' "
            "(or 'cur_epoch != expected_lease_epoch').",
        )

    def test_integer_lease_epoch_increment_rejection(self):
        """Verify non-callable integer epoch rejection when current > expected (forward advancement)."""
        with self.assertRaises(FencingLeaseViolationError) as cm:
            atomic_write_verified(
                self.target,
                "v = stale\n",
                expected_lease_epoch=1,
                current_lease_epoch=2,  # current system epoch has advanced to 2
            )
        self.assertIn("saat ini 2 != diharapkan 1", str(cm.exception))

    def test_integer_lease_epoch_backward_regression_rejection(self):
        """Verify non-callable integer epoch rejection when current < expected (backward regression)."""
        with self.assertRaises(FencingLeaseViolationError) as cm:
            atomic_write_verified(
                self.target,
                "v = regressed\n",
                expected_lease_epoch=5,
                current_lease_epoch=4,  # system epoch regressed or mismatched
            )
        self.assertIn("saat ini 4 != diharapkan 5", str(cm.exception))

    def test_dynamic_lease_epoch_backward_regression_rejection(self):
        """Verify dynamic callable lease epoch rejection on backward regression."""
        system_epoch = 4

        with self.assertRaises(FencingLeaseViolationError) as cm:
            atomic_write_verified(
                self.target,
                "v = regressed_dynamic\n",
                expected_lease_epoch=5,
                current_lease_epoch=lambda: system_epoch,
            )
        self.assertIn("saat ini 4 != diharapkan 5", str(cm.exception))

    def test_lease_epoch_exact_match_success(self):
        """Verify that writes succeed when current == expected epoch."""
        res = atomic_write_verified(
            self.target,
            "v = epoch_matched\n",
            expected_lease_epoch=5,
            current_lease_epoch=5,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), "v = epoch_matched\n")

        # Also dynamic callable match
        res_dyn = atomic_write_verified(
            self.target,
            "v = dynamic_matched\n",
            expected_preimage_sha256=res["postimage_sha256"],
            expected_lease_epoch=5,
            current_lease_epoch=lambda: 5,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), "v = dynamic_matched\n")

    def test_concurrent_fencing_epoch_heterogeneous_race(self):
        """Stress test: 10 threads race with differing epochs; only matching epoch=5 may succeed."""
        init_res = atomic_write_verified(self.target, "base_val\n")
        orig_hash = init_res["postimage_sha256"]
        curr_sys_epoch = 5

        test_epochs = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 100]
        results = {}

        def attempt_write(epoch: int):
            try:
                atomic_write_verified(
                    self.target,
                    f"written_by_epoch_{epoch}\n",
                    expected_preimage_sha256=orig_hash,
                    expected_lease_epoch=epoch,
                    current_lease_epoch=lambda: curr_sys_epoch,
                    timeout_sec=5.0,
                )
                return ("SUCCESS", epoch, None)
            except FencingLeaseViolationError as e:
                return ("FENCING_REJECT", epoch, str(e))
            except Exception as e:
                return ("OTHER_ERROR", epoch, f"{type(e).__name__}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(test_epochs)) as ex:
            futures = [ex.submit(attempt_write, ep) for ep in test_epochs]
            for f in concurrent.futures.as_completed(futures):
                status, ep, detail = f.result()
                results[ep] = (status, detail)

        # Only epoch=5 should succeed
        self.assertEqual(results[5][0], "SUCCESS", f"Expected epoch 5 to succeed: {results[5]}")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "written_by_epoch_5\n")

        # All other epochs must be rejected with FencingLeaseViolationError
        for ep in test_epochs:
            if ep == 5:
                continue
            status, detail = results[ep]
            self.assertEqual(
                status,
                "FENCING_REJECT",
                f"Epoch {ep} did not fail with FENCING_REJECT, got {status} ({detail})",
            )

    # =========================================================================
    # Dimension 5: Exact Preimage SHA256 Verification & Invariants
    # =========================================================================

    def test_exact_preimage_hash_verification(self):
        """Verify preimage SHA256 integrity checks."""
        atomic_write_verified(self.target, "initial_data\n")
        correct_hash = compute_file_sha256(self.target)

        # Mismatched hash must be rejected
        with self.assertRaises(StalePreimageError):
            atomic_write_verified(
                self.target,
                "tampered_data\n",
                expected_preimage_sha256="0" * 64,
            )
        self.assertEqual(self.target.read_text(encoding="utf-8"), "initial_data\n")

        # Matching hash succeeds
        res = atomic_write_verified(
            self.target,
            "updated_data\n",
            expected_preimage_sha256=correct_hash,
        )
        self.assertEqual(res["preimage_sha256"], correct_hash)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "updated_data\n")

    def test_new_file_creation_with_missing_preimage(self):
        """Verify expected_preimage_sha256='MISSING' semantics."""
        new_file = self.temp_dir / "brand_new.py"
        self.assertFalse(new_file.exists())

        # If file missing, 'MISSING' succeeds
        res = atomic_write_verified(new_file, "content\n", expected_preimage_sha256="MISSING")
        self.assertEqual(res["preimage_sha256"], "MISSING")
        self.assertTrue(new_file.exists())

    def test_lease_verifier_callback(self):
        """Verify lease_verifier callback can independently gate commits."""
        atomic_write_verified(self.target, "init\n")

        # Fails when verifier returns False
        with self.assertRaises(FencingLeaseViolationError):
            atomic_write_verified(
                self.target,
                "fail\n",
                lease_verifier=lambda: False,
            )

        # Succeeds when verifier returns True
        res = atomic_write_verified(
            self.target,
            "pass\n",
            lease_verifier=lambda: True,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), "pass\n")

    def test_independent_file_writes_concurrency(self):
        """Verify distinct target files have distinct sibling lockfiles and execute without blocking."""
        target_a = self.temp_dir / "target_a.py"
        target_b = self.temp_dir / "target_b.py"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(atomic_write_verified, target_a, "content_a\n")
            f2 = ex.submit(atomic_write_verified, target_b, "content_b\n")
            r1 = f1.result()
            r2 = f2.result()

        self.assertEqual(target_a.read_text(encoding="utf-8"), "content_a\n")
        self.assertEqual(target_b.read_text(encoding="utf-8"), "content_b\n")
        self.assertTrue((self.temp_dir / ".target_a.py.lock").exists())
        self.assertTrue((self.temp_dir / ".target_b.py.lock").exists())


if __name__ == "__main__":
    unittest.main()
