"""Typed Tool Broker enforcing allowlist, path isolation, subprocess RLIMIT_CPU, and ACE Runtime bridge.

Untrusted staged candidates in ``workspace/candidates/`` are NEVER executed here
(``BLOCKED_ENVIRONMENT``); only fixed trusted core test suites inside ``source_root``
may run via isolated subprocesses.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
from typing import Any, Callable

from .errors import IntegrityError, PolicyError, UncertainExternalEffectError
from .policy import (
    GoalPolicy,
    MAX_FILE_BYTES,
    TRUSTED_TEST_SUITES,
    path_matches_prefixes,
    safe_read_regular_file,
    safe_write_staged_file,
    validate_step,
)


class TypedToolBroker:
    """Executes schema-validated actions within the declared GoalPolicy and resource ceiling."""

    def __init__(
        self,
        *,
        workspace: Path,
        source_root: Path,
        external_handler: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.workspace = workspace
        self.root = source_root
        self.external_handler = external_handler

    def _load_ace_runtime(self):
        from ace_runtime import engine as rt_engine

        expected_engine = (self.root / "code/ace_runtime/engine.py").resolve()
        if (self.root / "code/ace_runtime/__init__.py").is_file():
            loaded_engine = Path(rt_engine.__file__).resolve()
            if loaded_engine != expected_engine:
                raise IntegrityError(
                    f"ace_runtime sys.path mismatch: loaded {loaded_engine}, expected {expected_engine}"
                )
        return rt_engine

    def dispatch(
        self,
        action: dict[str, Any],
        *,
        goal_id: str,
        policy: GoalPolicy,
        remaining_wall_s: float,
        remaining_cpu_s: float,
    ) -> dict[str, Any]:
        validate_step(action, policy=policy)
        tool = action["tool"]

        if tool == "inspect_file":
            rel = action["path"]
            if not path_matches_prefixes(rel, policy.read_prefixes):
                raise PolicyError("file path outside authorized read_prefixes")
            raw = safe_read_regular_file(self.root, rel, max_bytes=MAX_FILE_BYTES)
            return {
                "tool": tool,
                "path": rel,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        if tool == "verify_upstream_sources":
            manifest_raw = safe_read_regular_file(
                self.root, "docs/UPSTREAM_SOURCES.json", max_bytes=MAX_FILE_BYTES * 4
            )
            manifest = json.loads(manifest_raw.decode("utf-8"))
            files = manifest.get("files", {})
            if type(files) is not dict or not files:
                raise IntegrityError("UPSTREAM_SOURCES.json contains no files mapping")
            verified = 0
            for rel, meta in sorted(files.items()):
                content = safe_read_regular_file(self.root, rel, max_bytes=MAX_FILE_BYTES * 16)
                git_blob = hashlib.sha1(f"blob {len(content)}\0".encode("utf-8") + content).hexdigest()
                if git_blob != meta["git_blob"]:
                    raise IntegrityError(f"upstream blob mismatch on {rel}")
                verified += 1
            return {
                "tool": tool,
                "verified_files": verified,
                "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            }

        if tool == "run_trusted_suite":
            suite = action["suite"]
            if suite not in TRUSTED_TEST_SUITES:
                raise PolicyError("untrusted test suite forbidden")
            code_dir = self.root / "code"
            if not code_dir.is_dir():
                raise PolicyError("code directory missing in source_root")
            cpu_lim = max(1, int(math.ceil(remaining_cpu_s)))
            wall_lim = max(0.2, min(60.0, remaining_wall_s))

            def _apply_rlimits() -> None:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_lim, cpu_lim + 1))

            clean_env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PYTHONPATH": str(code_dir),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", suite, "-v"],
                cwd=str(self.root),
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=wall_lim,
                preexec_fn=_apply_rlimits,
                check=False,
            )
            out_tail = (proc.stdout + "\n" + proc.stderr).strip()[-1200:]
            if proc.returncode != 0:
                raise RuntimeError(f"trusted suite {suite} failed (rc={proc.returncode}): {out_tail}")
            return {
                "tool": tool,
                "suite": suite,
                "returncode": proc.returncode,
                "output_sha256": hashlib.sha256((proc.stdout + proc.stderr).encode("utf-8")).hexdigest(),
            }

        if tool == "stage_candidate":
            rel = action["rel_path"]
            content_bytes = action["content"].encode("utf-8")
            staging_base = self.workspace / "candidates" / goal_id
            written = safe_write_staged_file(staging_base, rel, content_bytes)
            rel_to_ws = written.relative_to(self.workspace).as_posix()
            return {
                "tool": tool,
                "staged_path": rel_to_ws,
                "kind": action["kind"],
                "bytes": len(content_bytes),
                "sha256": hashlib.sha256(content_bytes).hexdigest(),
                "executed": False,
                "execution_gate": "BLOCKED_ENVIRONMENT_DRAFT_ONLY",
            }

        if tool in {
            "ace_status",
            "ace_demo",
            "ace_enqueue_task",
            "ace_run_tasks",
            "ace_predict",
            "ace_evaluate",
            "ace_report",
        }:
            rt_engine = self._load_ace_runtime()
            Runtime = rt_engine.Runtime
            RuntimeIntegrityError = rt_engine.IntegrityError
            rt_ws = self.workspace / "real_ace_workspace"
            try:
                with Runtime(rt_ws) as runtime:
                    if tool == "ace_status":
                        z = runtime.status()
                        return {
                            "tool": tool,
                            "implementation": z["implementation"],
                            "completed": z["completed"],
                            "capabilities": z["capabilities"],
                            "scientific_decision": z["scientific_decision"],
                        }
                    if tool == "ace_demo":
                        from ace_runtime.cli import demo

                        result = demo(runtime)
                        if any(v["correct"] != v["total"] for v in result["evaluation"].values()):
                            raise IntegrityError("real ACE public demo failed")
                        z = result["status"]
                        return {
                            "tool": tool,
                            "tasks": z["completed"],
                            "capabilities": z["capabilities"],
                            "events": z["events"],
                            "implementation": z["implementation"],
                            "scientific_decision": z["scientific_decision"],
                        }
                    if tool == "ace_enqueue_task":
                        tid = runtime.enqueue(action["task"])
                        z = runtime.status()
                        return {
                            "tool": tool,
                            "task_id": tid,
                            "pending": z["pending"],
                            "implementation": z["implementation"],
                            "scientific_decision": z["scientific_decision"],
                        }
                    if tool == "ace_run_tasks":
                        max_t = action.get("max_tasks", 16)
                        outcomes = runtime.run(max_tasks=max_t)
                        z = runtime.status()
                        return {
                            "tool": tool,
                            "outcomes_count": len(outcomes),
                            "completed": z["completed"],
                            "capabilities": z["capabilities"],
                            "implementation": z["implementation"],
                            "scientific_decision": z["scientific_decision"],
                        }
                    if tool == "ace_predict":
                        rep = runtime.report(action["task_id"])
                        preds = [runtime.predict(action["task_id"], w) for w in action["inputs"]]
                        return {
                            "tool": tool,
                            "task_id": action["task_id"],
                            "model_id": rep["model_id"],
                            "predictions": preds,
                            "scientific_decision": "NOT_ASSESSED",
                        }
                    if tool == "ace_evaluate":
                        ev = runtime.evaluate(action["task_id"], action["examples"])
                        return {
                            "tool": tool,
                            "task_id": ev["task_id"],
                            "model_id": ev["model_id"],
                            "correct": ev["correct"],
                            "total": ev["total"],
                            "data_sha256": ev["data_sha256"],
                            "predictions_sha256": ev["predictions_sha256"],
                            "scientific_decision": ev["scientific_decision"],
                        }
                    if tool == "ace_report":
                        rep = runtime.report(action["task_id"])
                        return {
                            "tool": tool,
                            "task_id": rep["task_id"],
                            "task_status": rep["status"],
                            "phase": rep["phase"],
                            "model_id": rep["model_id"],
                            "scientific_decision": "NOT_ASSESSED",
                        }
            except RuntimeIntegrityError as exc:
                raise IntegrityError(f"ace_runtime integrity failure: {exc}") from exc

        if tool == "abstain":
            return {
                "tool": tool,
                "abstained": True,
                "reason": action["reason"],
                "scientific_decision": "NOT_ASSESSED",
            }

        if tool == "external_action":
            if self.external_handler is None:
                raise PolicyError("no external_handler configured for external_action")
            try:
                resp = self.external_handler(action["operation"], dict(action["payload"]))
            except UncertainExternalEffectError:
                raise
            except Exception as exc:
                raise UncertainExternalEffectError(
                    f"external_action outcome ambiguous after dispatch: {type(exc).__name__}: {exc}"
                ) from exc
            if type(resp) is not dict or type(resp.get("receipt_id")) is not str or type(resp.get("conclusive")) is not bool:
                raise UncertainExternalEffectError("external_handler returned malformed or non-conclusive receipt")
            if not resp["conclusive"]:
                raise UncertainExternalEffectError("external_handler reported non-conclusive delivery")
            return {
                "tool": tool,
                "operation": action["operation"],
                "receipt_id": resp["receipt_id"],
                "conclusive": True,
            }

        raise PolicyError("unauthorized tool")
