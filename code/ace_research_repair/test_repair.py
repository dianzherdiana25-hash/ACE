"""Comprehensive unit tests for ACE Fase 5 Autonomous Software Repair (`ace_research_repair`).

Covers:
1. AST import isolation (`evaluator.py` never imported by repair/fit modules),
2. Staging safety (repository files untouched; crashes and infinite loops isolated/timed out),
3. Full 8-stage pipeline, real `ace_runtime.engine.Runtime` integration, and SQLite `RepairMemory`
   persistence + tamper detection across restarts,
4. Anti-overfitting `Verify` gate rejecting `TRAP_overfit` special-case and constant-collapse patches,
5. Safe abstention on `OOD_abstain` bugs and strict candidate budget enforcement,
6. Fail-closed `verify.py` tamper rejection and deterministic canonical replay.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from .corpus import (
    ARMS,
    BUDGET_K,
    FAMILIES,
    DevTestCase,
    canonical_json,
    sha256_digest,
    source_units,
    target_units,
)
from .engine import PIPELINE_STAGES, RepairEngine
from .evaluator import evaluate_target_trial
from .memory import MemoryIntegrityError, RepairMemory
from .runner import compress_deterministic_gzip, decompress_gzip, run_benchmark
from .sandbox import run_dev_suite
from .verify import (
    RepairVerificationError,
    verify_ast_isolation,
    verify_report_bytes,
    verify_upstream_pins,
)


class SoftwareRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        evidence_path = cls.repo_root / "evidence/repair/ace_repair_v1.json.gz"
        if evidence_path.is_file():
            cls.gz_bytes = evidence_path.read_bytes()
            cls.raw_json = decompress_gzip(cls.gz_bytes)
            cls.report = json.loads(cls.raw_json.decode("utf-8"))
        else:
            cls.report = run_benchmark()
            cls.raw_json = canonical_json(cls.report)
            cls.gz_bytes = compress_deterministic_gzip(cls.raw_json)

    def test_1_ast_import_isolation_enforced(self) -> None:
        checked = verify_ast_isolation(Path(__file__).resolve().parent)
        self.assertEqual(checked, 7)

        # Verify tampering with a module to import evaluator is caught immediately
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_pkg = Path(tmp_str)
            src_pkg = Path(__file__).resolve().parent
            for name in ("__init__.py", "corpus.py", "sandbox.py", "operators.py", "represent.py", "memory.py", "engine.py"):
                (tmp_pkg / name).write_text((src_pkg / name).read_text(encoding="utf-8"), encoding="utf-8")
            (tmp_pkg / "engine.py").write_text(
                "from . import evaluator\n" + (tmp_pkg / "engine.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaises(RepairVerificationError):
                verify_ast_isolation(tmp_pkg)

    def test_2_staging_safety_timeout_crash_and_repo_immutability(self) -> None:
        pinned_before = verify_upstream_pins(self.repo_root)
        self.assertEqual(pinned_before, 25)
        corpus_file = Path(__file__).resolve().parent / "corpus.py"
        corpus_sha_before = hashlib.sha256(corpus_file.read_bytes()).hexdigest()

        # Infinite loop candidate safely terminated by timeout/RLIMIT_CPU
        inf_loop_src = """def hang(x):
    while True:
        x = x + 1
    return x
"""
        loop_res = run_dev_suite(
            inf_loop_src,
            "hang",
            (DevTestCase("t1", "call", (1,), 2),),
            timeout_sec=0.6,
            cpu_limit_sec=1,
        )
        self.assertFalse(loop_res["all_passed"])
        self.assertTrue(loop_res["timed_out"] or loop_res["sandbox_error"] is not None)

        # Child process hard exit (`SystemExit`) isolated from parent test runner
        crash_src = """import sys
def boom(x):
    sys.exit(9)
