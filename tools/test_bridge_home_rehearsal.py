"""Harness rehearsal end-to-end bridge_home atas rumah fixture lengkap (AG25).

Kenapa: memastikan preflight dan rencana cutover bridge_home selaras 100%
dengan semantik status engine house_check (kontrak K8) pada skenario rumah
lengkap (repo git mini + workspace + manifest nama-saja + status engine),
serta memverifikasi perintah launch tanpa pernah mengeksekusinya.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools import bridge_home, house_check


BRIDGE_HOME_CLI = Path(__file__).with_name("bridge_home.py")


class BridgeHomeRehearsalTests(unittest.TestCase):
    def _build_fixture_home(self, root: Path, now: datetime) -> dict:
        repo = root / "ace-home-repo"
        (repo / "tools").mkdir(parents=True)
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
        # Jebakan: skrip brain_bridge.py di fixture tidak boleh pernah dieksekusi selama rehearsal.
        sentinel = root / "MUST_NOT_EXECUTE.flag"
        (repo / "tools" / "brain_bridge.py").write_text(
            f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('ran')\nraise SystemExit(99)\n",
            encoding="utf-8",
        )

        workspace = root / "workspace"
        helpers = workspace / "helpers"
        helpers.mkdir(parents=True)
        state = workspace / "bridge_state.json"
        call_log = workspace / "bridge_calls.jsonl"
        stdout_log = workspace / "bridge.stdout.log"
        pid_file = workspace / "bridge.pid"
        pid_file.write_text("999991\n", encoding="utf-8")

        engine_status = workspace / "engine_status.json"
        pump_pid = workspace / "pump.pid"
        pump_pid.write_text("4242\n", encoding="utf-8")

        manifest = root / "bundle-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": bridge_home.BUNDLE_MANIFEST_SCHEMA,
                    "entries": [{"name": name} for name in bridge_home.REQUIRED_ENTRY_NAMES],
                }
            ),
            encoding="utf-8",
        )

        config = {
            "repo": str(repo),
            "helpers": str(helpers),
            "budget_state": str(state),
            "call_log": str(call_log),
            "stdout_log": str(stdout_log),
            "pid_file": str(pid_file),
            "port": 18941,
            "current_bridge_url": "http://127.0.0.1:18931",
            "engine_status_file": str(engine_status),
        }
        config_path = root / "bridge_home_config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        return {
            "repo": repo,
            "sentinel": sentinel,
            "workspace": workspace,
            "engine_status": engine_status,
            "pump_pid": pump_pid,
            "manifest": manifest,
            "config": config,
            "config_path": config_path,
            "now": now,
        }

    def test_end_to_end_rehearsal_status_matrix_matches_house_check_and_launch_shape(self) -> None:
        now = datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            fix = self._build_fixture_home(Path(tmp), now)
            base_status = {
                "pid": 1234,
                "cycle_count": 19,
                "running": True,
                "updated_at": now.isoformat(),
            }
            cases = {
                "sehat": json.dumps(base_status),
                "stale": json.dumps({**base_status, "updated_at": "2026-11-20T09:54:59+00:00"}),
                "stopped": json.dumps({**base_status, "running": False}),
                "json_rusak": '{"pid": 1234, "running": ',
            }

            for label, payload in cases.items():
                with self.subTest(case=label):
                    fix["engine_status"].write_text(payload, encoding="utf-8")
                    house = house_check.inspect_house(
                        "http://127.0.0.1:18931",
                        fix["pump_pid"],
                        fix["engine_status"],
                        health_probe=lambda *_: True,
                        pid_probe=lambda _: True,
                        now=now,
                    )
                    plan = bridge_home.plan_home(
                        fix["config"],
                        bundle_manifest=fix["manifest"],
                        pid_probe=lambda _: False,
                        now=now,
                    )
                    house_safe = house["exit_code"] == 0
                    self.assertEqual(plan["preflight"]["safe_to_continue"], house_safe)
                    self.assertEqual(
                        plan["preflight"]["engine_status"]["safe_to_continue"],
                        house_safe,
                    )
                    self.assertEqual(
                        plan["preflight"]["engine_status"]["state"],
                        house["components"]["engine"]["state"],
                    )

                    steps = {s["id"]: s for s in plan["steps"]}
                    self.assertEqual(list(steps), ["preflight", "launch", "health", "cutover"])
                    launch_cmd = steps["launch"]["action"]
                    cmd_head, _, cmd_tail = launch_cmd.partition(" > ")
                    argv = shlex.split(cmd_head)
                    self.assertEqual(
                        argv,
                        [
                            "nohup",
                            "python3",
                            str(fix["repo"] / "tools" / "brain_bridge.py"),
                            "--port",
                            "18941",
                            "--state",
                            fix["config"]["budget_state"],
                            "--log",
                            fix["config"]["call_log"],
                            "--helpers",
                            fix["config"]["helpers"],
                        ],
                    )
                    self.assertIn(shlex.quote(fix["config"]["stdout_log"]), cmd_tail)
                    self.assertIn(shlex.quote(fix["config"]["pid_file"]), cmd_tail)

            # Uji CLI subproses end-to-end dengan status sehat (fresh relatif clock sistem)
            live_now = datetime.now(timezone.utc)
            fix["engine_status"].write_text(
                json.dumps({**base_status, "updated_at": live_now.isoformat()}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(BRIDGE_HOME_CLI),
                    str(fix["config_path"]),
                    "--bundle-manifest",
                    str(fix["manifest"]),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            cli_plan = json.loads(proc.stdout)
            self.assertEqual(cli_plan["preflight"]["credential_markers"]["state"], "present")
            self.assertEqual(cli_plan["preflight"]["engine_status"]["state"], "healthy")
            self.assertFalse(fix["sentinel"].exists(), "Perintah launch tidak boleh dieksekusi.")


if __name__ == "__main__":
    unittest.main()
