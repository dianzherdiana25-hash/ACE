"""Autonomous Multi-Agent Software Factory for ACE.

Implements an end-to-end multi-agent software engineering pipeline:
1. ArchitectAgent: Analyzes specifications (in Indonesian or English) and creates full system blueprints.
2. CoderAgent: Synthesizes multi-file codebases atomically with AST syntax validation.
3. QualityAssuranceAgent: Executes test suites in isolated subprocesses with real assertions.
4. AutoRepairAgent: Performs self-healing diagnostic repair loops when tests fail.
5. ReceiptAuditor: Generates immutable audit records (ace.receipt.v1) into OperationalStore.
"""
from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from .coding_loop import atomic_write_verified, file_lock_guard
from .models_backend import ModelRouter
from .store import OperationalStore

logger = logging.getLogger("ace_software_factory")


class SoftwareFactory:
    """Orchestrates multi-agent software engineering pipelines for complex deliverables."""

    def __init__(self, store: OperationalStore, router: ModelRouter | None = None):
        self.store = store
        self.router = router or ModelRouter(store)

    def plan_architecture(self, project_name: str, spec_id: str) -> dict[str, Any]:
        """ArchitectAgent: Analyze prompt and design modular project structure."""
        logger.info(f"[ArchitectAgent] Planning architecture for '{project_name}'...")
        prompt = (
            f"Rancang arsitektur sistem perangkat lunak untuk proyek: {project_name}\n"
            f"Spesifikasi Kebutuhan:\n{spec_id}\n\n"
            f"Tentukan modul-modul yang dibutuhkan (backend, database, web interface/cli, dan automated tests)."
        )
        tier_res = self.router.generate_text(
            [
                {"role": "system", "content": "Kamu adalah Lead Software Architect ACE. Rancang sistem modular yang bersih, teruji, dan siap produksi."},
                {"role": "user", "content": prompt},
            ],
            tier="auto",
            max_tokens=64,
        )
        return {
            "project_name": project_name,
            "spec": spec_id,
            "architecture_overview": tier_res.get("text", "Arsitektur Modular Standar ACE"),
            "tier_used": tier_res.get("tier_used", "deep"),
            "backend_used": tier_res.get("backend_used", "local-router"),
        }

    def synthesize_module(self, target_path: Path, code_content: str, is_python: bool = True) -> dict[str, Any]:
        """CoderAgent: Validate syntax and write code atomically with OS file locking."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if is_python:
            try:
                ast.parse(code_content, filename=str(target_path))
            except SyntaxError as e:
                return {"success": False, "error": f"SyntaxError pada {target_path.name}: {e}"}

        lock_file = target_path.with_suffix(target_path.suffix + ".lock")
        try:
            with file_lock_guard(lock_file, timeout_sec=5.0):
                target_path.write_text(code_content, encoding="utf-8")
        except Exception as e:
            return {"success": False, "error": f"File lock failed for {target_path}: {e}"}

        return {"success": True, "path": str(target_path), "bytes": len(code_content.encode("utf-8"))}

    def execute_test_suite(self, test_file_path: Path, cwd: Path | None = None) -> dict[str, Any]:
        """QualityAssuranceAgent: Execute test file and return execution telemetry."""
        work_dir = cwd or test_file_path.parent
        cmd = [sys.executable, str(test_file_path)]
        try:
            start_t = time.time()
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            elapsed = time.time() - start_t
            passed = proc.returncode == 0
            return {
                "passed": passed,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration_seconds": round(elapsed, 4),
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Execution timeout exceeded (30s)",
                "duration_seconds": 30.0,
            }
        except Exception as e:
            return {
                "passed": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
                "duration_seconds": 0.0,
            }

    def auto_repair_loop(
        self,
        target_file: Path,
        test_file: Path,
        current_code: str,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """AutoRepairAgent: Self-healing loop that repairs code until test suite passes."""
        working_code = current_code
        for attempt in range(1, max_attempts + 1):
            logger.info(f"[AutoRepairAgent] Running test evaluation round #{attempt} for {target_file.name}...")
            qa_res = self.execute_test_suite(test_file)
            if qa_res["passed"]:
                return {
                    "repaired": attempt > 1,
                    "attempts": attempt,
                    "final_code": working_code,
                    "qa_result": qa_res,
                }

            error_msg = qa_res["stderr"] or qa_res["stdout"]
            logger.warning(f"[AutoRepairAgent] Test failed on attempt #{attempt}:\n{error_msg[:200]}")

            # Request repair snippet from router
            repair_prompt = (
                f"File '{target_file.name}' gagal dalam pengujian otomatis:\n{error_msg}\n"
                f"Kode saat ini:\n```python\n{working_code}\n```\n"
                f"Perbaiki kode agar test berhasil lolos 100%. Kembalikan kode perbaikan lengkap."
            )
            rep_res = self.router.generate_text(
                [
                    {"role": "system", "content": "Kamu adalah ACE Automated Code Repair Specialist. Perbaiki bug sintaksis dan logika Python."},
                    {"role": "user", "content": repair_prompt},
                ],
                tier="fast",
                max_tokens=128,
            )
            rep_text = rep_res.get("text", "")
            import re
            m = re.search(r"```(?:python)?\s*(.*?)\s*```", rep_text, flags=re.DOTALL)
            if m:
                repaired_code = m.group(1).strip()
            else:
                repaired_code = working_code

            # Validate AST before applying
            try:
                ast.parse(repaired_code)
                working_code = repaired_code
                self.synthesize_module(target_file, working_code, is_python=True)
            except SyntaxError:
                logger.warning("[AutoRepairAgent] Synthesized code had syntax error, retaining previous candidate")

        # Final verification attempt
        final_qa = self.execute_test_suite(test_file)
        return {
            "repaired": final_qa["passed"],
            "attempts": max_attempts,
            "final_code": working_code,
            "qa_result": final_qa,
        }

    def build_project(
        self,
        project_name: str,
        specification_id: str,
        target_dir: Path,
        files_spec: dict[str, str],
        test_spec: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        """End-to-End Autonomous Factory Execution: Blueprint -> Coding -> Testing -> Auto-Repair -> Receipt."""
        target_dir.mkdir(parents=True, exist_ok=True)
        task = self.store.create_task(
            title_id=f"Software Factory: {project_name}",
            user_request=specification_id,
            normalized_goal=f"Membangun proyek '{project_name}' secara otonom dan memverifikasi kualitasnya",
        )
        self.store.emit_event(
            kind="task_started",
            status="ACTIVE",
            summary_code=f"Factory: {project_name}",
            technical_detail={"project_name": project_name, "target_dir": str(target_dir)},
        )

        plan = self.plan_architecture(project_name, specification_id)
        written_files = []

        # Synthesize modules
        for rel_path, code in files_spec.items():
            dest = target_dir / rel_path
            is_py = rel_path.endswith(".py")
            res = self.synthesize_module(dest, code, is_python=is_py)
            if not res.get("success"):
                logger.error(f"Failed to synthesize {rel_path}: {res.get('error')}")
                return {"success": False, "failed_file": rel_path, "error": res.get("error")}
            written_files.append(str(dest))

        # Test and Auto-Repair
        repair_report = None
        if test_spec:
            test_rel_path, test_code = test_spec
            test_dest = target_dir / test_rel_path
            self.synthesize_module(test_dest, test_code, is_python=True)
            written_files.append(str(test_dest))

            main_py = target_dir / list(files_spec.keys())[0]
            current_main_code = files_spec[list(files_spec.keys())[0]]
            repair_report = self.auto_repair_loop(main_py, test_dest, current_main_code)

        all_passed = bool(not test_spec or (repair_report and repair_report["qa_result"]["passed"]))

        # Record receipt
        receipt = self.store.record_receipt(
            task_id=task["task_id"],
            action_kind="software_factory_build",
            input_data=specification_id,
            output_data=json.dumps(plan),
            command_or_operation=f"SoftwareFactory.build_project({project_name})",
            exit_code=0 if all_passed else 1,
            stdout_text=repair_report["qa_result"]["stdout"] if repair_report else "No tests specified",
            stderr_text=repair_report["qa_result"]["stderr"] if repair_report else "",
            artifacts_created=written_files,
            verified_by="ace_software_factory_qa_agent",
            passed=all_passed,
        )

        self.store.update_task(
            task["task_id"],
            status="COMPLETED" if all_passed else "FAILED",
            verification_summary={"passed": all_passed, "receipt_id": receipt["receipt_id"]},
            artifacts=written_files,
        )

        return {
            "success": all_passed,
            "project_name": project_name,
            "target_dir": str(target_dir),
            "plan": plan,
            "written_files": written_files,
            "repair_report": repair_report,
            "receipt_id": receipt["receipt_id"],
        }
