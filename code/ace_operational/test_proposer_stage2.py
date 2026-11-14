"""Tests for Proposer Engine Stage 2 (Isolated Staging & Constitution Engine)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from ace_mission.bus import MissionBus
from ace_operational import preaudit_validator
from ace_operational.proposer_episodes import load_episodes
from ace_operational.proposer_stage2 import (
    AutoRetryBlockedError,
    BlobIntegrityError,
    DoNotRunError,
    EnvironmentIsolationError,
    LedgerTamperError,
    RatificationError,
    RatificationVocabularyError,
    RequestConflictError,
    RevokedError,
    Stage2StagingEngine,
    StagingEnvironmentProfile,
    ValidationRejectedError,
    package_sha256,
)
from ace_operational.store import OperationalStore
from ace_operational.test_proposer_engine import valid_package


class _FakeClock:
    def __init__(self, initial: float = 1_700_000_000.0):
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, delta: float) -> float:
        self.now += delta
        return self.now


class ProposerStage2Tests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.ws = Path(self._td.name) / "ws"
        self.store = OperationalStore(self.ws)
        self.bus = MissionBus(self.ws / "mission_bus.sqlite3")
        self.clock = _FakeClock()
        self.engine = Stage2StagingEngine(
            self.store,
            mission_bus=self.bus,
            now_fn=self.clock,
        )
        self.ep = load_episodes()[0]

    def tearDown(self):
        self.store.close()
        self._td.cleanup()

    def _pkg(self, *, recommended: str | None = None, max_calls: int = 4,
             max_wall: int = 30, max_cost: float = 2.0) -> dict:
        pkg = valid_package(self.ep)
        pkg["cost_estimate"] = {"calls": 1, "wall_seconds": 5, "cost_units": 0.2}
        pkg["cost_ceiling"] = {
            "max_calls": max_calls,
            "max_wall_seconds": max_wall,
            "max_cost_units": max_cost,
        }
        if recommended is not None:
            pkg["recommended_option"] = recommended
        return pkg

    def test_stage_and_dispatch_end_to_end_with_preaudit_sesuai(self):
        pkg = self._pkg()
        sha = package_sha256(pkg)
        staged, created = self.engine.stage_package(pkg, request_id="req-e2e-001")
        self.assertTrue(created)
        self.assertEqual(staged["identity_mode"], "staging-only")
        self.assertEqual(staged["payload_sha256"], sha)
        self.assertTrue(staged["mission_id"].startswith("mission_"))
        self.assertTrue(self.bus.verify_hash_chain())
        self.assertTrue(self.bus.verify_evaluation_journal())

        # Stage-2 package awaits internal ratification before dispatch.
        with self.assertRaises(RatificationError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)

        rat = self.engine.ratify_staged(
            staged["staging_id"],
            audience="kernel",
            payload_sha256=sha,
            ttl_seconds=120.0,
        )
        self.assertEqual(rat["bound_payload_sha256"], sha)

        run1 = self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)
        self.assertEqual(run1["status"], "COMPLETED")
        self.assertEqual(run1["identity_mode"], "staging-only")
        self.assertTrue(run1["stop_visible"])
        self.assertEqual(run1["preaudit_exit_code"], 0)
        self.assertEqual(run1["calls_used"], 1)
        self.assertGreaterEqual(run1["work_completed_units"], 1)

        # Verify real enforcer versions are pinned in the isolated environment snapshot.
        enforcers = run1["env_snapshot"]["enforcer_versions"]
        self.assertIn("proposer_validator", enforcers)
        self.assertIn("preaudit_validator", enforcers)
        self.assertEqual(len(enforcers["proposer_stage2"]["source_sha256"]), 64)

        # Independent mechanical pre-audit verification of the emitted frozen bundle.
        bundle = Path(run1["bundle_dir"])
        manifest_path = bundle / "manifest.json"
        report = preaudit_validator.validate(manifest_path.read_bytes(), bundle / "source")
        self.assertEqual(report["summary_by_state"][preaudit_validator.TIDAK_SESUAI], 0)
        self.assertEqual(report["summary_by_state"][preaudit_validator.UNKNOWN], 0)
        self.assertEqual(report["unlisted_files_informational_only"], 0)

        # Intentional replication mints a fresh execution_run_id (#8C).
        run2 = self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)
        self.assertNotEqual(run1["execution_run_id"], run2["execution_run_id"])
        self.assertEqual(run2["status"], "COMPLETED")
        self.assertTrue(self.engine.verify_ledger())

    def test_idempotent_staging_and_request_conflict_rejected(self):
        pkg = self._pkg()
        s1, c1 = self.engine.stage_package(pkg, request_id="req-idem-1")
        s2, c2 = self.engine.stage_package(pkg, request_id="req-idem-1")
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(s1["staging_id"], s2["staging_id"])

        mutated = self._pkg()
        mutated["claim"] = "Different claim using the exact same request_id must fail."
        with self.assertRaises(RequestConflictError):
            self.engine.stage_package(mutated, request_id="req-idem-1")
        self.assertTrue(self.engine.verify_ledger())

    def test_forbidden_owner_vocabulary_and_audience_rejected(self):
        pkg = self._pkg()
        with self.assertRaises(RatificationVocabularyError):
            self.engine.stage_package(pkg, request_id="req-owner_approval-bad")

        staged, _ = self.engine.stage_package(pkg, request_id="req-vocab-ok")
        sha = staged["payload_sha256"]

        for bad_aud in ("owner", "external_human", "izin_pemilik"):
            with self.assertRaises(RatificationVocabularyError):
                self.engine.ratify_staged(staged["staging_id"], audience=bad_aud, payload_sha256=sha)

        with self.assertRaises(RatificationVocabularyError):
            self.engine.ratify_staged(
                staged["staging_id"],
                audience="hub",
                payload_sha256=sha,
                ratified_by="persetujuan_pemilik:bypass",
            )

        with self.assertRaises(ValidationRejectedError):
            bad_pkg = self._pkg()
            bad_pkg["stop_controls"]["no_auto_retry"] = False
            self.engine.stage_package(bad_pkg, request_id="req-bad-pkg")

    def test_payload_hash_pin_and_expiry_fail_closed(self):
        pkg = self._pkg()
        staged, _ = self.engine.stage_package(pkg, request_id="req-hash-ttl")
        sha = staged["payload_sha256"]

        with self.assertRaises(RatificationError):
            self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256="0" * 64)

        with self.assertRaises(RatificationError):
            self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256=sha, ttl_seconds=0)

        self.engine.ratify_staged(staged["staging_id"], audience="evidence", payload_sha256=sha, ttl_seconds=10.0)
        with self.assertRaises(RatificationError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256="f" * 64)

        self.clock.advance(10.0)
        with self.assertRaises(RatificationError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)

    def test_irrevocable_revocation_effective_seq_and_blocks_reratify(self):
        pkg = self._pkg()
        staged, _ = self.engine.stage_package(pkg, request_id="req-revoke-01")
        sha = staged["payload_sha256"]
        self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256=sha, ttl_seconds=300)

        run_ok = self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)
        self.assertEqual(run_ok["status"], "COMPLETED")

        revoked = self.engine.revoke_staged(
            staged["staging_id"],
            actor="hub",
            reason="evidence superseded before replication",
        )
        self.assertTrue(revoked["revoked"])
        self.assertGreater(revoked["revocation_ledger_seq"], 0)

        # Revocation is irrevocable: neither re-ratification nor new dispatch is permitted.
        with self.assertRaises(RevokedError):
            self.engine.ratify_staged(staged["staging_id"], audience="kernel", payload_sha256=sha, ttl_seconds=300)
        with self.assertRaises(RevokedError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)

    def test_visible_stop_accounts_inflight_cost_and_blocks_auto_retry(self):
        pkg = self._pkg(max_calls=10, max_wall=60, max_cost=5.0)
        staged, _ = self.engine.stage_package(pkg, request_id="req-stop-01")
        sha = staged["payload_sha256"]
        self.engine.ratify_staged(staged["staging_id"], audience="kernel", payload_sha256=sha, ttl_seconds=120)

        entered_step2 = threading.Event()
        allow_step2_check = threading.Event()
        holder: dict = {}

        def worker(ctx, _pkg):
            ctx.record_step(
                step_name="step_1",
                calls=2,
                cost_units=0.35,
                work_units=3,
                dummy_artifact_rel="step1.txt",
                dummy_content=b"partial-ok",
            )
            self.clock.advance(1.5)
            entered_step2.set()
            allow_step2_check.wait(timeout=5.0)
            # Step 2 triggers visible stop check with partial work already accounted cleanly.
            ctx.record_step(step_name="step_2", calls=1, cost_units=0.25, work_units=2)
            return {"should_not_finish": True}

        t = threading.Thread(
            target=lambda: holder.setdefault(
                "run",
                self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha, worker=worker),
            ),
            daemon=True,
        )
        t.start()
        self.assertTrue(entered_step2.wait(timeout=5.0))

        running = self.engine.list_runs(staged["staging_id"])
        self.assertEqual(len(running), 1)
        run_id = running[0]["execution_run_id"]
        self.assertTrue(self.engine.request_stop(run_id, reason="operator_visible_halt"))
        self.clock.advance(0.25)
        allow_step2_check.set()
        t.join(timeout=5.0)

        stopped_run = holder["run"]
        self.assertEqual(stopped_run["status"], "STOPPED")
        self.assertTrue(stopped_run["stop_visible"])
        self.assertTrue(stopped_run["stop_requested"])
        self.assertEqual(stopped_run["stop_reason"], "operator_visible_halt")
        self.assertEqual(stopped_run["calls_used"], 2)
        self.assertAlmostEqual(stopped_run["cost_units"], 0.35, places=6)
        self.assertEqual(stopped_run["work_completed_units"], 3)
        self.assertAlmostEqual(stopped_run["result_summary"]["stop_latency_seconds"], 0.25, places=6)
        self.assertEqual(stopped_run["preaudit_exit_code"], 0)

        # no_auto_retry=True blocks automatic re-dispatch of a STOPPED staged package.
        with self.assertRaises(AutoRetryBlockedError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)

    def test_midflight_revocation_halts_run_and_records_effective_seq(self):
        pkg = self._pkg(max_calls=10, max_wall=60, max_cost=5.0)
        staged, _ = self.engine.stage_package(pkg, request_id="req-mid-revoke")
        sha = staged["payload_sha256"]
        self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256=sha, ttl_seconds=120)

        step1_done = threading.Event()
        proceed = threading.Event()
        holder: dict = {}

        def worker(ctx, _pkg):
            ctx.record_step(step_name="step_1", calls=1, cost_units=0.1, work_units=1)
            step1_done.set()
            proceed.wait(timeout=5.0)
            ctx.record_step(step_name="step_2", calls=1, cost_units=0.1, work_units=1)

        t = threading.Thread(
            target=lambda: holder.setdefault(
                "run",
                self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha, worker=worker),
            ),
            daemon=True,
        )
        t.start()
        self.assertTrue(step1_done.wait(timeout=5.0))
        rev = self.engine.revoke_staged(staged["staging_id"], actor="evidence", reason="midflight_anomaly")
        proceed.set()
        t.join(timeout=5.0)

        run = holder["run"]
        self.assertEqual(run["status"], "STOPPED")
        self.assertIn(f"revoked_at_seq:{rev['revocation_ledger_seq']}", run["stop_reason"])
        self.assertEqual(run["calls_used"], 1)
        self.assertEqual(run["preaudit_exit_code"], 0)

    def test_ceilings_and_do_not_run_enforced_fail_closed(self):
        # Calls ceiling
        pkg_calls = self._pkg(max_calls=1, max_wall=60, max_cost=5.0)
        s_calls, _ = self.engine.stage_package(pkg_calls, request_id="req-ceil-calls")
        self.engine.ratify_staged(s_calls["staging_id"], audience="kernel", payload_sha256=s_calls["payload_sha256"])

        def exceed_calls(ctx, _pkg):
            ctx.record_step(step_name="s1", calls=1, cost_units=0.1, work_units=1)
            ctx.record_step(step_name="s2", calls=1, cost_units=0.1, work_units=1)

        r_calls = self.engine.dispatch_staged(
            s_calls["staging_id"], expected_payload_sha256=s_calls["payload_sha256"], worker=exceed_calls
        )
        self.assertEqual(r_calls["status"], "ABORTED_CEILING")
        self.assertEqual(r_calls["calls_used"], 1)
        self.assertEqual(r_calls["preaudit_exit_code"], 0)

        # Wall ceiling via fake clock
        pkg_wall = self._pkg(max_calls=10, max_wall=5, max_cost=5.0)
        s_wall, _ = self.engine.stage_package(pkg_wall, request_id="req-ceil-wall")
        self.engine.ratify_staged(s_wall["staging_id"], audience="kernel", payload_sha256=s_wall["payload_sha256"])

        def exceed_wall(ctx, _pkg):
            ctx.record_step(step_name="s1", calls=1, cost_units=0.1, work_units=1)
            self.clock.advance(6.0)
            ctx.record_step(step_name="s2", calls=1, cost_units=0.1, work_units=1)

        r_wall = self.engine.dispatch_staged(
            s_wall["staging_id"], expected_payload_sha256=s_wall["payload_sha256"], worker=exceed_wall
        )
        self.assertEqual(r_wall["status"], "ABORTED_CEILING")
        self.assertIn("max_wall_seconds", r_wall["stop_reason"])

        # do_not_run recommendation refuses active dispatch
        pkg_dnr = self._pkg(recommended="do_not_run")
        s_dnr, _ = self.engine.stage_package(pkg_dnr, request_id="req-dnr-01")
        self.engine.ratify_staged(s_dnr["staging_id"], audience="hub", payload_sha256=s_dnr["payload_sha256"])
        with self.assertRaises(DoNotRunError):
            self.engine.dispatch_staged(s_dnr["staging_id"], expected_payload_sha256=s_dnr["payload_sha256"])

    def test_environment_isolation_rejects_live_identity_egress_creds_and_escapes(self):
        pkg = self._pkg()
        staged, _ = self.engine.stage_package(pkg, request_id="req-env-01")
        sha = staged["payload_sha256"]
        self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256=sha)

        base_dummy = self.engine.dummy_base_dir / "custom_sub"
        bad_profiles = [
            StagingEnvironmentProfile(
                identity_mode="production",
                effective_identity="staging:x",
                egress_blocked=True,
                dummy_credentials_only=True,
                dummy_credentials={"k": "dummy_1"},
                dummy_resource_root=base_dummy,
            ),
            StagingEnvironmentProfile(
                identity_mode="staging-only",
                effective_identity="staging:x",
                egress_blocked=False,
                dummy_credentials_only=True,
                dummy_credentials={"k": "dummy_1"},
                dummy_resource_root=base_dummy,
            ),
            StagingEnvironmentProfile(
                identity_mode="staging-only",
                effective_identity="staging:x",
                egress_blocked=True,
                dummy_credentials_only=True,
                dummy_credentials={"token": "ghp_reallookingsecret"},
                dummy_resource_root=base_dummy,
            ),
            StagingEnvironmentProfile(
                identity_mode="staging-only",
                effective_identity="staging:x",
                egress_blocked=True,
                dummy_credentials_only=True,
                dummy_credentials={"k": "dummy_1"},
                dummy_resource_root=Path("/tmp/outside_staging"),
            ),
        ]
        for prof in bad_profiles:
            with self.assertRaises(EnvironmentIsolationError):
                self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha, env_profile=prof)

        # In-step path escape fails worker cleanly without touching outside paths
        def escaping_worker(ctx, _pkg):
            ctx.record_step(
                step_name="escape",
                calls=1,
                cost_units=0.1,
                work_units=0,
                dummy_artifact_rel="../escaped.txt",
                dummy_content=b"nope",
            )

        r_esc = self.engine.dispatch_staged(
            staged["staging_id"], expected_payload_sha256=sha, worker=escaping_worker
        )
        self.assertEqual(r_esc["status"], "FAILED")
        self.assertFalse((self.engine.dummy_base_dir / "escaped.txt").exists())

    def test_immutable_blob_before_commit_and_ledger_tamper_detection(self):
        pkg = self._pkg()
        staged, _ = self.engine.stage_package(pkg, request_id="req-blob-commit")
        sha = staged["payload_sha256"]
        self.engine.ratify_staged(staged["staging_id"], audience="evidence", payload_sha256=sha)

        def corrupt_bundle(pkg_dir: Path) -> None:
            p = pkg_dir / "execution_summary.json"
            os.chmod(p, 0o600)
            p.write_bytes(b'{"tampered":true}')

        with self.assertRaises(BlobIntegrityError):
            self.engine.dispatch_staged(
                staged["staging_id"],
                expected_payload_sha256=sha,
                pre_commit_bundle_hook=corrupt_bundle,
            )

        # Because immutable-blob verification failed before DB commit, finalize never committed.
        runs = self.engine.list_runs(staged["staging_id"])
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "RUNNING")
        self.assertEqual(runs[0]["bundle_manifest_sha256"], "")

        # Direct SQLite tampering breaks ledger verification fail-closed.
        with sqlite3.connect(str(self.store.db_path)) as con:
            con.execute("UPDATE proposer_stage2_ledger SET detail_json = '{\"tampered\":1}' WHERE seq = 1")
            con.commit()
        self.assertFalse(self.engine.verify_ledger())
        with self.assertRaises(LedgerTamperError):
            self.engine.stage_package(self._pkg(), request_id="req-after-tamper")

    def test_stage_pre_commit_blob_integrity_and_enforcer_digests(self):
        import hashlib
        pkg = self._pkg()
        sha = package_sha256(pkg)

        def abort_blob(path: Path) -> None:
            os.chmod(path, 0o600)
            path.write_bytes(b'{"tampered":"staging"}')

        with self.assertRaises(BlobIntegrityError):
            self.engine.stage_package(pkg, request_id="req-stage-abort", pre_commit_blob_hook=abort_blob)

        # Fail-closed #8C: nothing was committed to proposer_staged_packages.
        expected_id = "stg_" + hashlib.sha256(f"req-stage-abort:{sha}".encode("utf-8")).hexdigest()[:20]
        self.assertIsNone(self.engine.get_staged(expected_id))

        # Now stage cleanly and verify DB-tampered audience fails closed before dispatch.
        staged, created = self.engine.stage_package(pkg, request_id="req-enforcer-check")
        self.assertTrue(created)
        rat = self.engine.ratify_staged(staged["staging_id"], audience="hub", payload_sha256=sha)
        with sqlite3.connect(str(self.store.db_path)) as con:
            con.execute(
                "UPDATE proposer_stage2_ratifications SET audience = 'owner_approval' WHERE ratification_id = ?",
                (rat["ratification_id"],),
            )
            con.commit()
        with self.assertRaises(RatificationVocabularyError):
            self.engine.dispatch_staged(staged["staging_id"], expected_payload_sha256=sha)

        # Clean package dispatch binds exact SHA-256 of real runtime enforcers on disk.
        staged2, _ = self.engine.stage_package(pkg, request_id="req-enforcer-clean")
        self.engine.ratify_staged(staged2["staging_id"], audience="evidence", payload_sha256=sha)
        run = self.engine.dispatch_staged(staged2["staging_id"], expected_payload_sha256=sha)
        enforcers = run["env_snapshot"]["enforcer_versions"]
        base_dir = Path(__file__).resolve().parent
        expected_files = {
            "proposer_validator": base_dir / "proposer_validator.py",
            "preaudit_validator": base_dir / "preaudit_validator.py",
            "proposer_stage2": base_dir / "proposer_stage2.py",
            "operational_store": base_dir / "store.py",
        }
        for key, path in expected_files.items():
            actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(enforcers[key]["source_sha256"], actual_sha)

    def test_constitution_battery_over_frozen_stage1_v2_packages(self):
        from ace_operational.proposer_stage2_battery import run_stage2_constitution_battery

        repo_root = Path(__file__).resolve().parents[2]
        report = run_stage2_constitution_battery(repo_root)
        self.assertTrue(report["all_passed"])
        self.assertEqual(report["checks_total"], 7)
        self.assertEqual(report["checks_passed"], 7)
        self.assertEqual(len(report["source_packages"]), 6)
        self.assertEqual(report["identity_mode"], "staging-only")
        for chk in report["checks"]:
            self.assertTrue(chk["passed"], msg=f"Battery check failed: {chk}")


if __name__ == "__main__":
    unittest.main()