"""
        crash_res = run_dev_suite(
            crash_src,
            "boom",
            (DevTestCase("t1", "call", (1,), 2),),
            timeout_sec=1.5,
            cpu_limit_sec=1,
        )
        self.assertFalse(crash_res["all_passed"])

        # Confirm repository and pinned files remain 100% untouched
        self.assertEqual(verify_upstream_pins(self.repo_root), 25)
        self.assertEqual(hashlib.sha256(corpus_file.read_bytes()).hexdigest(), corpus_sha_before)

    def test_3_eight_stage_pipeline_ace_runtime_and_memory_persistence(self) -> None:
        src_views = [u.public_view() for u in source_units()]
        tgt_map = {u.unit_id: u.public_view() for u in target_units()}

        with tempfile.TemporaryDirectory() as tmp_str:
            ws = Path(tmp_str) / "repair_ws"
            with RepairEngine(ws) as eng:
                receipts = eng.train_source_bank(src_views, budget_k=BUDGET_K)
                self.assertEqual(len(receipts), 8)
                self.assertTrue(all(r["staged"] for r in receipts))
                for r in receipts:
                    self.assertEqual(set(r["stages"].keys()), set(PIPELINE_STAGES))
                    self.assertTrue(r["stages"]["Remember"]["remembered"])

                rt_status = eng.bridge.status()
                mem_status = eng.memory.status()
                self.assertEqual(rt_status["capabilities"], 4)
                self.assertEqual(rt_status["completed"], 8)
                self.assertEqual(mem_status["total_records"], 8)

                phases = [r["stages"]["Represent"]["runtime"]["runtime_phase"] for r in receipts]
                self.assertEqual(phases.count("LEARNED_STAGED"), 4)
                self.assertEqual(phases.count("REUSE_VALIDATED"), 4)

                live_t01 = eng.solve_unit(tgt_map["T01_binary_search_index"], arm="R_ace", remember=False)
                self.assertTrue(live_t01["staged"])

            # Cold restart on same workspace without re-running train_source_bank
            with RepairEngine(ws) as restarted:
                self.assertEqual(restarted.memory.status()["total_records"], 8)
                self.assertEqual(restarted.bridge.status()["capabilities"], 4)
                replay_t01 = restarted.solve_unit(tgt_map["T01_binary_search_index"], arm="R_ace", remember=False)
                self.assertEqual(replay_t01["patched_source_sha256"], live_t01["patched_source_sha256"])
                self.assertEqual(
                    replay_t01["stages"]["Represent"]["runtime"]["runtime_phase"],
                    "REUSE_VALIDATED",
                )
                self.assertFalse(
                    replay_t01["stages"]["Represent"]["runtime"]["runtime_learning_called"]
                )

            # Corrupting RepairMemory SQLite row triggers MemoryIntegrityError on reopen
            db_file = ws / "repair_memory.sqlite3"
            conn = sqlite3.connect(db_file)
            conn.execute("UPDATE repairs SET operator_family = 'tampered' WHERE ordinal = 1")
            conn.commit()
            conn.close()
            with self.assertRaises(MemoryIntegrityError):
                RepairMemory(db_file)

    def test_4_anti_overfitting_gate_rejects_trap_units(self) -> None:
        ace_trials = {t["unit_id"]: t for t in self.report["target_trials_by_arm"]["R_ace"]}
        fresh_trials = {t["unit_id"]: t for t in self.report["target_trials_by_arm"]["R_fresh"]}
        fixed_trials = {t["unit_id"]: t for t in self.report["target_trials_by_arm"]["R_fixed"]}

        for trap_id in ("T17_trap_constant_collapse", "T18_trap_special_case_guard"):
            ace_t = ace_trials[trap_id]
            self.assertFalse(ace_t["staged"])
            self.assertTrue(ace_t["abstained"])
            self.assertGreaterEqual(len(ace_t["verify_rejections"]), 1)
            self.assertFalse(ace_t["terminal"]["overfit_false_admission"])

            # Confirm unverified arms fall into the overfit trap on weak dev tests
            self.assertTrue(
                fresh_trials[trap_id]["terminal"]["overfit_false_admission"]
                or fixed_trials[trap_id]["terminal"]["overfit_false_admission"]
            )

    def test_5_ood_abstention_and_budget_enforcement(self) -> None:
        for arm in ARMS:
            for row in self.report["target_trials_by_arm"][arm]:
                self.assertLessEqual(row["total_candidate_sandbox_evals"], BUDGET_K)
                if row["category"] == "OOD_abstain" and arm == "R_ace":
                    self.assertFalse(row["staged"])
                    self.assertTrue(row["abstained"])
                    self.assertFalse(row["terminal"]["overfit_false_admission"])

        # All 4 families represented and evaluated
        self.assertEqual(tuple(self.report["families"]), FAMILIES)
        for fam in FAMILIES:
            self.assertGreaterEqual(
                self.report["arm_summaries"]["R_ace"]["by_family"][fam]["terminal_verified"],
                2,
            )

    def test_6_verifier_tamper_rejection_and_deterministic_replay(self) -> None:
        # Structure + custody verification passes on clean artifact
        receipt = verify_report_bytes(self.gz_bytes, repo_root=self.repo_root, replay=False)
        self.assertEqual(receipt["canonical_json_sha256"], sha256_digest(self.raw_json))

        # Tamper 1: promote scientific_decision -> rejected
        bad_sci = copy.deepcopy(self.report)
        bad_sci["scientific_decision"] = "GO"
        with self.assertRaises(RepairVerificationError):
            verify_report_bytes(canonical_json(bad_sci), repo_root=self.repo_root, replay=False)

        # Tamper 2: promote release_gate -> rejected
        bad_rel = copy.deepcopy(self.report)
        bad_rel["release_gate"] = "ALLOW_RELEASE"
        with self.assertRaises(RepairVerificationError):
            verify_report_bytes(canonical_json(bad_rel), repo_root=self.repo_root, replay=False)

        # Tamper 3: boolean-to-integer alias (`staged = 1`) -> rejected
        bad_bool = copy.deepcopy(self.report)
        bad_bool["target_trials_by_arm"]["R_ace"][0]["staged"] = 1
        with self.assertRaises(RepairVerificationError):
            verify_report_bytes(canonical_json(bad_bool), repo_root=self.repo_root, replay=False)

        # Tamper 4: non-deterministic OS header byte in gzip -> rejected
        non_det_gz = gzip.compress(self.raw_json, compresslevel=9, mtime=12345)
        with self.assertRaises(RepairVerificationError):
            verify_report_bytes(non_det_gz, repo_root=self.repo_root, replay=False)

        # Tamper 5: fabricated terminal score -> caught by exact replay check
        bad_score = copy.deepcopy(self.report)
        bad_score["arm_summaries"]["R_rule"]["nominal_terminal_verified"] = 12
        with self.assertRaises(RepairVerificationError):
            verify_report_bytes(canonical_json(bad_score), repo_root=self.repo_root, replay=True)


if __name__ == "__main__":
    unittest.main()
