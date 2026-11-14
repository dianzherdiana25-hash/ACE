"""Tests for unified offline OAIE closed-loop engine (`oaie_engine.py`)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.experiment_kernel import ExperimentKernel
from ace_operational.oaie_engine import (
    OAIE_ENGINE_VERSION,
    _build_oaie_stage2_package,
    run_oaie_closed_loop,
)
from ace_operational.population_archive import MixedEvaluatorError, PopulationArchive
from ace_operational.proposer_stage2 import RatificationVocabularyError, Stage2StagingEngine
from ace_operational.self_evolution_engine import SelfEvolutionEngine
from ace_operational.store import OperationalStore


class OaieClosedLoopTests(unittest.TestCase):
    def test_full_g0_to_g3_closed_loop_and_byte_exact_replay_determinism(self):
        with tempfile.TemporaryDirectory(prefix="oaie-r1-") as d1, tempfile.TemporaryDirectory(prefix="oaie-r2-") as d2:
            r1 = run_oaie_closed_loop(d1, seed=20261114)
            r2 = run_oaie_closed_loop(d2, seed=20261114)

            self.assertEqual(r1["engine_version"], OAIE_ENGINE_VERSION)
            self.assertTrue(r1["verified_ok"])
            self.assertEqual(r1["replay_digest"], r2["replay_digest"])

            # Non-regressive growth trajectory G0 <= G1 <= G2 <= G3 and G3 > G0
            gens = r1["generations"]
            self.assertTrue(gens["monotonic_non_decreasing"])
            self.assertGreater(gens["G3"]["solved"], gens["G0"]["solved"])
            self.assertEqual(r1["forgetting_count"], 0)
            self.assertEqual(r1["controls"]["G2"], r1["controls"]["total"])

            # E4 Cross-Family Wake-Sleep Compression & zero-shot transfer on unseen quota_policy
            e4 = r1["e4_abstraction"]
            self.assertGreaterEqual(e4["cross_family_macros"], 1)
            self.assertGreater(e4["compression_ratio"], 1.2)
            self.assertLess(e4["compressed_dl_bits"], e4["flat_dl_bits"])

            unseen = r1["unseen_transfer"]
            self.assertEqual(unseen["solved"], unseen["total"])
            self.assertGreaterEqual(unseen["macro_hits"], 1)
            self.assertLess(unseen["macro_calls"], unseen["flat_calls"])

            # Archive, Split-Custody Kernel, Stage-2 Constitutional Dispatch, OpenWorld Execution, Register
            self.assertTrue(r1["archive_audit"]["replay_matches"])
            self.assertEqual(r1["kernel_audit"]["status"], "CLEAN")
            self.assertEqual(r1["stage2"]["run_status"], "COMPLETED")
            self.assertEqual(r1["stage2"]["preaudit_exit_code"], 0)
            self.assertTrue(r1["stage2"]["ledger_ok"])
            self.assertEqual(r1["frontier_promotion"]["status"], "KNOWN_AND_TESTED")
            self.assertEqual(r1["open_world_execution"]["status"], "COMPLETED")
            self.assertTrue(r1["opportunity_register"]["chain_ok"])

    def test_negative_control_violation_and_mixed_evaluator_and_vocabulary_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="oaie-neg-") as d:
            ws = Path(d)
            # 1. ExperimentKernel flags VIOLATIONS if negative control claims PASS
            k = ExperimentKernel(ws / "k", candidate_key=b"c" * 32, evaluator_key=b"e" * 32)
            ev = b"eval"
            fx = b"fix"
            c_base = b"base"
            c_neg = b"neg"
            k.custody_evaluator("ev-1", ev, fx)
            k.custody_candidate("base", c_base)
            k.custody_candidate("neg", c_neg)
            k.preregister(
                experiment_id="neg-check",
                hypothesis="neg ctrl must not pass",
                protocol={"pass_rule": {"metric": "score", "gte": 0.8}},
                evaluator_id="ev-1",
                budget={"calls": 1},
                candidate_ids=["base", "neg"],
                baseline_candidate_id="base",
                negative_control_id="neg",
            )
            k.record_result(
                experiment_id="neg-check",
                candidate_id="neg",
                candidate_artifact=c_neg,
                metrics={"score": 0.9},
                claimed_verdict="pass",
                raw_telemetry={"t": 1},
            )
            self.assertEqual(k.audit("neg-check")["status"], "VIOLATIONS")

            # 2. PopulationArchive rejects mixing distinct evaluator/protocol/budget evaluations
            arch = PopulationArchive(ws / "arch")
            cid = arch.register_candidate(kind="catalog", descriptor="x", artifact_bytes=b"abc")
            e1 = arch.record_evaluation(
                candidate_id=cid, evaluator_id="e1", protocol="p1", budget={"k": 1}, metrics={"m": 1.0}, outcome="pass"
            )
            e2 = arch.record_evaluation(
                candidate_id=cid, evaluator_id="e2", protocol="p1", budget={"k": 1}, metrics={"m": 2.0}, outcome="pass"
            )
            with self.assertRaises(MixedEvaluatorError):
                arch.assert_comparable([e1, e2])

            # 3. Stage-2 blocks forbidden owner-approval ratification vocabulary
            store = OperationalStore(workspace=ws / "st")
            self.addCleanup(store.close)
            s2 = Stage2StagingEngine(store)
            bad_pkg = _build_oaie_stage2_package(
                proposal_id="bad-vocab",
                claim="Promote with owner_approval",
                rationale="Should be rejected fail-closed",
                archive_state_hash=hashlib.sha256(b"a").hexdigest(),
                kernel_protocol_hash=hashlib.sha256(b"b").hexdigest(),
                catalog_digest=hashlib.sha256(b"c").hexdigest(),
                prereg_id="p0",
            )
            with self.assertRaises(RatificationVocabularyError):
                s2.stage_package(bad_pkg, request_id="req-bad-vocab")

    def test_self_evolution_engine_oaie_hook_promotes_with_receipt_without_local_gguf(self):
        with tempfile.TemporaryDirectory(prefix="oaie-see-") as d:
            store = OperationalStore(workspace=Path(d))
            self.addCleanup(store.close)
            engine = SelfEvolutionEngine(store=store)
            with patch.object(engine.router, "health_check", return_value={"local_gguf": {"ready": False}}):
                res = engine.run_oaie_evolution_cycle(seed=20261114)
            self.assertTrue(res["verified_ok"])
            self.assertEqual(res["open_world_execution"]["status"], "COMPLETED")
            frontier = {c["capability_id"]: c for c in store.list_frontier()}
            self.assertEqual(frontier["cap_oaie_closed_loop"]["status"], "KNOWN_AND_TESTED")
            self.assertTrue(frontier["cap_oaie_closed_loop"]["evidence_ref"].startswith("stage2:"))
            status_doc = json.loads(engine.status_path.read_text(encoding="utf-8"))
            self.assertEqual(status_doc["oaie_replay_digest"], res["replay_digest"])


if __name__ == "__main__":
    unittest.main()
