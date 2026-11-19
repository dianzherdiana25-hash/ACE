"""Tes edge-case dan adversarial Garis D3 untuk ace_self_dev dan ace_runtime."""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from ace_runtime import engine as rt_engine
from ace_self_dev.atomic_lease import (
    ConcurrencyLockError,
    EventConflict,
    FencedStore,
    Lease,
    LeaseRejected,
    StateManager,
)
from ace_self_dev.checkpoint_manager import CheckpointManager
from ace_self_dev.confirmation_suite import create_confirmation_suite
from ace_self_dev.lineage_governor import LineageGovernor
from ace_self_dev.models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    CycleCheckpoint,
    EvaluationReceipt,
    PersistentResearchState,
    ResearchHypothesis,
)
from ace_self_dev.stagnation_detector import BitvectorRegistry, StagnationDetector, StagnationType


def _valid_runtime_task(name: str = "d3-task") -> dict:
    from ace_capability_evolution import compositional as c

    train, validation, _ = c.bank("equal", 20261106)
    return {"name": name, "train": train, "validation": validation}


class FencedStoreEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d3-fenced-")
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "store.sqlite"
        self.store = FencedStore(self.db_path)

    def test_01_symlink_db_path_is_rejected_fail_closed(self) -> None:
        real_db = Path(self.tmp.name) / "real.sqlite"
        real_db.write_bytes(b"")
        sym_db = Path(self.tmp.name) / "sym.sqlite"
        sym_db.symlink_to(real_db)
        with self.assertRaisesRegex(ValueError, "symlink"):
            FencedStore(sym_db)

    def test_02_boundary_expires_at_equal_now_is_rejected_and_reacquirable(self) -> None:
        lease = self.store.acquire("job1", "owner1", ttl=10.0, now=100.0)
        # Strict inequality requires row[3] > now; at exactly now == 110.0 lease is expired.
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(lease, "ev1", {"k": 1}, now=110.0)
        new_lease = self.store.acquire("job1", "owner2", ttl=10.0, now=110.0)
        self.assertGreater(new_lease.epoch, lease.epoch)

    def test_03_append_receipt_rejects_nan_content_and_invalid_event_id(self) -> None:
        lease = self.store.acquire("job1", "owner1", now=100.0)
        with self.assertRaises(ValueError):
            self.store.append_receipt(lease, "bad-nan", {"x": float("nan")}, now=101.0)
        for bad_ev in ("", "   ", "e" * 257):
            with self.assertRaises(ValueError):
                self.store.append_receipt(lease, bad_ev, {"x": 1}, now=101.0)

    def test_04_forged_lease_token_rejected_even_when_epoch_matches(self) -> None:
        real = self.store.acquire("job1", "owner1", now=100.0)
        forged = Lease(real.job_id, real.owner, "0" * 32, real.epoch, real.expires_at)
        with self.assertRaises(LeaseRejected):
            self.store.append_receipt(forged, "ev", {"v": 1}, now=101.0)
        with self.assertRaises(LeaseRejected):
            self.store.release(forged, now=101.0)

    def test_05_ack_outbox_unknown_event_raises_key_error_and_reack_is_idempotent(self) -> None:
        lease = self.store.acquire("job1", "owner1", now=100.0)
        with self.assertRaises(KeyError):
            self.store.ack_outbox(lease, "missing-event", now=101.0)
        self.store.append_receipt(lease, "ev1", {"x": 1}, now=101.0)
        self.store.ack_outbox(lease, "ev1", now=102.0)
        self.store.ack_outbox(lease, "ev1", now=103.0)
        self.assertEqual(self.store.pending_outbox("job1"), [])

    def test_06_ttl_upper_bound_86400_allowed_and_above_rejected(self) -> None:
        lease = self.store.acquire("job-max", "owner1", ttl=86400.0, now=100.0)
        self.assertEqual(lease.expires_at, 86500.0)
        with self.assertRaises(ValueError):
            self.store.acquire("job-over", "owner1", ttl=86400.01, now=100.0)

    def test_07_nan_now_timestamp_must_not_bypass_expired_lease(self) -> None:
        # Bug terdokumentasi di code/ace_self_dev/fenced_store.py: _active() memakai `row[3] <= now`,
        # dan NaN membuat perbandingan IEEE-754 False sehingga lease expired lolos tulis.
        # DIPERBAIKI (gelombang robustness 2026-11-20): _active menolak now tak-hingga/NaN.
        lease = self.store.acquire("job-nan", "owner1", ttl=5.0, now=100.0)
        with self.assertRaises((LeaseRejected, ValueError)):
            self.store.append_receipt(lease, "ev-nan", {"x": 1}, now=math.nan)


class StateManagerAndCheckpointEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d3-state-")
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / "state"
        self.mgr = StateManager(state_dir=str(self.state_dir), lock_ttl_seconds=10.0)

    def test_08_load_state_corrupted_primary_restores_recovery_backup(self) -> None:
        self.mgr.record_completed_cycle(
            cycle_id=1,
            hypothesis_id="h1",
            target_task_id="t1",
            candidate_id="c1",
            source_sha="sha1",
            decision="REJECTED",
            holdout_score=0.6,
            gain_over_parent=0.05,
            rejection_reason="margin",
            evidence_path="ev.json",
            receipt_signature="sig1",
            gene_dict={"a": 1},
            mutation_ordinal=1,
            active_head_id="G0_self_dev_root_c0",
        )
        self.mgr.state_path.write_text("{corrupt_json", encoding="utf-8")
        recovered = self.mgr.load_state()
        self.assertEqual(recovered.cycle_count, 1)
        self.assertEqual(recovered.fail_closed_recovery["recovery_count"], 1)
        self.assertFalse(recovered.concurrency_lock["is_locked"])

    def test_09_load_state_both_primary_and_backup_corrupt_falls_back_to_genesis(self) -> None:
        self.mgr.load_state()
        self.mgr.state_path.write_bytes(b"bad-primary")
        self.mgr.recovery_backup_path.write_bytes(b"bad-backup")
        recovered = self.mgr.load_state()
        self.assertEqual(recovered.cycle_count, 0)
        self.assertEqual(recovered.active_generation_id, "G0_self_dev_root_c0")
        self.assertEqual(recovered.fail_closed_recovery["recovery_count"], 1)

    def test_10_force_unlock_clears_lock_and_allows_reacquisition(self) -> None:
        self.mgr.acquire_lock("worker1")
        with self.assertRaises(ConcurrencyLockError):
            self.mgr.acquire_lock("worker2")
        self.mgr.force_unlock()
        tok2 = self.mgr.acquire_lock("worker2")
        self.mgr.release_lock(tok2)

    def test_11_record_completed_cycle_chains_merkle_digest_and_failure_catalog(self) -> None:
        s1 = self.mgr.record_completed_cycle(
            cycle_id=1,
            hypothesis_id="h1",
            target_task_id="taskA",
            candidate_id="c1",
            source_sha="sha1",
            decision="REJECTED",
            holdout_score=0.5,
            gain_over_parent=0.0,
            rejection_reason="fail",
            evidence_path="e1.json",
            receipt_signature="sig1",
            gene_dict={"k": 1},
            mutation_ordinal=1,
            active_head_id="G0",
        )
        s2 = self.mgr.record_completed_cycle(
            cycle_id=2,
            hypothesis_id="h2",
            target_task_id="taskA",
            candidate_id="c2",
            source_sha="sha2",
            decision="ACCEPTED",
            holdout_score=0.9,
            gain_over_parent=0.4,
            rejection_reason="",
            evidence_path="e2.json",
            receipt_signature="sig2",
            gene_dict={"k": 2},
            mutation_ordinal=2,
            active_head_id="c2",
        )
        self.assertEqual(s2.completed_cycles[1]["prior_digest"], s1.state_digest)
        self.assertEqual(len(s2.failure_catalog["taskA"]), 1)
        self.assertEqual([h["status"] for h in s2.hypotheses_history], ["FALSIFIED", "CONFIRMED"])

    def test_12_acquire_lock_breaks_expired_lease(self) -> None:
        with patch("ace_self_dev.state_manager.time.time", return_value=100.0):
            tok1 = self.mgr.acquire_lock("worker-stale")
        with patch("ace_self_dev.state_manager.time.time", return_value=111.0):
            tok2 = self.mgr.acquire_lock("worker-fresh")
        self.assertNotEqual(tok1, tok2)
        self.assertEqual(self.mgr.load_state().concurrency_lock["locked_by"], "worker-fresh")

    def test_13_checkpoint_manager_save_load_missing_and_overwrite(self) -> None:
        cm = CheckpointManager(str(Path(self.tmp.name) / "ckpts"))
        self.assertFalse(cm.has_checkpoint(99))
        self.assertIsNone(cm.load_checkpoint(99))
        cp1 = CycleCheckpoint(cycle_id=7, phase="INITIALIZED", active_head_id="G0", cost_usd=0.0)
        cm.save_checkpoint(cp1)
        cp2 = CycleCheckpoint(cycle_id=7, phase="REPORTED", active_head_id="C7", decision="ACCEPTED", cost_usd=0.12)
        cm.save_checkpoint(cp2)
        loaded = cm.load_checkpoint(7)
        assert loaded is not None
        self.assertEqual(loaded.phase, "REPORTED")
        self.assertEqual(loaded.active_head_id, "C7")
        self.assertAlmostEqual(loaded.cost_usd, 0.12)
        self.assertFalse((cm.checkpoint_dir / "cycle_0007.tmp").exists())


class StagnationAndGovernorEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d3-stag-")
        self.addCleanup(self.tmp.cleanup)
        self.tasks = create_confirmation_suite(task_seed=42)
        self.task_k2 = self.tasks["task_k2_modular_stride_shift"]

    def test_14_bitvector_registry_corrupt_json_recovers_empty_and_scopes_by_task(self) -> None:
        path = Path(self.tmp.name) / "bv.json"
        path.write_text("{corrupt", encoding="utf-8")
        reg = BitvectorRegistry(path)
        self.assertIsNone(reg.lookup("t1", "h1"))
        reg.register("t1", "same_hash", "cand_1")
        self.assertTrue(reg.has("t1", "same_hash"))
        self.assertFalse(reg.has("t2", "same_hash"))

    def test_15_patience_window_filters_by_task_and_handles_exact_threshold(self) -> None:
        det = StagnationDetector(patience_k=2, min_improvement=0.01)
        state = PersistentResearchState(
            completed_cycles=[
                {"cycle_id": 1, "target_task_id": "t_other", "holdout_score": 0.99},
                {"cycle_id": 2, "target_task_id": "t1", "holdout_score": 0.50},
                {"cycle_id": 3, "target_task_id": "t1", "holdout_score": 0.5099},  # < 0.01 gain
                {"cycle_id": 4, "target_task_id": "t1", "holdout_score": 0.5050},  # count=2 -> stagnated
            ]
        )
        stag, cnt, best, scores = det.check_patience_window(state, task_id="t1")
        self.assertTrue(stag)
        self.assertEqual(cnt, 2)
        self.assertAlmostEqual(best, 0.50)
        self.assertEqual(len(scores), 3)

        # Exact min_improvement resets consecutive count cleanly
        state.completed_cycles.append({"cycle_id": 5, "target_task_id": "t1", "holdout_score": 0.51})
        stag2, cnt2, best2, _ = det.check_patience_window(state, task_id="t1")
        self.assertFalse(stag2)
        self.assertEqual(cnt2, 0)
        self.assertAlmostEqual(best2, 0.51)

    def test_16_strategy_exhaustion_deduplicates_mutation_ordinals(self) -> None:
        det = StagnationDetector(strategy_limits={"LINEAR_MUTATION": 3})
        state = PersistentResearchState(
            failure_catalog={
                "t1": [
                    {"mutation_ordinal": 0, "gene_dict": {}},
                    {"mutation_ordinal": 0, "gene_dict": {}},  # duplicate ordinal
                    {"mutation_ordinal": 1, "gene_dict": {}},
                    {"mutation_ordinal": 2, "gene_dict": {"is_gated": True}},  # different strategy
                ]
            }
        )
        exhausted, attempted, limit, _ = det.check_strategy_exhaustion("LINEAR_MUTATION", "t1", state)
        self.assertFalse(exhausted)
        self.assertEqual(attempted, 2)
        self.assertEqual(limit, 3)

    def test_17_inspect_pre_evaluation_handles_syntax_compile_failure_safely(self) -> None:
        det = StagnationDetector()
        cand = CodeCandidate(
            candidate_id="bad_ast",
            parent_id="G0",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def broken(:",
            source_sha="unique_sha_bad",
            gene_dict={},
        )
        hyp = ResearchHypothesis(hypothesis_id="h", statement="s", target_task_id="t1")
        res = det.inspect_pre_evaluation(cand, hyp, PersistentResearchState(), self.task_k2)
        self.assertTrue(res.is_stagnated)
        self.assertEqual(res.stagnation_type, StagnationType.NONE)
        self.assertFalse(res.should_evaluate)
        self.assertFalse(res.should_commit)

    def test_18_lineage_governor_promotes_accepted_retains_rejected_and_guards_corruption(self) -> None:
        gov = LineageGovernor()

        def _receipt(cand_id: str, decision: CandidateDecision) -> EvaluationReceipt:
            return EvaluationReceipt(
                receipt_id="r1",
                evaluator_manifest_digest="d",
                candidate_id=cand_id,
                parent_id="G0",
                train_score=0.5,
                validation_score=0.5,
                holdout_score=0.5,
                gain_over_parent=0.0,
                prior_regression=0.0,
                decision=decision,
                decision_reason="test",
                evaluator_calls=1,
                cpu_seconds=0.1,
                memory_mb=1.0,
                cost_usd=0.0,
                receipt_signature="sig",
                key_fingerprint="fp",
                timestamp="2026-11-19T00:00:00Z",
            )

        self.assertEqual(gov.apply_decision(_receipt("C1", CandidateDecision.ACCEPTED), fallback_head_id="G0"), ("C1", True))
        for dec in (CandidateDecision.REJECTED, CandidateDecision.BLOCKED, CandidateDecision.STAGNATED, CandidateDecision.ABSTAINED):
            self.assertEqual(gov.apply_decision(_receipt("C2", dec), fallback_head_id="G0"), ("G0", False))

        corrupted_host = SimpleNamespace(lineage=SimpleNamespace(active_head_id="C_BAD"))
        with self.assertRaisesRegex(RuntimeError, "Lineage corruption"):
            gov.apply_decision(_receipt("C_BAD", CandidateDecision.REJECTED), host_controller=corrupted_host)  # type: ignore[arg-type]


class ModelsAndRuntimeEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="d3-rt-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "ws"

    def test_19_code_candidate_and_persistent_state_roundtrip_defaults(self) -> None:
        cand = CodeCandidate(
            candidate_id="c1",
            parent_id="p0",
            author_type=AuthorType.CODEX,
            source_code="x",
            source_sha="s",
            gene_dict={"m": 2},
        )
        rt_cand = CodeCandidate.from_dict(cand.to_dict())
        self.assertEqual(rt_cand, cand)
        st = PersistentResearchState.from_dict({})
        self.assertEqual(st.schema_version, "2.0")
        self.assertEqual(st.completed_cycles, [])
        self.assertFalse(st.concurrency_lock["is_locked"])

    def test_20_encoded_rejects_nan_and_inf(self) -> None:
        with self.assertRaises(ValueError):
            rt_engine.encoded({"x": float("nan")})
        with self.assertRaises(ValueError):
            rt_engine.encoded({"x": float("inf")})

    def test_21_validate_task_rejects_whitespace_names_and_empty_train(self) -> None:
        t = _valid_runtime_task()
        for bad_name in ("", " lead", "trail ", "n" * 81, 123):
            bad = dict(t, name=bad_name)
            with self.assertRaises(ValueError):
                rt_engine.validate_task(bad)
        with self.assertRaises(ValueError):
            rt_engine.validate_task(dict(t, train=[]))

    def test_22_program_from_data_rejects_missing_or_extra_keys_and_dfa_over_budget(self) -> None:
        with self.assertRaises(rt_engine.IntegrityError):
            rt_engine.program_from_data({"kind": "counter"})
        bad_dfa = {
            "kind": "dfa",
            "weights": None,
            "counter_ast": None,
            "fixed_guard": "true",
            "dfa": [[False, [["a", 0], ["b", 0]]] for _ in range(64)],
        }
        with self.assertRaisesRegex(rt_engine.IntegrityError, "budget"):
            rt_engine.program_from_data(bad_dfa)

    def test_23_runtime_report_and_evaluate_before_run_fail_closed(self) -> None:
        t = _valid_runtime_task("pending-only")
        with rt_engine.Runtime(self.ws) as rt:
            tid = rt.enqueue(t)
            with self.assertRaisesRegex(ValueError, "unknown or unfinished"):
                rt.report(tid)
            with self.assertRaisesRegex(ValueError, "unknown or unfinished"):
                rt.predict(tid, "ab")
            with self.assertRaisesRegex(ValueError, "unknown or unfinished"):
                rt.evaluate(tid, t["validation"])

    def test_24_runtime_metadata_tamper_fails_on_reopen(self) -> None:
        with rt_engine.Runtime(self.ws) as rt:
            rt.db.execute("UPDATE metadata SET value='tampered' WHERE key='schema'")
        with self.assertRaisesRegex(rt_engine.IntegrityError, "runtime source/schema changed"):
            rt_engine.Runtime(self.ws)

    def test_25_runtime_pending_task_with_result_and_orphaned_library_detected(self) -> None:
        t = _valid_runtime_task("tamper-task")
        with rt_engine.Runtime(self.ws) as rt:
            tid = rt.enqueue(t)
            rt.db.execute("UPDATE tasks SET result='{\"dummy\":1}' WHERE id=?", (tid,))
        with self.assertRaisesRegex(rt_engine.IntegrityError, "pending task has a result"):
            rt_engine.Runtime(self.ws)

    def test_26_runtime_run_max_tasks_bounds_enforced(self) -> None:
        with rt_engine.Runtime(self.ws) as rt:
            for bad in (0, -1, 257, True, False, "2"):
                with self.assertRaises(ValueError):
                    rt.run(bad)
            self.assertEqual(rt.run(1), [])

    def test_27_runtime_evaluate_rejects_overlap_with_train_or_validation(self) -> None:
        from ace_capability_evolution import compositional as c

        train, validation, terminal = c.bank("equal", 20261106)
        with rt_engine.Runtime(self.ws) as rt:
            tid = rt.enqueue({"name": "overlap-check", "train": train, "validation": validation})
            rt.run(1)
            with self.assertRaisesRegex(ValueError, "overlap"):
                rt.evaluate(tid, [validation[0]] + terminal[:3])

    def test_28_runtime_program_from_data_rejects_noncanonical_dfa_with_extra_edges(self) -> None:
        # Duplicate 'a' edge or unknown edge label must raise IntegrityError
        bad = {
            "kind": "dfa",
            "weights": None,
            "counter_ast": None,
            "fixed_guard": "true",
            "dfa": [[True, [["a", 0], ["a", 0]]]],
        }
        with self.assertRaises(rt_engine.IntegrityError):
            rt_engine.program_from_data(bad)


if __name__ == "__main__":
    unittest.main()
