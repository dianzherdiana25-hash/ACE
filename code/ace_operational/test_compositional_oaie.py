"""Tests for the Zero-Theater Compositional OAIE Engine (`compositional_oaie.py`)."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.compositional_oaie import (
    CompositionalOAIERunner,
    IndependentHoldoutVerifier,
    LearnedSkillRecord,
)
from ace_operational.sovereign_runtime import SporeContinuityError, SubstrateSpore


class CompositionalOAIETests(unittest.TestCase):
    def test_compositional_oaie_full_curriculum_dominance_wake_sleep_and_falsification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_comp_oaie_") as d:
            ws = Path(d)
            report = CompositionalOAIERunner(ws).run(include_falsification=True)

            self.assertEqual(report["schema"], "ace.compositional_oaie.v1")
            self.assertEqual(report["overall_verdict"], "COMPOSITIONAL_OAIE_VERIFIED")

            totals = report["arm_totals"]
            self.assertEqual(totals["ace_evolving"]["solved"], totals["ace_evolving"]["tasks"])
            self.assertEqual(totals["ace_evolving"]["solved"], 14)
            self.assertGreater(totals["ace_evolving"]["solved"], totals["cold_fresh"]["solved"])
            self.assertGreater(totals["ace_evolving"]["solved"], totals["cold_double_budget"]["solved"])
            self.assertGreater(totals["ace_evolving"]["solved"], totals["sham_control"]["solved"])

            # Verify cross-generation Wake-Sleep MDL compression & G4 macro reuse
            gens = {g["generation"]: g for g in report["generations"]}
            g3_ws = gens["G3"]["wake_sleep_compression"]
            self.assertGreater(g3_ws["compression_ratio"], 1.0)
            self.assertLess(g3_ws["compressed_dl_nodes"], g3_ws["flat_dl_nodes"])
            self.assertGreaterEqual(len(g3_ws["macros_discovered"]), 1)

            g4_deps = [dep for t in gens["G4"]["tasks"] for dep in t["ace_evolving"]["deps"]]
            self.assertTrue(any(dep.startswith("macro_ast_") for dep in g4_deps))

            # Verify standalone synthesized .py files are syntactically valid and parse cleanly
            skill_files = sorted((ws / "synthesized_skills").glob("*.py"))
            self.assertEqual(len(skill_files), 14)
            for sf in skill_files:
                ast.parse(sf.read_text(encoding="utf-8"), filename=str(sf))

            # Verify split-custody ExperimentKernel, StigmergicDAG causal lineage & SubstrateSpore
            self.assertEqual(report["experiment_kernel_audit"]["status"], "CLEAN")
            self.assertEqual(report["experiment_kernel_audit"]["ledger_entries_verified"], 4)
            self.assertTrue(report["dag_chain_valid"])
            self.assertGreater(report["causal_lineage_edges"], 0)

            exam = report["spore_continuity_exam"]
            self.assertTrue(exam["exam_passed"])
            self.assertGreater(exam["behavioral_checks_passed"], 0)
            self.assertEqual(exam["forgetting_count"], 0)

            # Verify falsification probes prove honest fail-closed & abstain limits
            fals = report["falsification"]
            self.assertTrue(fals["all_falsification_probes_passed"])
            probes = {p["probe"]: p for p in fals["probes"]}
            self.assertTrue(probes["overfit_deception_trap"]["passed"])
            self.assertTrue(probes["unrepresentable_task_honest_unsat"]["passed"])
            self.assertTrue(probes["trivial_cold_matched_honest_hold"]["passed"])

            # Verify spore behavioral tampering fails closed
            spore_path = ws / "compositional_spore.json"
            spore_doc = json.loads(spore_path.read_text(encoding="utf-8"))
            tampered_doc = json.loads(json.dumps(spore_doc))
            for sk in tampered_doc["certified_skills"]:
                if sk.get("source_code"):
                    sk["source_code"] = sk["source_code"].replace("return ", "return 999999 + ", 1)
                    break
            tampered_path = ws / "tampered_spore.json"
            tampered_path.write_text(json.dumps(tampered_doc), encoding="utf-8")
            with self.assertRaises(SporeContinuityError):
                SubstrateSpore.import_and_verify_spore(
                    spore_path=tampered_path,
                    target_workspace=ws / "tamper_probe",
                    expected_ancestor_skills=["g1_bounded_margin"],
                    antibody_probes=[],
                )

    def test_independent_holdout_verifier_rejects_bool_int_spoof_imports_and_forgetting(self) -> None:
        # 1. Reject forbidden import/exec
        bad_import = IndependentHoldoutVerifier.verify_skill(
            source_code="import os\ndef f(x):\n    return x\n",
            entrypoint="f",
            holdout_io=(({"x": 1}, 1),),
            prior_skills=[],
        )
        self.assertFalse(bad_import["verified"])
        self.assertEqual(bad_import["failure_reason"], "forbidden_import")

        # 2. Reject Python bool-as-int coercion (`True == 1`)
        bool_spoof = IndependentHoldoutVerifier.verify_skill(
            source_code="def f(x):\n    return True\n",
            entrypoint="f",
            holdout_io=(({"x": 1}, 1),),
            prior_skills=[],
        )
        self.assertFalse(bool_spoof["verified"])
        self.assertEqual(bool_spoof["holdout_passed"], 0)

        # 3. Detect catastrophic forgetting if an ancestor skill breaks
        broken_prior = LearnedSkillRecord(
            skill_id="prior_broken",
            component_name="skill_prior",
            entrypoint="prior_fn",
            arg_names=("x",),
            arg_types=("int",),
            return_type="int",
            expr_code="(x + 999)",
            program_ast=None,  # type: ignore[arg-type]
            deps=(),
            dag_node_id="proof_prior",
            standalone_source="def prior_fn(x):\n    return x + 999\n",
            birth_sha256="0" * 64,
            holdout_io=(({"x": 1}, 2),),
        )
        reg_check = IndependentHoldoutVerifier.verify_skill(
            source_code="def f(x):\n    return x + 1\n",
            entrypoint="f",
            holdout_io=(({"x": 2}, 3),),
            prior_skills=[broken_prior],
        )
        self.assertFalse(reg_check["verified"])
        self.assertEqual(reg_check["forgetting_count"], 1)


if __name__ == "__main__":
    unittest.main()
