"""Tests for AI-Agnostic Passive Evolution Work-Order Loop (`evolution_mission_loop.py`)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational.evolution_mission_loop import (
    EvolutionPatchVerifier,
    PassiveEvolutionPlanner,
    RealRepoAuditor,
)


def _create_sandbox_repo(root: Path, *, target_src: str, test_src: str) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "code" / "ace_runtime").mkdir(parents=True, exist_ok=True)
    (root / "code" / "ace_operational").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "UPSTREAM_SOURCES.json").write_text(
        json.dumps({"schema": "ace.source-integration.v1", "files": {"code/ace_runtime/protected.py": {"git_blob": "0"}}}),
        encoding="utf-8",
    )
    (root / "code" / "ace_runtime" / "protected.py").write_text('"""Protected."""\nVALUE = 1\n', encoding="utf-8")
    (root / "code" / "ace_operational" / "__init__.py").write_text('"""Package."""\n', encoding="utf-8")
    (root / "code" / "ace_operational" / "target_mod.py").write_text(target_src, encoding="utf-8")
    (root / "code" / "ace_operational" / "test_target_mod.py").write_text(test_src, encoding="utf-8")


class EvolutionMissionLoopTests(unittest.TestCase):
    def test_multi_generation_emit_fix_ratify_lineage_and_hold_when_clean(self) -> None:
        initial_target = (
            "def parse_positive(raw: str) -> int:\n"
            "    try:\n"
            "        val = int(raw)\n"
            "        return max(0, val)\n"
            "    except Exception:\n"
            "        pass\n"
            "    return 0\n"
            "\n"
            "def extra_padding_one(x: int) -> int:\n"
            "    return x + 1\n"
            "\n"
            "def extra_padding_two(x: int) -> int:\n"
            "    return x + 2\n"
        )
        initial_test = (
            "import unittest\n"
            "from ace_operational.target_mod import parse_positive\n\n"
            "class TargetTests(unittest.TestCase):\n"
            "    def test_parse(self) -> None:\n"
            "        self.assertEqual(parse_positive('5'), 5)\n"
            "        self.assertEqual(parse_positive('bad'), 0)\n"
        )
        with tempfile.TemporaryDirectory(prefix="ace_evo_loop_") as d:
            base = Path(d)
            repo = base / "repo"
            ws = base / "ws"
            _create_sandbox_repo(repo, target_src=initial_target, test_src=initial_test)

            planner = PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational")

            # Gen 1: Highest severity finding is silent_except_pass
            plan1 = planner.plan_next_evolution(test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan1["status"], "MISSION_EMITTED")
            self.assertEqual(plan1["generation_seq"], 1)
            self.assertEqual(plan1["top_finding"]["kind"], "silent_except_pass")
            self.assertTrue((ws / "EVOLUTION_WORK_ORDER.json").is_file())
            self.assertTrue((ws / "EVOLUTION_WORK_ORDER.md").is_file())
            self.assertTrue((ws / "EVOLUTION_BACKLOG.json").is_file())
            self.assertIn(plan1["order_id"], (ws / "EVOLUTION_WORK_ORDER.md").read_text(encoding="utf-8"))

            # External AI fixes silent_except_pass while keeping behavior & still missing module docstring
            fixed_g1 = initial_target.replace(
                "    except Exception:\n        pass\n",
                "    except ValueError:\n        return 0\n",
            )
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(fixed_g1, encoding="utf-8")

            ver1 = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertTrue(ver1["accepted"], msg=str(ver1))
            self.assertEqual(ver1["status"], "VERIFIED_AND_RATIFIED")
            self.assertEqual(ver1["forgetting_count"], 0)
            self.assertTrue(ver1["dag_chain_valid"])
            self.assertEqual(ver1["parent_ids"], [])
            self.assertTrue((ws / "evolution_spore.json").is_file())

            # Gen 2: Planner advances to missing_module_docstring
            plan2 = planner.plan_next_evolution(test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan2["status"], "MISSION_EMITTED")
            self.assertEqual(plan2["generation_seq"], 2)
            self.assertEqual(plan2["top_finding"]["kind"], "missing_module_docstring")

            # External AI adds module docstring
            fixed_g2 = '"""Positive integer parsing helpers."""\n' + fixed_g1
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(fixed_g2, encoding="utf-8")

            ver2 = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertTrue(ver2["accepted"], msg=str(ver2))
            self.assertEqual(ver2["parent_ids"], [f"ratify_{plan1['order_id']}".replace("ratify_", "proof_ratify_")])
            self.assertTrue(ver2["dag_chain_valid"])

            # Gen 3: No open findings remain -> honest HOLD
            plan3 = planner.plan_next_evolution(test_modules=["ace_operational.test_target_mod"])
            self.assertEqual(plan3["status"], "HOLD_NO_ACTIONABLE_FINDINGS")
            self.assertEqual(plan3["open_findings_count"], 0)

    def test_adversarial_patches_fail_closed_and_quarantine(self) -> None:
        base_target = (
            '"""Target module."""\n'
            "def compute(x: int) -> int:\n"
            "    try:\n"
            "        return int(x)\n"
            "    except Exception:\n"
            "        pass\n"
            "    return 0\n"
        )
        base_test = (
            '"""Tests."""\n'
            "import unittest\n"
            "from ace_operational.target_mod import compute\n\n"
            "class ComputeTests(unittest.TestCase):\n"
            "    def test_compute(self) -> None:\n"
            "        self.assertEqual(compute(3), 3)\n"
            "        self.assertEqual(compute(0), 0)\n"
        )

        # 1. No-op edit rejected
        with tempfile.TemporaryDirectory(prefix="ace_evo_noop_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertEqual(res["status"], "REJECTED_AND_QUARANTINED")
            self.assertIn("no_target_changes_detected", res["reasons"])

        # 2. Forbidden protected custody edit rejected
        with tempfile.TemporaryDirectory(prefix="ace_evo_forb_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            (repo / "code" / "ace_runtime" / "protected.py").write_text('"""Tampered."""\nVALUE = 2\n', encoding="utf-8")
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(
                base_target.replace("except Exception:\n        pass", "except ValueError:\n        return 0"),
                encoding="utf-8",
            )
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertTrue(any("forbidden_paths_modified" in r for r in res["reasons"]))

        # 3. Newly added hardcoded `"verified": True` bypass rejected by AST anti-cheat
        with tempfile.TemporaryDirectory(prefix="ace_evo_cheat_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            cheated = (
                base_target.replace("except Exception:\n        pass", "except ValueError:\n        return 0")
                + "\ndef fake_gate():\n    return {'verified': True}\n"
            )
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(cheated, encoding="utf-8")
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertTrue(any("added_unguarded_verified_true" in r for r in res["reasons"]))

        # 4. Deleted test assertions rejected by AST anti-cheat
        with tempfile.TemporaryDirectory(prefix="ace_evo_assert_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(
                base_target.replace("except Exception:\n        pass", "except ValueError:\n        return 0"),
                encoding="utf-8",
            )
            (repo / "code" / "ace_operational" / "test_target_mod.py").write_text(
                base_test.replace("        self.assertEqual(compute(0), 0)\n", ""),
                encoding="utf-8",
            )
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertTrue(any("assertions_weakened" in r for r in res["reasons"]))

        # 5. Functional regression breaks acceptance test -> fail closed
        with tempfile.TemporaryDirectory(prefix="ace_evo_reg_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            broken = (
                '"""Target module."""\n'
                "def compute(x: int) -> int:\n"
                "    return 999\n"
            )
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(broken, encoding="utf-8")
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertTrue(any("acceptance_checks_failed" in r for r in res["reasons"]))

        # 6. Tampered work order JSON rejected fail-closed
        with tempfile.TemporaryDirectory(prefix="ace_evo_tamp_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=base_target, test_src=base_test)
            PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            wo_path = ws / "EVOLUTION_WORK_ORDER.json"
            doc = json.loads(wo_path.read_text(encoding="utf-8"))
            doc["goal"] = "Tampered goal"
            wo_path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()

    def test_compositional_report_capability_gaps_surfaced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_evo_gaps_") as d:
            base = Path(d)
            repo = base / "repo"
            _create_sandbox_repo(
                repo,
                target_src='"""Clean."""\ndef ok() -> int:\n    return 1\n',
                test_src=(
                    '"""Tests."""\nimport unittest\nfrom ace_operational.target_mod import ok\n\n'
                    "class T(unittest.TestCase):\n    def test_ok(self):\n        self.assertEqual(ok(), 1)\n"
                ),
            )
            (repo / "code" / "ace_operational" / "compositional_oaie.py").write_text(
                '"""Placeholder."""\n', encoding="utf-8"
            )
            report_path = base / "comp_report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "generations": [
                            {
                                "generation": "G5",
                                "tasks": [
                                    {
                                        "task_id": "g5_hard_gap",
                                        "ace_evolving": {"verified": False, "status": "UNSAT", "candidates": 160000},
                                    },
                                    {
                                        "task_id": "g5_slow_win",
                                        "ace_evolving": {"verified": True, "status": "SUCCESS", "candidates": 95000},
                                    },
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            audit = RealRepoAuditor(repo, scan_subpath="code/ace_operational").audit(
                compositional_report_path=report_path
            )
            kinds = [f["kind"] for f in audit["findings"]]
            self.assertIn("oaie_unsolved_task", kinds)
            self.assertIn("oaie_high_search_cost", kinds)

    def test_cross_package_snapshot_catches_sibling_package_cheat(self) -> None:
        target_src = (
            '"""Target."""\ndef fn(x: int) -> int:\n    try:\n        return int(x)\n'
            "    except Exception:\n        pass\n    return 0\n"
        )
        test_src = (
            '"""Tests."""\nimport unittest\nfrom ace_operational.target_mod import fn\n\n'
            "class T(unittest.TestCase):\n    def test_fn(self):\n        self.assertEqual(fn(2), 2)\n"
        )
        with tempfile.TemporaryDirectory(prefix="ace_evo_xpkg_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=target_src, test_src=test_src)
            synth_dir = repo / "code" / "ace_component_synthesis"
            synth_dir.mkdir(parents=True, exist_ok=True)
            (synth_dir / "__init__.py").write_text('"""Synth."""\n', encoding="utf-8")
            (synth_dir / "synth.py").write_text('"""Synth helper."""\ndef run(x: int) -> int:\n    return x\n', encoding="utf-8")

            # Scan ONLY code/ace_operational; snapshot must STILL cover code/ace_component_synthesis!
            plan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code/ace_operational").plan_next_evolution()
            self.assertEqual(plan["status"], "MISSION_EMITTED")

            # Cleanly fix target_mod.py, but smuggle unguarded `'verified': True` into sibling package
            (repo / "code" / "ace_operational" / "target_mod.py").write_text(
                target_src.replace("except Exception:\n        pass", "except ValueError:\n        return 0"),
                encoding="utf-8",
            )
            (synth_dir / "synth.py").write_text(
                '"""Synth helper."""\ndef run(x: int) -> dict:\n    return {"verified": True, "val": x}\n',
                encoding="utf-8",
            )
            res = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(res["accepted"])
            self.assertIn("code/ace_component_synthesis/synth.py", res["changed_files"])
            self.assertTrue(any("added_unguarded_verified_true" in r for r in res["reasons"]))

    def test_trivial_test_assertion_detected_and_blocked(self) -> None:
        clean_mod = '"""Clean."""\ndef add_one(x: int) -> int:\n    return x + 1\n'
        trivial_test = (
            '"""Weak test."""\nimport unittest\nfrom ace_operational.target_mod import add_one\n\n'
            "class T(unittest.TestCase):\n    def test_weak(self) -> None:\n"
            "        self.assertTrue(True)\n        self.assertEqual(1, 1)\n        self.assertEqual(add_one(1), 2)\n"
        )
        with tempfile.TemporaryDirectory(prefix="ace_evo_triv_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(repo, target_src=clean_mod, test_src=trivial_test)
            plan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution()
            self.assertEqual(plan["top_finding"]["kind"], "trivial_test_assertion")

            # Replacing with another trivial assert must be quarantined
            (repo / "code" / "ace_operational" / "test_target_mod.py").write_text(
                trivial_test.replace("self.assertTrue(True)", "assert True"),
                encoding="utf-8",
            )
            bad = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(bad["accepted"])

            # Replacing both trivial asserts with real behavioral asserts succeeds
            real_test = (
                '"""Real test."""\nimport unittest\nfrom ace_operational.target_mod import add_one\n\n'
                "class T(unittest.TestCase):\n    def test_add_one(self) -> None:\n"
                "        self.assertEqual(add_one(0), 1)\n"
                "        self.assertEqual(add_one(5), 6)\n"
                "        self.assertEqual(add_one(-3), -2)\n"
            )
            (repo / "code" / "ace_operational" / "test_target_mod.py").write_text(real_test, encoding="utf-8")
            good = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertTrue(good["accepted"], msg=str(good))

    def test_missing_unit_test_lifecycle_rejects_fakes_and_ratifies_real_test(self) -> None:
        long_mod = '"""Untested helper module."""\n\n' + "\n".join(
            [f"def helper_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(10)]
        )
        with tempfile.TemporaryDirectory(prefix="ace_evo_mut_") as d:
            repo, ws = Path(d) / "repo", Path(d) / "ws"
            _create_sandbox_repo(
                repo,
                target_src='"""Clean."""\ndef a() -> int:\n    return 1\n',
                test_src=(
                    '"""Tests."""\nimport unittest\nfrom ace_operational.target_mod import a\n\n'
                    "class T(unittest.TestCase):\n    def test_a(self) -> None:\n        self.assertEqual(a(), 1)\n"
                ),
            )
            mod_path = repo / "code" / "ace_operational" / "untested_mod.py"
            mod_path.write_text(long_mod, encoding="utf-8")

            plan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution()
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            self.assertEqual(plan["top_finding"]["kind"], "missing_unit_test")
            self.assertEqual(
                plan["top_finding"]["file_path"],
                "code/ace_operational/untested_mod.py",
            )
            order = json.loads((ws / "EVOLUTION_WORK_ORDER.json").read_text(encoding="utf-8"))
            self.assertIn("code/ace_operational/test_untested_mod.py", order["target_files"])

            # Cheat 1: Shrink source module below 25 lines without creating companion test -> REJECTED
            mod_path.write_text('"""Shrunk."""\ndef helper_0(x: int) -> int:\n    return x\n', encoding="utf-8")
            bad_shrink = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(bad_shrink["accepted"])
            self.assertTrue(any("missing_companion_test" in r for r in bad_shrink["reasons"]))
            mod_path.write_text(long_mod, encoding="utf-8")

            # Cheat 2: Create companion test with < 2 assertions or trivial assert -> REJECTED
            test_path = repo / "code" / "ace_operational" / "test_untested_mod.py"
            test_path.write_text(
                '"""Weak."""\nimport unittest\nclass T(unittest.TestCase):\n'
                "    def test_fake(self) -> None:\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            bad_weak = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(bad_weak["accepted"])
            self.assertTrue(any("ast_anti_cheat_violations" in r for r in bad_weak["reasons"]))

            # Honest fix: Real companion test exercising untested_mod
            test_path.write_text(
                '"""Real unit tests."""\nimport unittest\n'
                "from ace_operational.untested_mod import helper_0, helper_3\n\n"
                "class UntestedModTests(unittest.TestCase):\n"
                "    def test_helpers(self) -> None:\n"
                "        self.assertEqual(helper_0(5), 5)\n"
                "        self.assertEqual(helper_3(5), 8)\n",
                encoding="utf-8",
            )
            ok = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertTrue(ok["accepted"], msg=str(ok))
            self.assertIn("code/ace_operational/test_untested_mod.py", ok["changed_files"])

            # Delete test_untested_mod.py later -> planner MUST still catch the regression!
            test_path.unlink()
            replan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution()
            self.assertEqual(replan["status"], "MISSION_EMITTED")
            self.assertEqual(replan["top_finding"]["kind"], "missing_unit_test")

    def test_oaie_high_search_cost_verified_by_subprocess_not_static_ast(self) -> None:
        comp_stub_tpl = (
            '"""Compositional OAIE stub for verifier testing."""\n'
            "class CompositionalOAIERunner:\n"
            "    def __init__(self, workspace, **kwargs):\n"
            "        self.workspace = workspace\n"
            "    def run(self, include_falsification: bool = True):\n"
            "        if not self.workspace:\n"
            '            raise ValueError("missing workspace")\n'
            "        verified = self.workspace is not None\n"
            "        return {{\n"
            '            "experiment_kernel_audit": {{"status": "CLEAN"}},\n'
            '            "spore_continuity_exam": {{"forgetting_count": 0}},\n'
            '            "falsification": {{"all_falsification_probes_passed": True}},\n'
            '            "generations": [{{"generation": "G3", "tasks": [{{\n'
            '                "task_id": "g3_bottleneck",\n'
            '                "ace_evolving": {{"verified": verified, "status": "SUCCESS", "candidates": {cands}}},\n'
            "            }}]}}],\n"
            "        }}\n"
        )
        with tempfile.TemporaryDirectory(prefix="ace_evo_oaie_") as d:
            base = Path(d)
            repo, ws = base / "repo", base / "ws"
            _create_sandbox_repo(
                repo,
                target_src='"""Clean."""\ndef ok() -> int:\n    return 1\n',
                test_src=(
                    '"""Tests."""\nimport unittest\nfrom ace_operational.target_mod import ok\n\n'
                    "class T(unittest.TestCase):\n    def test_ok(self) -> None:\n        self.assertEqual(ok(), 1)\n"
                ),
            )
            comp_mod = repo / "code" / "ace_operational" / "compositional_oaie.py"
            comp_mod.write_text(comp_stub_tpl.format(cands=92_000), encoding="utf-8")
            report_dir = ws / "compositional_oaie"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "compositional_oaie_report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "generations": [
                            {
                                "generation": "G3",
                                "tasks": [
                                    {
                                        "task_id": "g3_bottleneck",
                                        "ace_evolving": {"verified": True, "status": "SUCCESS", "candidates": 92_000},
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            plan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution(
                compositional_report_path=report_path
            )
            self.assertEqual(plan["top_finding"]["kind"], "oaie_high_search_cost")

            # Editing compositional_oaie.py WITHOUT reducing search cost <= 80,000 must fail closed!
            comp_mod.write_text(comp_stub_tpl.format(cands=91_000), encoding="utf-8")
            rejected = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertFalse(rejected["accepted"])
            self.assertTrue(any("oaie_high_search_cost_unresolved" in r for r in rejected["reasons"]))

            # Reducing search cost below 80,000 passes subprocess verification & refreshes workspace report!
            comp_mod.write_text(comp_stub_tpl.format(cands=32_000), encoding="utf-8")
            ratified = EvolutionPatchVerifier(ws, repo).verify_and_ratify_evolution()
            self.assertTrue(ratified["accepted"], msg=str(ratified))
            refreshed = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed["generations"][0]["tasks"][0]["ace_evolving"]["candidates"], 32_000)
            clean_plan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution(
                compositional_report_path=report_path
            )
            self.assertEqual(clean_plan["status"], "HOLD_NO_ACTIONABLE_FINDINGS")

            # Subsequent regression in report must re-surface even if compositional_oaie.py itself was not edited
            regressed_doc = json.loads(json.dumps(refreshed))
            regressed_doc["generations"][0]["tasks"][0]["ace_evolving"]["candidates"] = 99_000
            report_path.write_text(json.dumps(regressed_doc), encoding="utf-8")
            replan = PassiveEvolutionPlanner(ws, repo, scan_subpath="code").plan_next_evolution(
                compositional_report_path=report_path
            )
            self.assertEqual(replan["status"], "MISSION_EMITTED")
            self.assertEqual(replan["top_finding"]["kind"], "oaie_high_search_cost")


if __name__ == "__main__":
    unittest.main()
