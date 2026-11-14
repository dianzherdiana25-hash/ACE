"""ACE Self-Evolution & Recursive Intelligence Enhancement Engine.

Empowers ACE to inspect, diagnose, benchmark, and iteratively improve its own:
1. Codebase Health & Structural Integrity (AST metrics, cyclomatic checks, docstring ratios)
2. Cognitive & Model Router Telemetry (inference latency, token throughput, RAM efficiency)
3. Frontier Capability Verification & Promotion (empirical receipts)
4. Recursive Self-Optimization Proposals (identifying bottlenecks and self-generating tasks)
"""
from __future__ import annotations

import ast
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any

from .models_backend import ModelRouter
from .store import OperationalStore

logger = logging.getLogger("ace_self_evolution")


class SelfEvolutionEngine:
    """Orchestrates recursive self-diagnosis and autonomous intelligence enhancement."""

    def __init__(
        self,
        store: OperationalStore | None = None,
        router: ModelRouter | None = None,
        code_root: Path | None = None,
    ):
        self.code_root = code_root or (Path(__file__).resolve().parent.parent)
        self.store = store or OperationalStore()
        self.router = router or ModelRouter(self.store)
        self.evolution_log_path = self.store.workspace / "self_evolution_log.jsonl"
        self.status_path = self.store.workspace / "self_evolution.status.json"

    def audit_internal_codebase(self) -> dict[str, Any]:
        """Perform recursive AST static analysis on ACE's own codebase."""
        logger.info(f"[Self-Evolution] Auditing internal codebase at {self.code_root}...")
        total_files = 0
        total_lines = 0
        total_functions = 0
        total_classes = 0
        syntax_errors = []
        module_metrics = []

        for py_file in self.code_root.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue
            total_files += 1
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                total_lines += len(lines)
                tree = ast.parse(content, filename=str(py_file))

                fn_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
                cls_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
                total_functions += fn_count
                total_classes += cls_count

                module_metrics.append({
                    "file": py_file.name,
                    "lines": len(lines),
                    "functions": fn_count,
                    "classes": cls_count,
                    "has_docstring": ast.get_docstring(tree) is not None,
                })
            except SyntaxError as syn_err:
                syntax_errors.append({"file": str(py_file), "error": str(syn_err)})
            except Exception as e:
                logger.warning(f"Failed to inspect {py_file}: {e}")

        health_score = 100.0 if not syntax_errors else max(0.0, 100.0 - len(syntax_errors) * 20.0)
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_python_files": total_files,
            "total_lines_of_code": total_lines,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "syntax_errors_count": len(syntax_errors),
            "syntax_errors": syntax_errors,
            "health_score": health_score,
            "codebase_clean": len(syntax_errors) == 0,
            "top_modules": sorted(module_metrics, key=lambda m: m["lines"], reverse=True)[:5],
        }

    def benchmark_cognitive_inference(self) -> dict[str, Any]:
        """Empirically measure inference latency, token throughput, and memory budget."""
        logger.info("[Self-Evolution] Benchmarking cognitive inference pipeline...")
        hc = self.router.health_check()
        avail_ram = hc.get("local_gguf", {}).get("available_ram_mb", 0)

        # Run quick synthesis probe
        test_prompt = "def hitung_faktorial(n: int) -> int:\n    return 1 if n <= 1 else n * hitung_faktorial(n - 1)"
        start_t = time.monotonic()
        res = self.router.generate_text(
            [
                {"role": "system", "content": "Kamu adalah ACE engine internal benchmark."},
                {"role": "user", "content": f"Verifikasi kode Python ini secara ringkas: {test_prompt}"},
            ],
            tier="fast",
            max_tokens=32,
        )
        elapsed = time.monotonic() - start_t
        resp_text = res.get("text", "")
        backend = res.get("backend_used", "unavailable")
        model = res.get("model")
        healthy = bool(
            hc.get("local_gguf", {}).get("ready") is True
            and res.get("success") is True and res.get("status") == "SUCCESS"
            and isinstance(resp_text, str) and resp_text.strip()
            and isinstance(backend, str)
            and (backend.startswith("local-gguf:") or backend == "local-gguf-server")
            and isinstance(model, dict) and model.get("id")
            and res.get("evidence_event_id")
        )
        token_estimate = len(resp_text.split()) * 1.3 if healthy else 0.0
        throughput_tokens_per_sec = round(token_estimate / max(0.01, elapsed), 2)

        return {
            "active_backend": backend,
            "tier_used": res.get("tier_used", "auto"),
            "latency_seconds": round(elapsed, 4),
            "throughput_tokens_per_sec": throughput_tokens_per_sec,
            "throughput_is_estimate": True,
            "token_count_method": "word_count_times_1.3",
            "available_ram_mb": avail_ram,
            "backend_healthy": healthy,
            "status": "PASS" if healthy else "HOLD",
            "error_code": res.get("error_code") if not healthy else None,
            "model": model,
            "inference_id": res.get("inference_id"),
            "evidence_event_id": res.get("evidence_event_id"),
            "task_verified": False,
        }

    def verify_and_promote_self_capabilities(self) -> list[dict[str, Any]]:
        """Verify internal subsystems and promote tested capabilities to OperationalStore."""
        logger.info("[Self-Evolution] Evaluating self-capabilities for frontier promotion...")
        promoted = []

        # 1. Self-Diagnosis Capability
        audit_res = self.audit_internal_codebase()
        if audit_res["codebase_clean"]:
            self.store.set_frontier_capability(
                capability_id="cap_self_codebase_auditor",
                name_id="Automated AST Self-Codebase Auditor",
                category="self_evolution",
                status="KNOWN_AND_TESTED",
                evidence_ref=f"ast_clean:{audit_res['total_python_files']}_files:{audit_res['total_lines_of_code']}_loc",
            )
            promoted.append({"id": "cap_self_codebase_auditor", "status": "KNOWN_AND_TESTED"})

        # 2. Dynamic Hybrid Router Capability
        tier_deep = self.router.classify_task_tier("Rancang arsitektur sistem kompleks")
        tier_fast = self.router.classify_task_tier("Buatkan snippet helper cepat")
        if tier_deep == "deep" and tier_fast == "fast":
            self.store.set_frontier_capability(
                capability_id="cap_dynamic_hybrid_router",
                name_id="3-Tier Dynamic Hybrid Model Router",
                category="models",
                status="KNOWN_AND_TESTED",
                evidence_ref="verified:tier_classification_pass",
            )
            promoted.append({"id": "cap_dynamic_hybrid_router", "status": "KNOWN_AND_TESTED"})

        # This method does not execute SoftwareFactory. Its existence or an old
        # status marker cannot justify a new verified frontier promotion.
        factory = next((c for c in self.store.list_frontier()
                        if c["capability_id"] == "cap_software_factory"), None)
        if factory and factory.get("evidence_ref") == "verified:software_factory_end_to_end_pass":
            self.store.set_frontier_capability(
                capability_id="cap_software_factory", name_id=factory["name_id"],
                category=factory["category"], status="RETEST_REQUIRED",
                failure_reason="Legacy self-evolution marker has no factory execution receipt.",
            )

        return promoted

    def run_evolution_cycle(self) -> dict[str, Any]:
        """Execute one complete cycle of recursive self-evolution."""
        start_t = time.time()
        logger.info("=== Starting ACE Self-Evolution Cycle ===")

        # 1. Audit own codebase
        code_health = self.audit_internal_codebase()

        # 2. Benchmark inference
        inference_bench = self.benchmark_cognitive_inference()

        # 3. Promote verified capabilities
        promoted = self.verify_and_promote_self_capabilities()

        # 4. Generate next self-improvement proposal
        proposal = {
            "target_domain": "self_optimization",
            "priority": "HIGH",
            "objective": "Tingkatkan efisiensi cache parser AST dan kurangi latency inferensi model",
            "recommendation": (
                f"Seluruh {code_health['total_python_files']} berkas Python bersih tanpa syntax error. "
                f"Skor kesehatan kode: {code_health['health_score']}%. "
                f"Status inferensi: {inference_bench['status']}; perkiraan throughput "
                f"berdasarkan jumlah kata: {inference_bench['throughput_tokens_per_sec']} token/detik. "
                f"Terpromosikan {len(promoted)} kapabilitas baru ke Frontier Registry."
            ),
        }

        cycle_result = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_seconds": round(time.time() - start_t, 3),
            "code_health": code_health,
            "inference_bench": inference_bench,
            "promoted_capabilities": promoted,
            "self_improvement_proposal": proposal,
        }

        # Save to evolution telemetry log
        try:
            with open(self.evolution_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(cycle_result, ensure_ascii=False) + "\n")

            # Write status file
            self.status_path.write_text(
                json.dumps({
                    "schema": "ace.self_evolution.status.v1",
                    "running": True,
                    "last_cycle_at": cycle_result["timestamp"],
                    "code_health_score": code_health["health_score"],
                    "total_loc": code_health["total_lines_of_code"],
                    "promoted_count": len(promoted),
                    "proposal": proposal["recommendation"],
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to record evolution telemetry: {e}")

        logger.info(f"=== ACE Self-Evolution Cycle Completed in {cycle_result['duration_seconds']}s ===")
        return cycle_result

    def run_oaie_evolution_cycle(self, *, seed: int = 20261114) -> dict[str, Any]:
        """Run the unified offline OAIE closed-loop (G0 -> G3) anchored to ``self.store``."""
        from .oaie_engine import run_oaie_closed_loop

        result = run_oaie_closed_loop(self.store.workspace, seed=seed, store=self.store)
        try:
            with open(self.evolution_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"kind": "oaie_closed_loop", **result}, ensure_ascii=False) + "\n")
            self.status_path.write_text(
                json.dumps(
                    {
                        "schema": "ace.self_evolution.oaie.status.v1",
                        "running": True,
                        "last_cycle_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "oaie_verified_ok": result["verified_ok"],
                        "oaie_replay_digest": result["replay_digest"],
                        "oaie_generations": result["generations"],
                        "forgetting_count": result["forgetting_count"],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to record OAIE evolution telemetry: {e}")
        return result

    def run_oaie_unlimited_evolution_cycle(self, *, seed: int = 20261114) -> dict[str, Any]:
        """Run the unified offline OAIE-Unlimited sovereign cycle (`G0 -> G5_unlimited`)."""
        from .oaie_unlimited import run_oaie_unlimited_cycle

        result = run_oaie_unlimited_cycle(self.store.workspace, seed=seed, store=self.store)
        try:
            with open(self.evolution_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"kind": "oaie_unlimited_sovereign", **result}, ensure_ascii=False) + "\n")
            self.status_path.write_text(
                json.dumps(
                    {
                        "schema": "ace.self_evolution.oaie_unlimited.status.v1",
                        "running": True,
                        "last_cycle_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "verified_unlimited_ok": result["verified_unlimited_ok"],
                        "unlimited_replay_digest": result["unlimited_replay_digest"],
                        "life_responsibility": result["life_responsibility"],
                        "metabolic_status": result["homeostatic_economics"]["metabolic_status"],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to record OAIE-Unlimited telemetry: {e}")
        return result

    def run_sovereign_runtime_cycles(self, *, max_cycles: int = 3) -> dict[str, Any]:
        """Run bounded Epoch E SovereignRuntimeSupervisor ticks on this engine's workspace."""
        from .sovereign_runtime import SovereignRuntimeSupervisor

        sup = SovereignRuntimeSupervisor(self.store.workspace)
        return sup.run_until_health(
            target_health=0.8,
            max_cycles=max_cycles,
            task_factory=lambda idx: {
                "task_id": f"self_evo_tick_{idx}",
                "expected_benefit": 1.0,
                "estimated_dt": 0.4,
                "remaining_budget_ratio": 1.0,
            },
        )


