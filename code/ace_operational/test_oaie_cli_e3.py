"""Tes tepi luring untuk code/ace_operational/oaie_cli.py (E3 #7, TESTS ONLY)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from ace_operational import oaie_cli  # noqa: E402


class TestOaieCliE3(unittest.TestCase):
    """Uji unit tepi untuk build_parser, run_cli_action, dan main di oaie_cli."""

    def test_01_build_parser_supports_all_subcommands_and_repeatable_flags(self):
        parser = oaie_cli.build_parser()
        args_mp = parser.parse_args(
            [
                "--workspace",
                "/tmp/ws",
                "mission-plan",
                "--mission-id",
                "m1",
                "--title",
                "T",
                "--goal",
                "G",
                "--target-file",
                "code/a.py",
                "--target-file",
                "code/b.py",
                "--check",
                "c1",
                "--criterion",
                "k1",
            ]
        )
        self.assertEqual(args_mp.command, "mission-plan")
        self.assertEqual(args_mp.target_files, ["code/a.py", "code/b.py"])
        self.assertEqual(args_mp.checks, ["c1"])
        self.assertEqual(args_mp.criteria, ["k1"])

        args_co = parser.parse_args(["compositional-oaie", "--max-candidates", "42", "--timeout-sec", "0.5", "--no-falsification"])
        self.assertEqual(args_co.max_candidates, 42)
        self.assertAlmostEqual(args_co.timeout_sec, 0.5)
        self.assertTrue(args_co.no_falsification)

    def test_02_build_parser_rejects_missing_subcommand_or_required_args(self):
        parser = oaie_cli.build_parser()
        for bad_argv in (
            [],
            ["verify-spore"],
            ["work-order", "--order-id", "o1"],
            ["mission-plan", "--mission-id", "m1", "--title", "t", "--goal", "g"],
        ):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
                parser.parse_args(bad_argv)
            self.assertEqual(ctx.exception.code, 2)

    def test_03_resolve_cli_workspace_precedence_and_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = Path(tmp) / "custom_ws"
            repo_dir = Path(tmp) / "repo"
            self.assertEqual(
                oaie_cli._resolve_cli_workspace(SimpleNamespace(workspace=str(ws_dir), repo_root=str(repo_dir))),
                ws_dir.resolve(),
            )
            self.assertEqual(
                oaie_cli._resolve_cli_workspace(SimpleNamespace(workspace=None, repo_root=str(repo_dir))),
                (repo_dir / ".ace_evolution").resolve(),
            )
            self.assertEqual(
                oaie_cli._resolve_cli_workspace(SimpleNamespace(workspace=None, repo_root=None)),
                Path(".ace_evolution").resolve(),
            )

    def test_04_resolve_passive_workspace_detects_direct_and_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "plain"
            base.mkdir()
            self.assertEqual(oaie_cli._resolve_passive_workspace(base), base / "passive_evolution")

            for marker in ("EVOLUTION_WORK_ORDER.json", "evolution_state.json"):
                d = Path(tmp) / f"d_{marker}"
                d.mkdir()
                (d / marker).write_text("{}", encoding="utf-8")
                self.assertEqual(oaie_cli._resolve_passive_workspace(d), d)

            um = Path(tmp) / "um_parent"
            (um / "user_missions").mkdir(parents=True)
            self.assertEqual(oaie_cli._resolve_passive_workspace(um), um)

            dot_dir = Path(tmp) / ".ace_evolution"
            self.assertEqual(oaie_cli._resolve_passive_workspace(dot_dir), dot_dir)

    def test_05_run_cli_action_status_switches_to_runtime_subdir_when_passive_markers_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            sup_inst = mock.MagicMock(state={"ok": True})
            sup_inst.dag.verify_chain.return_value = True
            sup_inst.dag.nodes.return_value = ["n1", "n2"]

            args = oaie_cli.build_parser().parse_args(["--workspace", str(ws), "status"])
            with mock.patch.object(oaie_cli, "SovereignRuntimeSupervisor", return_value=sup_inst) as sup_cls:
                out = oaie_cli.run_cli_action(args)
            sup_cls.assert_called_once_with(ws.resolve())
            self.assertEqual(out["schema"], "ace.oaie_cli.status.v1")
            self.assertEqual(out["dag_nodes"], 2)

            (ws / "evolution_state.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(oaie_cli, "SovereignRuntimeSupervisor", return_value=sup_inst) as sup_cls2:
                oaie_cli.run_cli_action(args)
            sup_cls2.assert_called_once_with(ws.resolve() / "runtime")

    def test_06_run_cli_action_run_cycle_wires_task_factory_and_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            sup_inst = mock.MagicMock()
            sup_inst.run_until_health.return_value = {"final_health": 0.95, "unhandled_crashes": 0}
            args = oaie_cli.build_parser().parse_args(["--workspace", str(ws), "run-cycle", "--seed", "77", "--cycles", "2"])
            with (
                mock.patch.object(oaie_cli, "SovereignRuntimeSupervisor", return_value=sup_inst),
                mock.patch.object(
                    oaie_cli,
                    "run_oaie_unlimited_cycle",
                    return_value={"verified_unlimited_ok": True, "unlimited_replay_digest": "deadbeef"},
                ) as unl_mock,
                mock.patch.object(oaie_cli, "run_neuro_formal_genesis_cycle", return_value={"skills_synthesized": 3}),
            ):
                out = oaie_cli.run_cli_action(args)
            unl_mock.assert_called_once_with(ws.resolve() / "unlimited", seed=77)
            factory = sup_inst.run_until_health.call_args.kwargs["task_factory"]
            self.assertEqual(factory(5)["task_id"], "cli_cycle_77_5")
            self.assertEqual(out["runtime_health"], 0.95)
            self.assertEqual(out["synthesized_skills"], 3)

    def test_07_run_cli_action_compositional_oaie_respects_no_falsification(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            runner_inst = mock.MagicMock()
            runner_inst.run.return_value = {"passed": True}
            args = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "compositional-oaie", "--max-candidates", "10", "--timeout-sec", "0.2", "--no-falsification"]
            )
            with mock.patch.object(oaie_cli, "CompositionalOAIERunner", return_value=runner_inst) as runner_cls:
                out = oaie_cli.run_cli_action(args)
            runner_cls.assert_called_once_with(ws.resolve() / "compositional_oaie", max_candidates=10, timeout_sec=0.2)
            runner_inst.run.assert_called_once_with(include_falsification=False)
            self.assertEqual(out, {"passed": True})

    def test_08_run_cli_action_evolve_plan_autodetects_and_overrides_compositional_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            comp_file = ws / "compositional_oaie" / "compositional_oaie_report.json"
            comp_file.parent.mkdir(parents=True)
            comp_file.write_text("{}", encoding="utf-8")

            planner_inst = mock.MagicMock()
            planner_inst.plan_next_evolution.return_value = {"work_order": "ok"}

            args_auto = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "evolve-plan", "--repo-root", tmp, "--test-module", "m1"]
            )
            with mock.patch.object(oaie_cli, "PassiveEvolutionPlanner", return_value=planner_inst):
                oaie_cli.run_cli_action(args_auto)
            planner_inst.plan_next_evolution.assert_called_with(
                test_modules=["m1"],
                compositional_report_path=str(comp_file.resolve()),
            )

            args_explicit = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "evolve-plan", "--repo-root", tmp, "--compositional-report", "/custom.json"]
            )
            with mock.patch.object(oaie_cli, "PassiveEvolutionPlanner", return_value=planner_inst):
                oaie_cli.run_cli_action(args_explicit)
            planner_inst.plan_next_evolution.assert_called_with(
                test_modules=None,
                compositional_report_path="/custom.json",
            )

    def test_09_run_cli_action_evolve_verify_forwards_extra_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            verifier_inst = mock.MagicMock()
            verifier_inst.verify_and_ratify_evolution.return_value = {"ratified": False}
            args = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "evolve-verify", "--repo-root", tmp, "--check", "verify_sources.py"]
            )
            with mock.patch.object(oaie_cli, "EvolutionPatchVerifier", return_value=verifier_inst):
                out = oaie_cli.run_cli_action(args)
            verifier_inst.verify_and_ratify_evolution.assert_called_once_with(extra_checks=["verify_sources.py"])
            self.assertEqual(out, {"ratified": False})

    def test_10_run_cli_action_mission_plan_and_mission_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            coord_inst = mock.MagicMock()
            coord_inst.plan_user_mission.return_value = {"planned": "m-9"}
            coord_inst.verify_user_mission.return_value = {"verified": True}

            args_p = oaie_cli.build_parser().parse_args(
                [
                    "--workspace",
                    str(ws),
                    "mission-plan",
                    "--repo-root",
                    tmp,
                    "--mission-id",
                    "m-9",
                    "--title",
                    "Title",
                    "--goal",
                    "Goal",
                    "--target-file",
                    "code/x.py",
                ]
            )
            with mock.patch.object(oaie_cli, "UserMissionCoordinator", return_value=coord_inst):
                res_p = oaie_cli.run_cli_action(args_p)
            self.assertEqual(res_p, {"planned": "m-9"})
            coord_inst.plan_user_mission.assert_called_once_with(
                mission_id="m-9",
                title="Title",
                goal="Goal",
                target_files=["code/x.py"],
                acceptance_checks=[],
                criteria=[],
            )

            args_v = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "mission-verify", "--repo-root", tmp, "--mission-id", "m-9", "--check", "c1"]
            )
            with mock.patch.object(oaie_cli, "UserMissionCoordinator", return_value=coord_inst):
                res_v = oaie_cli.run_cli_action(args_v)
            self.assertEqual(res_v, {"verified": True})
            coord_inst.verify_user_mission.assert_called_once_with(mission_id="m-9", extra_checks=["c1"])

    def test_11_run_cli_action_evolve_once_and_multi(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            evolver_inst = mock.MagicMock()
            evolver_inst.run_evolution_generation.return_value = {"gen": "g2"}
            evolver_inst.run_multi_generation_loop.return_value = {"gens": 3}

            with mock.patch("ace_operational.autonomous_evolver.AutonomousEvolver", return_value=evolver_inst) as ev_cls:
                args_once = oaie_cli.build_parser().parse_args(
                    ["--workspace", str(ws), "evolve-once", "--generation-id", "g2", "--repo-root", tmp, "--skip-compositional"]
                )
                self.assertEqual(oaie_cli.run_cli_action(args_once), {"gen": "g2"})
                ev_cls.assert_called_with(ws.resolve() / "evolver", repo_root=tmp)
                evolver_inst.run_evolution_generation.assert_called_with("g2", include_compositional_oaie=False)

                args_multi = oaie_cli.build_parser().parse_args(
                    ["--workspace", str(ws), "evolve-multi", "--generations", "3", "--repo-root", tmp]
                )
                self.assertEqual(oaie_cli.run_cli_action(args_multi), {"gens": 3})
                evolver_inst.run_multi_generation_loop.assert_called_with(generations=3, include_compositional_oaie=True)

    def test_12_run_cli_action_verify_spore_uses_expected_ancestor_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            args = oaie_cli.build_parser().parse_args(["--workspace", str(ws), "verify-spore", "--spore-path", "/tmp/s.json"])
            with mock.patch(
                "ace_operational.sovereign_runtime.SubstrateSpore.import_and_verify_spore",
                return_value={"valid": True},
            ) as imp_mock:
                out = oaie_cli.run_cli_action(args)
            self.assertEqual(out, {"valid": True})
            imp_mock.assert_called_once_with(
                spore_path="/tmp/s.json",
                target_workspace=ws.resolve() / "spore_verify_probe",
                expected_ancestor_skills=["core_stage2_guard"],
                antibody_probes=[],
            )

    def test_13_run_cli_action_work_order_applies_default_checks_and_forbidden_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            sup_inst = mock.MagicMock()
            sup_inst.work_bridge.export_work_order.return_value = {"order_id": "wo-1"}
            args = oaie_cli.build_parser().parse_args(
                ["--workspace", str(ws), "work-order", "--order-id", "wo-1", "--goal", "Fix bug"]
            )
            with mock.patch.object(oaie_cli, "SovereignRuntimeSupervisor", return_value=sup_inst):
                out = oaie_cli.run_cli_action(args)
            self.assertEqual(out, {"order_id": "wo-1"})
            kw = sup_inst.work_bridge.export_work_order.call_args.kwargs
            self.assertEqual(kw["target_files"], [])
            self.assertEqual(kw["acceptance_checks"], ["unittest", "verify_sources.py"])
            self.assertIn("evidence/", kw["forbidden_paths"])

    def test_14_run_cli_action_rejects_unknown_command_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_args = SimpleNamespace(workspace=tmp, command="bogus-cmd")
            with self.assertRaisesRegex(ValueError, "Unknown command: bogus-cmd"):
                oaie_cli.run_cli_action(fake_args)

    def test_15_main_redirects_noisy_stdout_and_emits_sorted_json(self):
        def noisy_action(_args):
            print("NOISY DEBUG LINE THAT MUST NOT REACH CLI STDOUT")
            return {"z": 1, "a": 2}

        buf = io.StringIO()
        with (
            mock.patch.object(oaie_cli, "run_cli_action", side_effect=noisy_action),
            redirect_stdout(buf),
        ):
            rc = oaie_cli.main(["--workspace", "/tmp/w", "status"])
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertNotIn("NOISY DEBUG LINE", text)
        self.assertEqual(json.loads(text), {"a": 2, "z": 1})

    def test_16_main_propagates_action_error_without_silent_zero_exit(self):
        with mock.patch.object(oaie_cli, "run_cli_action", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                oaie_cli.main(["--workspace", "/tmp/w", "status"])


if __name__ == "__main__":
    unittest.main()
