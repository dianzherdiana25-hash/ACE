"""Unit tests for Autonomous Resilient Watchdog & Recovery Controller.

Tests:
1. Resource consumption sampling (CPU, RSS memory, active threads).
2. Merkle tree root calculation, leaf verification, and tamper detection.
3. Merkle state chain verification and corruption detection.
4. Checkpoint auto-recovery from recovery_baseline.json, immutable_baseline.json, and genesis.
5. Automatic hang and stall detection, safe interruption, and diagnostic dump generation.
6. Heartbeat telemetry recorder and periodic background monitor beacons.
7. Cycle context manager and full health reporting.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from ace_host_controller.resilient_watchdog import (
    GENESIS_BASELINE,
    GENESIS_DIGEST,
    CycleStallTimeoutError,
    DiagnosticDump,
    ResilientWatchdog,
    ResourceStats,
    TelemetryBeacon,
    WatchdogConfig,
    compute_merkle_root,
    recover_research_state,
    sample_process_resources,
    verify_merkle_tree,
    verify_state_merkle_chain,
)


class TestResourceStats(unittest.TestCase):
    """Test process resource footprint measurement."""

    def test_sample_process_resources(self):
        stats, sample = sample_process_resources()
        self.assertIsInstance(stats, ResourceStats)
        self.assertGreater(stats.rss_memory_mb, 0.0)
        self.assertGreater(stats.max_rss_mb, 0.0)
        self.assertGreaterEqual(stats.active_threads, 1)
        self.assertGreaterEqual(stats.cpu_user_seconds, 0.0)
        self.assertGreaterEqual(stats.cpu_system_seconds, 0.0)

        # Second sample to calculate CPU delta
        time.sleep(0.02)
        stats2, _ = sample_process_resources(
            prev_cpu_times=sample[0],
            prev_wall_time=sample[1],
        )
        self.assertGreaterEqual(stats2.cpu_percent, 0.0)
        d = stats2.to_dict()
        self.assertIn("rss_memory_mb", d)
        self.assertIn("cpu_percent", d)


class TestMerkleOperations(unittest.TestCase):
    """Test cryptographic Merkle tree root computation and verification."""

    def test_compute_merkle_root_empty(self):
        root = compute_merkle_root([])
        self.assertEqual(root, "0" * 64)

    def test_compute_merkle_root_single(self):
        h1 = hashlib.sha256(b"leaf1").hexdigest()
        root = compute_merkle_root([h1])
        self.assertEqual(root, h1)

    def test_compute_merkle_root_even_leaves(self):
        h1 = hashlib.sha256(b"leaf1").hexdigest()
        h2 = hashlib.sha256(b"leaf2").hexdigest()
        expected = hashlib.sha256((h1 + h2).encode("utf-8")).hexdigest()
        root = compute_merkle_root([h1, h2])
        self.assertEqual(root, expected)
        self.assertTrue(verify_merkle_tree([h1, h2], expected))

    def test_compute_merkle_root_odd_leaves(self):
        h1 = hashlib.sha256(b"leaf1").hexdigest()
        h2 = hashlib.sha256(b"leaf2").hexdigest()
        h3 = hashlib.sha256(b"leaf3").hexdigest()
        # Level 1: pair(h1, h2) and pair(h3, h3)
        p1 = hashlib.sha256((h1 + h2).encode("utf-8")).hexdigest()
        p2 = hashlib.sha256((h3 + h3).encode("utf-8")).hexdigest()
        expected = hashlib.sha256((p1 + p2).encode("utf-8")).hexdigest()
        root = compute_merkle_root([h1, h2, h3])
        self.assertEqual(root, expected)
        self.assertTrue(verify_merkle_tree([h1, h2, h3], expected))

    def test_merkle_tamper_detection(self):
        h1 = hashlib.sha256(b"leaf1").hexdigest()
        h2 = hashlib.sha256(b"leaf2").hexdigest()
        valid_root = compute_merkle_root([h1, h2])

        # Tampered leaf
        h2_tampered = hashlib.sha256(b"leaf2_tampered").hexdigest()
        self.assertFalse(verify_merkle_tree([h1, h2_tampered], valid_root))


class TestStateMerkleChainVerification(unittest.TestCase):
    """Test cryptographic Merkle state chain verification."""

    def test_genesis_state_verification(self):
        genesis_state = {
            "schema_version": "2.0",
            "active_generation_id": GENESIS_BASELINE["root_candidate_id"],
            "cycle_count": 0,
            "completed_cycles": [],
            "immutable_baseline": dict(GENESIS_BASELINE),
            "state_digest": GENESIS_DIGEST,
        }
        ok, msg, last_id = verify_state_merkle_chain(genesis_state)
        self.assertTrue(ok, msg)
        self.assertEqual(last_id, 0)

    def test_multicycle_merkle_chain_valid(self):
        d0 = GENESIS_DIGEST
        d1 = hashlib.sha256(f"{d0}:1:C1:ACCEPTED:sig1".encode("utf-8")).hexdigest()
        d2 = hashlib.sha256(f"{d1}:2:C2:REJECTED:sig2".encode("utf-8")).hexdigest()

        state = {
            "schema_version": "2.0",
            "active_generation_id": "C1",
            "cycle_count": 2,
            "immutable_baseline": dict(GENESIS_BASELINE),
            "completed_cycles": [
                {
                    "cycle_id": 1,
                    "candidate_id": "C1",
                    "prior_digest": d0,
                    "state_digest": d1,
                },
                {
                    "cycle_id": 2,
                    "candidate_id": "C2",
                    "prior_digest": d1,
                    "state_digest": d2,
                },
            ],
            "state_digest": d2,
        }
        ok, msg, last_id = verify_state_merkle_chain(state)
        self.assertTrue(ok, msg)
        self.assertEqual(last_id, 2)

    def test_broken_merkle_prior_digest(self):
        d0 = GENESIS_DIGEST
        d1 = hashlib.sha256(f"{d0}:1:C1:ACCEPTED:sig1".encode("utf-8")).hexdigest()
        tampered_prior = "0" * 64
        d2 = hashlib.sha256(f"{tampered_prior}:2:C2:REJECTED:sig2".encode("utf-8")).hexdigest()

        state = {
            "schema_version": "2.0",
            "active_generation_id": "C1",
            "cycle_count": 2,
            "immutable_baseline": dict(GENESIS_BASELINE),
            "completed_cycles": [
                {
                    "cycle_id": 1,
                    "candidate_id": "C1",
                    "prior_digest": d0,
                    "state_digest": d1,
                },
                {
                    "cycle_id": 2,
                    "candidate_id": "C2",
                    "prior_digest": tampered_prior,
                    "state_digest": d2,
                },
            ],
            "state_digest": d2,
        }
        ok, msg, _ = verify_state_merkle_chain(state)
        self.assertFalse(ok)
        self.assertIn("Merkle chain broken at cycle 2", msg)

    def test_broken_overall_digest(self):
        d0 = GENESIS_DIGEST
        d1 = hashlib.sha256(f"{d0}:1:C1:ACCEPTED:sig1".encode("utf-8")).hexdigest()
        state = {
            "schema_version": "2.0",
            "active_generation_id": "C1",
            "cycle_count": 1,
            "immutable_baseline": dict(GENESIS_BASELINE),
            "completed_cycles": [
                {
                    "cycle_id": 1,
                    "candidate_id": "C1",
                    "prior_digest": d0,
                    "state_digest": d1,
                },
            ],
            "state_digest": "f" * 64,  # Does not match last cycle d1
        }
        ok, msg, _ = verify_state_merkle_chain(state)
        self.assertFalse(ok)
        self.assertIn("State overall digest mismatch", msg)


class TestCheckpointAutoRecovery(unittest.TestCase):
    """Test checkpoint reconstruction from recovery_baseline and immutable_baseline."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ace_watchdog_test_")
        self.state_dir = Path(self.temp_dir)
        self.recovery_path = self.state_dir / "recovery_baseline.json"
        self.immutable_path = self.state_dir / "immutable_baseline.json"
        self.state_path = self.state_dir / "research_state.json"

        # Create valid immutable baseline
        with open(self.immutable_path, "w", encoding="utf-8") as f:
            json.dump(GENESIS_BASELINE, f, indent=2)

        # Create valid recovery baseline with 1 cycle and dangling lock
        d0 = GENESIS_DIGEST
        d1 = hashlib.sha256(f"{d0}:1:C1:ACCEPTED:sig1".encode("utf-8")).hexdigest()
        self.valid_recovery_data = {
            "schema_version": "2.0",
            "active_generation_id": "C1",
            "cycle_count": 1,
            "immutable_baseline": dict(GENESIS_BASELINE),
            "completed_cycles": [
                {
                    "cycle_id": 1,
                    "candidate_id": "C1",
                    "prior_digest": d0,
                    "state_digest": d1,
                }
            ],
            "concurrency_lock": {
                "is_locked": True,
                "locked_by": "dead_worker_999",
                "locked_at": "2026-11-07T00:00:00Z",
                "expires_at": "9999999999",
                "lock_token": "stale_token",
            },
            "state_digest": d1,
            "fail_closed_recovery": {
                "last_known_good_cycle": 1,
                "last_known_good_digest": d1,
                "recovery_count": 0,
            },
        }
        with open(self.recovery_path, "w", encoding="utf-8") as f:
            json.dump(self.valid_recovery_data, f, indent=2)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recover_when_state_missing(self):
        # research_state.json does not exist
        self.assertFalse(self.state_path.exists())
        recovered, source = recover_research_state(
            state_dir=self.state_dir,
            reason="Missing research_state.json",
        )
        self.assertEqual(source, "recovery_baseline.json")
        self.assertTrue(self.state_path.exists())
        self.assertEqual(recovered["cycle_count"], 1)
        # Verify lock was released
        self.assertFalse(recovered["concurrency_lock"]["is_locked"])
        self.assertEqual(recovered["fail_closed_recovery"]["recovery_count"], 1)

    def test_recover_when_state_corrupted_json(self):
        # Write corrupted JSON to research_state.json
        with open(self.state_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID_JSON_TRUNCATED: true, ")

        cfg = WatchdogConfig(state_dir=str(self.state_dir))
        wd = ResilientWatchdog(cfg)
        state = wd.ensure_valid_state()
        self.assertEqual(state["cycle_count"], 1)
        self.assertFalse(state["concurrency_lock"]["is_locked"])

    def test_recover_when_state_merkle_tampered(self):
        # State exists but has invalid Merkle chain
        tampered_state = dict(self.valid_recovery_data)
        tampered_state["state_digest"] = "bad" * 21 + "a"
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(tampered_state, f, indent=2)

        cfg = WatchdogConfig(state_dir=str(self.state_dir))
        wd = ResilientWatchdog(cfg)
        state = wd.ensure_valid_state()
        # Must be restored from clean recovery_baseline.json
        self.assertEqual(state["state_digest"], self.valid_recovery_data["state_digest"])

    def test_fallback_to_immutable_when_recovery_missing(self):
        # Remove recovery baseline
        self.recovery_path.unlink()
        self.assertFalse(self.recovery_path.exists())

        recovered, source = recover_research_state(
            state_dir=self.state_dir,
            reason="Recovery baseline absent",
        )
        self.assertEqual(source, "immutable_baseline.json")
        self.assertEqual(recovered["cycle_count"], 0)
        self.assertEqual(recovered["state_digest"], GENESIS_DIGEST)
        self.assertTrue(self.state_path.exists())
        self.assertTrue(self.recovery_path.exists())

    def test_fallback_to_genesis_when_all_baselines_missing(self):
        # Remove both recovery and immutable baseline
        self.recovery_path.unlink(missing_ok=True)
        self.immutable_path.unlink(missing_ok=True)

        recovered, source = recover_research_state(
            state_dir=self.state_dir,
            reason="All baselines missing",
        )
        self.assertEqual(source, "genesis_fallback")
        self.assertEqual(recovered["cycle_count"], 0)
        self.assertEqual(recovered["state_digest"], GENESIS_DIGEST)


class TestHangAndStallDetection(unittest.TestCase):
    """Test cycle hang detection, timeout interruption, and diagnostic dump generation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ace_hang_test_")
        self.cfg = WatchdogConfig(
            state_dir=self.temp_dir,
            diagnostic_dir=str(Path(self.temp_dir) / "diagnostics"),
            cycle_timeout_seconds=0.15,
            heartbeat_interval_seconds=1.0,
        )
        self.watchdog = ResilientWatchdog(self.cfg)

    def tearDown(self):
        self.watchdog.stop_background_monitor()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_guarded_cycle_success(self):
        def fast_cycle():
            return {"cycle_id": 10, "status": "COMPLETED", "decision": "ACCEPTED"}

        res = self.watchdog.run_guarded_cycle(fast_cycle, cycle_id=10)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(self.watchdog.total_cycles_completed, 1)
        self.assertEqual(self.watchdog.total_cycles_failed, 0)
        self.assertEqual(self.watchdog.last_cycle_id, 10)
        self.assertGreater(self.watchdog.last_cycle_duration, 0.0)

    def test_guarded_cycle_timeout_with_fallback(self):
        def hanging_cycle():
            time.sleep(2.0)
            return {"cycle_id": 11, "status": "COMPLETED"}

        res = self.watchdog.run_guarded_cycle(
            hanging_cycle,
            cycle_id=11,
            timeout_seconds=0.10,
            fallback_on_timeout=True,
        )
        self.assertEqual(res["status"], "TIMED_OUT")
        self.assertEqual(res["decision"], "STALLED")
        self.assertEqual(self.watchdog.total_cycles_failed, 1)

        # Verify diagnostic dump was generated
        diag_files = list(Path(self.cfg.diagnostic_dir).glob("diagnostic_*.json"))
        self.assertGreaterEqual(len(diag_files), 1)

        with open(diag_files[0], "r", encoding="utf-8") as f:
            dump_data = json.load(f)
        self.assertEqual(dump_data["trigger_reason"], "CYCLE_TIMEOUT_EXCEEDED")
        self.assertEqual(dump_data["cycle_id"], 11)
        self.assertIn("thread_stacks", dump_data)
        self.assertIn("resource_stats", dump_data)

    def test_guarded_cycle_timeout_raises_when_fallback_disabled(self):
        def hanging_cycle():
            time.sleep(2.0)

        with self.assertRaises(CycleStallTimeoutError):
            self.watchdog.run_guarded_cycle(
                hanging_cycle,
                cycle_id=12,
                timeout_seconds=0.10,
                fallback_on_timeout=False,
            )
        self.assertEqual(self.watchdog.total_cycles_failed, 1)

    def test_guarded_cycle_exception_handling(self):
        def faulty_cycle():
            raise RuntimeError("Engine failure in cycle computation")

        with self.assertRaises(RuntimeError):
            self.watchdog.run_guarded_cycle(faulty_cycle, cycle_id=13)

        self.assertEqual(self.watchdog.total_cycles_failed, 1)
        self.assertIsNotNone(self.watchdog.last_diagnostic_dump)
        self.assertEqual(
            self.watchdog.last_diagnostic_dump.trigger_reason,
            "EXCEPTION: RuntimeError",
        )


class TestHeartbeatTelemetryRecorder(unittest.TestCase):
    """Test periodic health beacons, throughput calculation, and background monitor."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ace_heartbeat_test_")
        self.cfg = WatchdogConfig(
            state_dir=self.temp_dir,
            diagnostic_dir=str(Path(self.temp_dir) / "diagnostics"),
            heartbeat_file="test_heartbeat.json",
            heartbeat_interval_seconds=0.08,
            cycle_timeout_seconds=1.0,
        )
        self.watchdog = ResilientWatchdog(self.cfg)

    def tearDown(self):
        self.watchdog.stop_background_monitor()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_heartbeat_atomic(self):
        beacon = self.watchdog.record_heartbeat(status="HEALTHY")
        self.assertIsInstance(beacon, TelemetryBeacon)
        self.assertEqual(beacon.beacon_id, 1)
        self.assertEqual(beacon.health_status, "HEALTHY")

        hb_path = Path(self.temp_dir) / "test_heartbeat.json"
        self.assertTrue(hb_path.is_file())

        with open(hb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["beacon_id"], 1)
        self.assertIn("uptime_seconds", data)
        self.assertIn("cycle_throughput_per_hour", data)
        self.assertIn("resource_stats", data)

    def test_background_monitor_thread_lifecycle(self):
        self.watchdog.start_background_monitor()
        # Verify monitor started
        self.assertIsNotNone(self.watchdog._monitor_thread)
        self.assertTrue(self.watchdog._monitor_thread.is_alive())

        # Allow monitor loop to emit periodic beacons
        time.sleep(0.25)

        self.watchdog.stop_background_monitor()
        self.assertIsNone(self.watchdog._monitor_thread)

        # Confirm heartbeat was written by background thread
        hb_path = Path(self.temp_dir) / "test_heartbeat.json"
        self.assertTrue(hb_path.is_file())
        with open(hb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreater(data["beacon_id"], 0)


class TestCycleMonitorScopeAndHealth(unittest.TestCase):
    """Test manual cycle monitoring context manager and health status reporting."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ace_scope_test_")
        self.cfg = WatchdogConfig(
            state_dir=self.temp_dir,
            diagnostic_dir=str(Path(self.temp_dir) / "diagnostics"),
            cycle_timeout_seconds=0.2,
        )
        self.watchdog = ResilientWatchdog(self.cfg)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_monitor_cycle_context_manager(self):
        with self.watchdog.monitor_cycle(cycle_id=42):
            time.sleep(0.02)

        self.assertEqual(self.watchdog.total_cycles_completed, 1)
        self.assertEqual(self.watchdog.last_cycle_id, 42)
        self.assertGreater(self.watchdog.last_cycle_duration, 0.0)

    def test_get_health_status(self):
        health = self.watchdog.get_health_status()
        self.assertIn("uptime_seconds", health)
        self.assertIn("total_cycles_completed", health)
        self.assertIn("total_cycles_failed", health)
        self.assertIn("cycle_throughput_per_hour", health)
        self.assertIn("resource_stats", health)


if __name__ == "__main__":
    unittest.main()
