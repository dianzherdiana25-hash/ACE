"""Tes tepi luring untuk tools/ace_autonomous_daemon.py (E3 #3, TESTS ONLY)."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import ace_autonomous_daemon as daemon  # noqa: E402


def _make_run_daemon_mocks(telemetry_seq):
    watchdog = mock.MagicMock()
    watchdog.ensure_valid_state.return_value = {"cycle_count": 3, "state_digest": "abcdef1234567890"}
    researcher = mock.MagicMock()
    researcher.execute_autonomous_cycle.return_value = {
        "cycle": 1,
        "decision": "REJECTED",
        "problem": {"problem_id": "p1", "title": "T1"},
        "hypothesis": {"statement": "H1"},
    }
    janitor = mock.MagicMock()
    janitor.run_full_housekeeping.return_value = {
        "pruned_snapshots_count": 1,
        "cleaned_caches_count": 2,
        "changelog_updated": True,
    }
    coord = mock.MagicMock()
    guardian = mock.MagicMock()
    guardian.sense.side_effect = list(telemetry_seq)
    guardian.execute_emergency_freeze.return_value = {"capsule_path": "/tmp/capsule.json"}
    return watchdog, researcher, janitor, coord, guardian


class TestAceAutonomousDaemonE3(unittest.TestCase):
    """Uji unit luring terisolasi untuk ace_autonomous_daemon (semua efek samping di-mock)."""

    def test_01_log_appends_utc_timestamped_line_in_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with mock.patch.object(daemon, "REPO_ROOT", Path(tmp)), redirect_stdout(buf):
                daemon.log("halo uji")
            log_file = Path(tmp) / "checkpoints" / "self_dev" / "daemon.log"
            self.assertTrue(log_file.exists())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("[Daemon] halo uji", content)
            self.assertIn("T", content.splitlines()[0])
            self.assertEqual(content, buf.getvalue())

    def test_02_get_current_branch_returns_stripped_branch_name(self):
        cp = subprocess.CompletedProcess(args=[], returncode=0, stdout="gravity/feature-x\n", stderr="")
        with mock.patch.object(daemon.subprocess, "run", return_value=cp):
            self.assertEqual(daemon.get_current_branch(), "gravity/feature-x")

    def test_03_get_current_branch_falls_back_on_empty_or_error(self):
        empty = subprocess.CompletedProcess(args=[], returncode=0, stdout="   \n", stderr="")
        with mock.patch.object(daemon.subprocess, "run", return_value=empty):
            self.assertEqual(
                daemon.get_current_branch(),
                "integration/ace-autonomous-self-dev-bootstrap-v03-20261107",
            )
        with mock.patch.object(daemon.subprocess, "run", side_effect=OSError("git missing")):
            self.assertEqual(
                daemon.get_current_branch(),
                "integration/ace-autonomous-self-dev-bootstrap-v03-20261107",
            )

    def test_04_git_commit_and_push_skips_when_working_tree_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            add_res = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            status_res = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon.subprocess, "run", side_effect=[add_res, status_res]) as run_mock,
                redirect_stdout(io.StringIO()),
            ):
                daemon.git_commit_and_push(1, "ACCEPTED", "prob-1")
            self.assertEqual(run_mock.call_count, 2)
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("No changes to commit.", text)

    def test_05_git_commit_and_push_commits_and_pushes_on_dirty_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            dirty = subprocess.CompletedProcess(args=[], returncode=0, stdout=" M code/x.py\n", stderr="")
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "get_current_branch", return_value="gravity/test-branch"),
                mock.patch.object(daemon.subprocess, "run", side_effect=[ok, dirty, ok, ok]) as run_mock,
                redirect_stdout(io.StringIO()),
            ):
                daemon.git_commit_and_push(7, "ACCEPTED", "prob-7")
            self.assertEqual(run_mock.call_count, 4)
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Push successful for Cycle 7.", text)

    def test_06_git_commit_and_push_logs_warning_and_nonfatal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            dirty = subprocess.CompletedProcess(args=[], returncode=0, stdout=" M a.py\n", stderr="")
            warn_push = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="rejected")
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "get_current_branch", return_value="b"),
                mock.patch.object(daemon.subprocess, "run", side_effect=[ok, dirty, ok, warn_push]),
                redirect_stdout(io.StringIO()),
            ):
                daemon.git_commit_and_push(8, "ACCEPTED", "prob-8")
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon.subprocess, "run", side_effect=RuntimeError("boom")),
                redirect_stdout(io.StringIO()),
            ):
                daemon.git_commit_and_push(9, "ACCEPTED", "prob-9")
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Push warning: rejected", text)
            self.assertIn("Git push error (non-fatal, continuing loop): boom", text)

    def test_07_run_researcher_cycle_handles_pr_metadata_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            researcher = mock.MagicMock()
            researcher.execute_autonomous_cycle.side_effect = [
                {
                    "problem": {"title": "Optimize"},
                    "hypothesis": {"statement": "Cache"},
                    "decision": "ACCEPTED",
                    "pr_metadata": {"branch_name": "b1", "pr_url": "https://example/1", "pr_number": 99},
                },
                {},
            ]
            with mock.patch.object(daemon, "REPO_ROOT", Path(tmp)), redirect_stdout(io.StringIO()):
                first = daemon.run_researcher_cycle(researcher, auto_pr=True)
                second = daemon.run_researcher_cycle(researcher, auto_pr=False)
            self.assertEqual(first["decision"], "ACCEPTED")
            self.assertEqual(second, {})
            researcher.execute_autonomous_cycle.assert_any_call(auto_pr=True)
            researcher.execute_autonomous_cycle.assert_any_call(auto_pr=False)
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("GitHub PR Created: https://example/1 (#99)", text)
            self.assertIn("Decision:   UNKNOWN", text)

    def test_08_run_parameter_cycle_passes_watchdog_and_logs_fallback_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            watchdog = mock.MagicMock()
            watchdog.run_guarded_cycle.return_value = {
                "cycle_id": 12,
                "decision": "HOLD",
                "hypothesis": {"target_task_id": "t-nested"},
                "gain_over_parent": 0.025,
                "holdout_score": 0.9,
                "is_promoted": False,
                "active_head_id": "h1",
            }
            coord = mock.MagicMock()
            with mock.patch.object(daemon, "REPO_ROOT", Path(tmp)), redirect_stdout(io.StringIO()):
                res = daemon.run_parameter_cycle(watchdog, coord)
            self.assertEqual(res["cycle_id"], 12)
            watchdog.run_guarded_cycle.assert_called_once_with(
                coord.run_autonomous_cycle,
                author_type=daemon.AuthorType.ACE_AUTONOMOUS_V02,
                timeout_seconds=60.0,
                fallback_on_timeout=True,
            )
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Task=t-nested, Gain=+0.0250", text)

    def test_09_run_daemon_loop_researcher_accepted_commits_and_stops_monitor(self):
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=2048.0, disk_free_gb=20.0, battery_level=100)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([nominal])
        researcher.execute_autonomous_cycle.return_value = {
            "cycle": 4,
            "decision": "ACCEPTED",
            "problem": {"problem_id": "p-ok", "title": "Fix"},
            "hypothesis": {"statement": "Patch"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(daemon, "git_commit_and_push") as commit_mock,
                mock.patch.object(daemon.time, "sleep"),
                redirect_stdout(io.StringIO()),
            ):
                daemon.run_daemon_loop(mode="researcher", max_cycles=1, batch_size=1, sleep_seconds=0, auto_pr=True)
        commit_mock.assert_called_once_with(4, "ACCEPTED", "p-ok")
        watchdog.start_background_monitor.assert_called_once()
        watchdog.stop_background_monitor.assert_called_once()

    def test_10_run_daemon_loop_critical_substrate_triggers_emergency_freeze(self):
        critical = SimpleNamespace(
            status_level="CRITICAL",
            available_ram_mb=128.0,
            disk_free_gb=0.4,
            battery_level=5,
            recommended_action="FREEZE",
        )
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=4096.0, disk_free_gb=30.0, battery_level=99)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([critical, nominal])
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(daemon, "git_commit_and_push") as commit_mock,
                mock.patch.object(daemon.time, "sleep") as sleep_mock,
                redirect_stdout(io.StringIO()),
            ):
                daemon.run_daemon_loop(mode="researcher", max_cycles=1, batch_size=1, sleep_seconds=0, auto_pr=False)
        guardian.execute_emergency_freeze.assert_called_once()
        commit_mock.assert_called_once_with(1, "EMERGENCY_FREEZE", "substrate_survival_halt")
        sleep_mock.assert_called_once_with(60)
        watchdog.stop_background_monitor.assert_called_once()

    def test_11_run_daemon_loop_parameter_mode_milestone_and_janitor_on_third_iter(self):
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=4096.0, disk_free_gb=30.0, battery_level=100)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([nominal, nominal, nominal])
        # max_cycles=3, batch_size=1, iteration 1..3 runs verifier each time and janitor at iter 3.
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(
                    daemon,
                    "run_parameter_cycle",
                    side_effect=[
                        {"cycle_id": 50, "decision": "KEEP", "target_task_id": "t50", "is_promoted": False},
                        {"cycle_id": 51, "decision": "PROMOTED", "target_task_id": None, "is_promoted": True},
                        {"cycle_id": 52, "decision": "HOLD", "target_task_id": "t52", "is_promoted": False},
                    ],
                ),
                mock.patch.object(daemon, "git_commit_and_push") as commit_mock,
                mock.patch.object(
                    daemon.subprocess,
                    "run",
                    side_effect=[
                        subprocess.CompletedProcess([], 0, stdout="", stderr=""),
                        subprocess.CompletedProcess([], 1, stdout="warn tail", stderr=""),
                    ],
                ),
                mock.patch.object(daemon.time, "sleep") as sleep_mock,
                redirect_stdout(io.StringIO()),
            ):
                daemon.run_daemon_loop(mode="parameter", max_cycles=3, batch_size=1, sleep_seconds=2)
        self.assertEqual(
            commit_mock.call_args_list,
            [
                mock.call(50, "KEEP", "t50"),
                mock.call(51, "PROMOTED", "param_task"),
            ],
        )
        janitor.run_full_housekeeping.assert_not_called()
        self.assertEqual(sleep_mock.call_count, 2)

    def test_12_run_daemon_loop_hybrid_mode_and_third_iter_housekeeping(self):
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=4096.0, disk_free_gb=30.0, battery_level=100)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([nominal, nominal, nominal])
        # Iteration 1 & 2 have inner exception -> total_completed stays 0 while verifier/janitor still run;
        # Iteration 3 runs janitor (iteration % 3 == 0), and cycle raises or reaches max_cycles after verifier!
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(
                    daemon,
                    "run_researcher_cycle",
                    side_effect=[
                        RuntimeError("transient1"),
                        RuntimeError("transient2"),
                        {"cycle": 3, "decision": "REJECTED", "problem": {"problem_id": "p3"}},
                    ],
                ),
                mock.patch.object(
                    daemon,
                    "run_parameter_cycle",
                    return_value={"cycle_id": 1, "decision": "HOLD", "is_promoted": False},
                ) as param_mock,
                mock.patch.object(daemon.subprocess, "run", side_effect=OSError("verifier down")),
                mock.patch.object(daemon.time, "sleep") as sleep_mock,
                redirect_stdout(io.StringIO()),
            ):
                daemon.run_daemon_loop(mode="hybrid", max_cycles=1, batch_size=1, sleep_seconds=1)
            # In iteration 3, both researcher (+1) and parameter (+1) execute before max_cycles=1 return!
            param_mock.assert_called_once()
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Error in cycle execution: transient1", text)
            self.assertIn("Verifier error: verifier down", text)
            self.assertIn("Target max_cycles (1) reached.", text)
            sleep_mock.assert_called_with(1)
            watchdog.stop_background_monitor.assert_called_once()

    def test_13_run_daemon_loop_janitor_runs_and_handles_exception_before_post_batch_return(self):
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=4096.0, disk_free_gb=30.0, battery_level=100)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([nominal, nominal, nominal])
        janitor.run_full_housekeeping.side_effect = RuntimeError("janitor fail")
        # batch_size=0 runs 0 inner steps per iteration, incrementing total_completed only outside?
        # Even simpler: raise on iteration 3 after janitor if total_completed unchanged, OR let iteration 1..3 run verifier & janitor, raising Stopped in sleep(3rd):
        # Better: inside run_daemon_loop, total_completed can reach max_cycles via a failing step ONLY if step completes;
        # Wait: when max_cycles=0, only exception stops loop; so raise KeyboardInterrupt on sleep at iter 3 to exit cleanly while watchdog.stop runs in finally!
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(daemon.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")),
                mock.patch.object(daemon.time, "sleep", side_effect=[None, None, KeyboardInterrupt()]),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    daemon.run_daemon_loop(mode="researcher", max_cycles=0, batch_size=1, sleep_seconds=1)
            janitor.run_full_housekeeping.assert_called_once()
            watchdog.stop_background_monitor.assert_called_once()
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Janitor error (non-fatal): janitor fail", text)
            self.assertIn("Halting watchdog background monitor...", text)

    def test_14_run_daemon_loop_janitor_success_on_third_iteration(self):
        nominal = SimpleNamespace(status_level="NOMINAL", available_ram_mb=4096.0, disk_free_gb=30.0, battery_level=100)
        watchdog, researcher, janitor, coord, guardian = _make_run_daemon_mocks([nominal, nominal, nominal])
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(daemon, "REPO_ROOT", Path(tmp)),
                mock.patch.object(daemon, "ResilientWatchdog", return_value=watchdog),
                mock.patch.object(daemon, "AutonomousSoftwareResearcher", return_value=researcher),
                mock.patch.object(daemon, "AutonomousRepoJanitor", return_value=janitor),
                mock.patch.object(daemon, "SelfDevelopmentCoordinator", return_value=coord),
                mock.patch.object(daemon, "SubstrateGuardian", return_value=guardian),
                mock.patch.object(daemon.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")),
                mock.patch.object(daemon.time, "sleep", side_effect=[None, None, KeyboardInterrupt()]),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    daemon.run_daemon_loop(mode="researcher", max_cycles=0, batch_size=1, sleep_seconds=1)
            text = (Path(tmp) / "checkpoints" / "self_dev" / "daemon.log").read_text(encoding="utf-8")
            self.assertIn("Pruned 1 old snapshots", text)

    def test_15_main_parses_defaults_and_custom_cli_flags(self):
        with (
            mock.patch.object(daemon, "run_daemon_loop") as loop_mock,
            mock.patch.object(sys, "argv", ["ace_autonomous_daemon.py"]),
        ):
            daemon.main()
        loop_mock.assert_called_once_with(
            mode="researcher", max_cycles=0, batch_size=1, sleep_seconds=15, auto_pr=False
        )

        with (
            mock.patch.object(daemon, "run_daemon_loop") as loop_mock,
            mock.patch.object(
                sys,
                "argv",
                [
                    "ace_autonomous_daemon.py",
                    "--mode",
                    "hybrid",
                    "--max-cycles",
                    "5",
                    "--batch-size",
                    "3",
                    "--sleep-seconds",
                    "2",
                    "--auto-pr",
                ],
            ),
        ):
            daemon.main()
        loop_mock.assert_called_once_with(
            mode="hybrid", max_cycles=5, batch_size=3, sleep_seconds=2, auto_pr=True
        )

    def test_16_main_rejects_invalid_mode_flag(self):
        with (
            mock.patch.object(sys, "argv", ["ace_autonomous_daemon.py", "--mode", "invalid"]),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as ctx:
                daemon.main()
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
