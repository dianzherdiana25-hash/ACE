"""Independent Host Verifier checking tool receipts against actual storage and post-conditions.

Never trusts model-provided or tool-returned ``ok: True`` claims without verifying
the underlying filesystem / ACE Runtime SQLite state independently.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .errors import IntegrityError, PolicyError
from .policy import (
    GoalPolicy,
    MAX_CANDIDATE_BYTES,
    MAX_FILE_BYTES,
    path_matches_prefixes,
    safe_read_regular_file,
)


def _is_hex64(val: Any) -> bool:
    return type(val) is str and len(val) == 64 and all(c in "0123456789abcdef" for c in val)


class IndependentVerifier:
    """Host-side post-condition verifier separated from Planner and ToolBroker."""

    def __init__(self, *, workspace: Path, source_root: Path):
        self.workspace = workspace
        self.root = source_root

    def verify_step_evidence(
        self,
        action: dict[str, Any],
        evidence: Any,
        *,
        goal_id: str,
        policy: GoalPolicy,
    ) -> dict[str, Any]:
        if type(evidence) is not dict or evidence.get("tool") != action.get("tool"):
            raise IntegrityError("verifier rejected malformed or mismatched tool receipt")
        tool = action["tool"]

        if tool == "inspect_file":
            rel = action["path"]
            if evidence.get("path") != rel or not path_matches_prefixes(rel, policy.read_prefixes):
                raise IntegrityError("verifier rejected inspect_file path mismatch")
            raw = safe_read_regular_file(self.root, rel, max_bytes=MAX_FILE_BYTES)
            actual_sha = hashlib.sha256(raw).hexdigest()
            if evidence.get("bytes") != len(raw) or evidence.get("sha256") != actual_sha:
                raise IntegrityError("verifier caught spoofed inspect_file digest or byte count")
            return {"verified": True, "kind": "file_inspection", "artifact_digest": actual_sha}

        if tool == "verify_upstream_sources":
            if type(evidence.get("verified_files")) is not int or evidence["verified_files"] < 1:
                raise IntegrityError("verifier rejected verify_upstream_sources count")
            if not _is_hex64(evidence.get("manifest_sha256")):
                raise IntegrityError("verifier rejected manifest_sha256")
            return {"verified": True, "kind": "source_provenance", "artifact_digest": evidence["manifest_sha256"]}

        if tool == "run_trusted_suite":
            if evidence.get("suite") != action["suite"] or evidence.get("returncode") != 0:
                raise IntegrityError("verifier rejected non-zero or mismatched trusted suite receipt")
            if not _is_hex64(evidence.get("output_sha256")):
                raise IntegrityError("verifier rejected trusted suite output_sha256")
            return {"verified": True, "kind": "trusted_test_pass", "artifact_digest": evidence["output_sha256"]}

        if tool == "stage_candidate":
            staged_path = evidence.get("staged_path")
            expected_prefix = f"candidates/{goal_id}/"
            if type(staged_path) is not str or not staged_path.startswith(expected_prefix):
                raise IntegrityError("verifier rejected staged_candidate outside goal staging directory")
            if evidence.get("executed") is not False:
                raise IntegrityError("verifier rejected staged_candidate claiming execution")
            raw = safe_read_regular_file(self.workspace, staged_path, max_bytes=MAX_CANDIDATE_BYTES)
            actual_sha = hashlib.sha256(raw).hexdigest()
            expected_sha = hashlib.sha256(action["content"].encode("utf-8")).hexdigest()
            if actual_sha != expected_sha or evidence.get("sha256") != actual_sha or evidence.get("bytes") != len(raw):
                raise IntegrityError("verifier caught staged candidate content mismatch")
            return {
                "verified": True,
                "kind": f"staged_candidate:{action['kind']}",
                "artifact_digest": actual_sha,
                "requires_review": True,
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
            if evidence.get("scientific_decision") != "NOT_ASSESSED":
                raise IntegrityError("verifier rejected false scientific_decision promotion")
            from ace_runtime.engine import Runtime

            rt_ws = self.workspace / "real_ace_workspace"
            if not (rt_ws / "ace.sqlite3").is_file():
                raise IntegrityError("verifier found no real_ace_workspace SQLite database")
            with Runtime(rt_ws) as runtime:
                live = runtime.status()
                if "implementation" in evidence and evidence["implementation"] != live["implementation"]:
                    raise IntegrityError("verifier caught mismatched ACE Runtime implementation digest")
                if tool == "ace_status":
                    if evidence.get("completed") != live["completed"] or evidence.get("capabilities") != live["capabilities"]:
                        raise IntegrityError("verifier caught spoofed ace_status counts")
                elif tool == "ace_demo":
                    if live["completed"] < 3 or live["capabilities"] < 2 or evidence.get("tasks") != live["completed"]:
                        raise IntegrityError("verifier caught incomplete or spoofed ace_demo state")
                elif tool == "ace_enqueue_task":
                    tid = evidence.get("task_id")
                    known_ids = {t["id"] for t in live["tasks"]}
                    if not _is_hex64(tid) or tid not in known_ids:
                        raise IntegrityError("verifier found enqueued task_id missing from ACE Runtime")
                elif tool == "ace_run_tasks":
                    if evidence.get("completed") != live["completed"] or evidence.get("capabilities") != live["capabilities"]:
                        raise IntegrityError("verifier caught spoofed ace_run_tasks completion counts")
                elif tool in {"ace_predict", "ace_evaluate", "ace_report"}:
                    tid = action["task_id"]
                    rep = runtime.report(tid)
                    if tool == "ace_evaluate":
                        ev_row = runtime.db.execute(
                            "SELECT report FROM evaluations WHERE task_id=?", (tid,)
                        ).fetchone()
                        if ev_row is None:
                            raise IntegrityError("verifier found missing terminal evaluation in ACE Runtime")
                        ev_db = __import__("json").loads(ev_row[0])
                        if (
                            ev_db["predictions_sha256"] != evidence.get("predictions_sha256")
                            or ev_db["correct"] != evidence.get("correct")
                        ):
                            raise IntegrityError("verifier caught spoofed ace_evaluate score")
                    elif tool == "ace_predict":
                        if rep["model_id"] != evidence.get("model_id"):
                            raise IntegrityError("verifier caught spoofed ace_predict model_id")
                    elif tool == "ace_report":
                        if rep["status"] != evidence.get("task_status"):
                            raise IntegrityError("verifier caught spoofed ace_report status")
            return {
                "verified": True,
                "kind": f"ace_runtime:{tool}",
                "artifact_digest": live["implementation"],
            }

        if tool == "abstain":
            if evidence.get("abstained") is not True or evidence.get("reason") != action["reason"]:
                raise IntegrityError("verifier rejected malformed abstain receipt")
            return {"verified": True, "kind": "epistemic_abstention", "artifact_digest": "0" * 64}

        if tool == "external_action":
            if evidence.get("conclusive") is not True or not evidence.get("receipt_id"):
                raise IntegrityError("verifier rejected non-conclusive external_action receipt")
            rid_sha = hashlib.sha256(evidence["receipt_id"].encode("utf-8")).hexdigest()
            return {"verified": True, "kind": f"external:{action['operation']}", "artifact_digest": rid_sha}

        raise PolicyError("verifier encountered unknown tool")
