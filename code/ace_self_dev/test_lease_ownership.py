"""Preregistered public regression tests for research-state lease ownership.

See docs/research/ACE_SELF_DEV_LEASE_ADMISSION_PRESCORE_20261110.md.
These tests operate exclusively on disposable temporary directories.
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from .state_manager import ConcurrencyLockError, StateManager


class TestLeaseOwnership(unittest.TestCase):
    def setUp(self) -> None:
        self.workdir = tempfile.TemporaryDirectory(prefix="ace-lock-test-")
        self.manager = StateManager(state_dir=self.workdir.name, lock_ttl_seconds=10.0)

    def tearDown(self) -> None:
        self.workdir.cleanup()

    def test_wrong_token_does_not_mutate_active_lease(self) -> None:
        correct = self.manager.acquire_lock("worker_a")
        original = self.manager.state_path.read_bytes()

        with self.assertRaises(ConcurrencyLockError):
            self.manager.release_lock("worker_b_fake_token")
        self.assertEqual(original, self.manager.state_path.read_bytes())
        with self.assertRaises(ConcurrencyLockError):
            self.manager.acquire_lock("worker_b")

        self.manager.release_lock(correct)
        second = self.manager.acquire_lock("worker_b")
        self.manager.release_lock(second)

    def test_empty_missing_and_non_string_tokens_fail_closed(self) -> None:
        correct = self.manager.acquire_lock("worker_a")
        original = self.manager.state_path.read_bytes()
        for invalid in ("", None, 0, False):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ConcurrencyLockError):
                    self.manager.release_lock(invalid)  # type: ignore[arg-type]
                self.assertEqual(original, self.manager.state_path.read_bytes())
        self.manager.release_lock(correct)

    def test_stale_token_cannot_release_replacement_lease(self) -> None:
        with patch("ace_self_dev.state_manager.time.time", return_value=100.0):
            first = self.manager.acquire_lock("worker_a")
        with patch("ace_self_dev.state_manager.time.time", return_value=200.0):
            second = self.manager.acquire_lock("worker_b")

        original = self.manager.state_path.read_bytes()
        with self.assertRaises(ConcurrencyLockError):
            self.manager.release_lock(first)
        self.assertEqual(original, self.manager.state_path.read_bytes())
        self.assertEqual(self.manager.load_state().concurrency_lock["locked_by"], "worker_b")
        self.manager.release_lock(second)
        self.assertFalse(self.manager.load_state().concurrency_lock["is_locked"])

    def test_valid_token_from_separate_manager_instance(self) -> None:
        correct = self.manager.acquire_lock("worker_a")
        resumed = StateManager(state_dir=self.workdir.name)
        resumed.release_lock(correct)
        self.assertFalse(self.manager.load_state().concurrency_lock["is_locked"])
        next_token = resumed.acquire_lock("worker_b")
        self.manager.release_lock(next_token)

    def test_legacy_active_lease_with_missing_stored_token_fails_closed(self) -> None:
        _ = self.manager.acquire_lock("worker_a")
        state = self.manager.load_state()
        state.concurrency_lock["lock_token"] = ""
        self.manager._atomic_save(state)
        original = self.manager.state_path.read_bytes()

        with self.assertRaises(ConcurrencyLockError):
            self.manager.release_lock("arbitrary")
        self.assertEqual(original, self.manager.state_path.read_bytes())
        self.assertTrue(self.manager.load_state().concurrency_lock["is_locked"])

    def test_releasing_unlocked_state_remains_idempotent(self) -> None:
        self.manager.release_lock("non_owner")
        state = self.manager.load_state()
        self.assertFalse(state.concurrency_lock.get("is_locked", False))


if __name__ == "__main__":
    unittest.main()
