"""Tests for the unified OAIE-∞ CLI (`ace_operational.oaie_cli`)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class OaieCliTests(unittest.TestCase):
    def _run_cli(self, workspace: Path, *args: str, timeout: int = 120) -> dict:
        proc = subprocess.run(
            [sys.executable, "-m", "ace_operational.oaie_cli", "--workspace", str(workspace), *args],
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ, "PYTHONPATH": "code"},
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        return json.loads(proc.stdout)

    def test_cli_status_run_cycle_compositional_evolve_loop_and_work_order(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            base = Path(d1)
            ws = base / "ws"
            st = self._run_cli(ws, "status")
            self.assertTrue(st["dag_chain_valid"])

            rc = self._run_cli(ws, "run-cycle", "--cycles", "3")
            self.assertTrue(rc["verified_unlimited_ok"])
            self.assertEqual(rc["unhandled_crashes"], 0)
            self.assertGreaterEqual(rc["synthesized_skills"], 4)

            comp = self._run_cli(ws, "compositional-oaie")
            self.assertEqual(comp["overall_verdict"], "COMPOSITIONAL_OAIE_VERIFIED")
            self.assertEqual(comp["arm_totals"]["ace_evolving"]["solved"], 14)

            # Exercise evolve-plan & evolve-verify CLI end-to-end on an isolated sandbox repo
            sandbox_repo = base / "sandbox_repo"
            (sandbox_repo / "code" / "ace_operational").mkdir(parents=True, exist_ok=True)
            (sandbox_repo / "code" / "ace_operational" / "__init__.py").write_text('"""Pkg."""\n', encoding="utf-8")
            mod_path = sandbox_repo / "code" / "ace_operational" / "sample.py"
            mod_path.write_text(
                "def f(x: int) -> int:\n" + ("    x = x + 1\n" * 12) + "    return x\n",
                encoding="utf-8",
            )
            plan = self._run_cli(ws, "evolve-plan", "--repo-root", str(sandbox_repo))
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            wo_md = (ws / "passive_evolution" / "EVOLUTION_WORK_ORDER.md").read_text(encoding="utf-8")
            self.assertIn(f'--workspace "{ws / "passive_evolution"}" evolve-verify', wo_md)

            mod_path.write_text('"""Sample module."""\n' + mod_path.read_text(encoding="utf-8"), encoding="utf-8")
            ver = self._run_cli(ws / "passive_evolution", "evolve-verify", "--repo-root", str(sandbox_repo))
            self.assertTrue(ver["accepted"])
            self.assertEqual(ver["status"], "VERIFIED_AND_RATIFIED")

            ev = self._run_cli(ws, "evolve-once", "--generation-id", "gen-cli", "--skip-compositional")
            self.assertEqual(ev["epoch_a_skills_synthesized"], 5)
            self.assertEqual(ev["forgetting_count"], 0)
            self.assertTrue(ev["dag_chain_valid"])

            vs = self._run_cli(
                ws,
                "verify-spore",
                "--spore-path",
                str(ws / "evolver" / "gen-cli" / "generation_spore.json"),
            )
            self.assertTrue(vs["exam_passed"])
            self.assertEqual(vs["forgetting_count"], 0)

            wo = self._run_cli(ws, "work-order", "--order-id", "wo-test", "--goal", "Verify CLI")
            self.assertEqual(len(wo["order_sha256"]), 64)
            self.assertTrue((ws / "ACE_WORK_ORDER.json").exists())

    def test_default_persistent_repo_ace_evolution_workspace_and_cross_package_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_cli_persist_") as d:
            sandbox = Path(d) / "repo"
            pkg_a = sandbox / "code" / "ace_operational"
            pkg_b = sandbox / "code" / "ace_component_synthesis"
            pkg_a.mkdir(parents=True, exist_ok=True)
            pkg_b.mkdir(parents=True, exist_ok=True)
            (pkg_a / "__init__.py").write_text('"""A."""\n', encoding="utf-8")
            (pkg_b / "__init__.py").write_text('"""B."""\n', encoding="utf-8")
            target_b = pkg_b / "synth_mod.py"
            target_b.write_text(
                '"""Synth."""\ndef f() -> dict:\n    return {"verified": True}\n',
                encoding="utf-8",
            )

            # Omit --workspace and --scan-subpath -> defaults to <repo-root>/.ace_evolution and scans all code/
            plan_proc = subprocess.run(
                [sys.executable, "-m", "ace_operational.oaie_cli", "evolve-plan", "--repo-root", str(sandbox)],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": "code"},
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            plan = json.loads(plan_proc.stdout)
            self.assertEqual(plan["status"], "MISSION_EMITTED")
            self.assertEqual(plan["top_finding"]["file_path"], "code/ace_component_synthesis/synth_mod.py")
            evo_dir = sandbox / ".ace_evolution"
            self.assertTrue((evo_dir / "EVOLUTION_WORK_ORDER.json").is_file())
            md_text = (evo_dir / "EVOLUTION_WORK_ORDER.md").read_text(encoding="utf-8")
            self.assertIn('--workspace ".ace_evolution" evolve-verify --repo-root "."', md_text)

            target_b.write_text(
                '"""Synth."""\ndef f(ok: bool) -> dict:\n    if not ok:\n        raise ValueError("fail")\n    return {"verified": True}\n',
                encoding="utf-8",
            )
            ver_proc = subprocess.run(
                [sys.executable, "-m", "ace_operational.oaie_cli", "evolve-verify", "--repo-root", str(sandbox)],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": "code"},
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            ver = json.loads(ver_proc.stdout)
            self.assertTrue(ver["accepted"], msg=str(ver))

    def test_user_mission_cli_plan_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_cli_mission_") as d:
            sandbox = Path(d) / "repo"
            pkg = sandbox / "code" / "ace_operational"
            pkg.mkdir(parents=True, exist_ok=True)
            (pkg / "__init__.py").write_text('"""Pkg."""\n', encoding="utf-8")

            plan_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ace_operational.oaie_cli",
                    "mission-plan",
                    "--repo-root",
                    str(sandbox),
                    "--mission-id",
                    "mission-0001-cli",
                    "--title",
                    "CLI User Mission",
                    "--goal",
                    "Tambah modul bicara uji CLI",
                    "--target-file",
                    "code/ace_operational/hello_mod.py",
                    "--target-file",
                    "code/ace_operational/test_hello_mod.py",
                ],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": "code"},
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            plan = json.loads(plan_proc.stdout)
            self.assertEqual(plan["status"], "USER_MISSION_EMITTED")
            self.assertTrue((sandbox / ".ace_evolution" / "user_missions" / "CURRENT_USER_MISSION.json").is_file())

            (pkg / "hello_mod.py").write_text(
                '"""Hello module."""\n\ndef say_hi(who: str) -> str:\n    return f"hai {who}"\n',
                encoding="utf-8",
            )
            (pkg / "test_hello_mod.py").write_text(
                '"""Tests."""\nimport unittest\nfrom ace_operational.hello_mod import say_hi\n\n'
                "class T(unittest.TestCase):\n"
                "    def test_say_hi(self) -> None:\n"
                '        self.assertEqual(say_hi("ACE"), "hai ACE")\n'
                '        self.assertEqual(say_hi("dunia"), "hai dunia")\n',
                encoding="utf-8",
            )
            ver_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ace_operational.oaie_cli",
                    "mission-verify",
                    "--repo-root",
                    str(sandbox),
                ],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": "code"},
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            ver = json.loads(ver_proc.stdout)
            self.assertTrue(ver["accepted"], msg=str(ver))
            self.assertEqual(ver["order_id"], "mission-0001-cli")
            self.assertEqual(ver["forgetting_count"], 0)


if __name__ == "__main__":
    unittest.main()

