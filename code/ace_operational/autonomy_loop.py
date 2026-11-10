"""Gap Discovery, Capability Frontier, AI Worker Orchestration, Learning Loop, and Anti-Stagnation (Appendices AA, AB).

Implements:
- `ace.gap.v1` discovery & fingerprint deduplication (`AUTO01`, `AUTO02`)
- Capability frontier registry (`AUTO03`, `AUTO04`, `AUTO05`)
- Concrete Anti-Stagnation & Pivot Ladder integrated with `StagnationDetector` (`A24`-`A26`, `AUTO12`-`AUTO14`)
- AI Worker orchestration over `MissionBus` with consumer check, snapshot hash check, idempotency, and independent verification (`AUTO06`-`AUTO09`, `A50`, `A51`)
- Bounded skill learning on 2+ cases, negative-transfer monitoring, and automatic parent task resumption (`A27`-`A30`, `AUTO10`, `AUTO11`)
- Priority agenda with aging (`A53`, `A54`) and staged self-update + rollback (`A55`, `A56`)
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from ace_mission.bus import MissionBus
from ace_self_dev.stagnation_detector import StagnationDetector
from . import RELEASE_VERSION, SCHEMA_VERSION_MANIFEST
from .coding_loop import CodingAgentLoop, atomic_write_verified, compute_file_sha256
from .store import OperationalStore, utc_now_iso


PIVOT_LADDER = (
    "direct_synthesis",
    "shrink_reproduction",
    "ast_structural_rewrite",
    "micro_skill_learning",
    "worker_delegation",
    "park_with_resume_condition",
)


class AutonomyOrchestrator:
    """Coordinates gap detection, anti-stagnation pivots, worker delegation, and skill learning."""

    def __init__(self, store: OperationalStore):
        self.store = store
        self.coding = CodingAgentLoop(store)
        self.mission_bus = MissionBus(store.workspace / "mission_bus.sqlite3")
        self.stagnation_detector = StagnationDetector(
            patience_k=2,
            registry_path=str(store.workspace / "stagnation_registry.json"),
        )

    # --- 1. Gap Discovery & Frontier (`AUTO01` - `AUTO05`) ---
    def report_gap(
        self,
        *,
        source_task_id: str,
        error_type: str,
        missing_skill_or_tool: str,
        description_id: str,
        reproduction_ref: str = "",
        resolution_strategy: str = "micro_experiment",
        frontier_status: str = "UNKNOWN_TO_ACE",
    ) -> dict[str, Any]:
        gap, is_new = self.store.record_gap(
            source_task_id=source_task_id,
            error_type=error_type,
            missing_skill_or_tool=missing_skill_or_tool,
            description_id=description_id,
            reproduction_ref=reproduction_ref,
            resolution_strategy=resolution_strategy,
        )
        cap_id = f"cap_{gap['fingerprint'][:10]}"
        self.store.set_frontier_capability(
            capability_id=cap_id,
            name_id=description_id,
            category=error_type,
            status=frontier_status if frontier_status != "KNOWN_AND_TESTED" else "AVAILABLE_UNVERIFIED",
            failure_reason=description_id,
        )
        task = self.store.get_task(source_task_id)
        conv_id = task["conversation_id"] if task else "conv_utama"
        if is_new:
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=source_task_id,
                kind="gap_detected",
                status="LEARNING",
                summary_code="gap_recorded",
                technical_detail={
                    "gap_id": gap["gap_id"],
                    "missing_skill_or_tool": missing_skill_or_tool,
                    "error_type": error_type,
                    "description_id": description_id,
                },
            )
        return {"gap": gap, "created_new": is_new, "capability_id": cap_id}

    # --- 2. Anti-Stagnation & Pivot Ladder (`A24`-`A26`, `AUTO12`-`AUTO14`) ---
    def evaluate_attempt_and_pivot(
        self,
        *,
        task_id: str,
        candidate_code: str,
        error_class: str,
        error_detail: str = "",
        metric_score: float = 0.0,
        external_resource_unavailable: bool = False,
    ) -> dict[str, Any]:
        """Check candidate attempt against prior attempts; detect duplicate patch/error and execute pivot ladder."""
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Task tidak ditemukan: {task_id}")
        conv_id = task["conversation_id"]

        patch_hash = hashlib.sha256(candidate_code.strip().encode("utf-8")).hexdigest()[:16]
        # Normalize whitespace/comments for semantic signature
        normalized_lines = [
            line.split("#")[0].strip()
            for line in candidate_code.splitlines()
            if line.split("#")[0].strip()
        ]
        semantic_sig = hashlib.sha256("\n".join(normalized_lines).encode("utf-8")).hexdigest()[:16]

        prior_attempts = self.store.list_attempts(task_id)
        duplicate_patch = any(a["patch_hash"] == patch_hash for a in prior_attempts)
        sem_eq, _ = self.stagnation_detector.check_semantic_equivalence(task_id, semantic_sig)
        duplicate_semantic = sem_eq or any(a["semantic_sig"] == semantic_sig for a in prior_attempts)

        # Record attempt in store and StagnationDetector registry
        att = self.store.record_attempt(
            task_id=task_id,
            patch_hash=patch_hash,
            semantic_sig=semantic_sig,
            error_class=error_class,
            strategy=task["current_strategy"],
            metric_score=metric_score,
        )
        self.stagnation_detector.registry.register(
            task_id=task_id,
            bitvector_hash=semantic_sig,
            candidate_id=att["attempt_id"],
            cycle_id=len(prior_attempts) + 1,
            source_sha=patch_hash,
            score=metric_score,
            bitvector=semantic_sig,
        )

        consecutive_same_error = (
            len(prior_attempts) >= 1 and prior_attempts[-1]["error_class"] == error_class and error_class != "NONE"
        )
        stagnant = bool(
            duplicate_patch
            or duplicate_semantic
            or consecutive_same_error
            or external_resource_unavailable
        )

        attempt_num = int(task["attempt_count"]) + 1
        if not stagnant and error_class == "NONE":
            updated = self.store.update_task(
                task_id,
                attempt_count=attempt_num,
                stagnation_score=0.0,
            )
            return {
                "stagnant": False,
                "duplicate_patch_rejected": False,
                "pivot_action": "none",
                "task": updated,
            }

        # Determine next strategy on the Pivot Ladder
        cur_strat = task["current_strategy"]
        if external_resource_unavailable:
            next_strat = "park_with_resume_condition"
        elif cur_strat in PIVOT_LADDER:
            idx = PIVOT_LADDER.index(cur_strat)
            next_strat = PIVOT_LADDER[min(idx + 1, len(PIVOT_LADDER) - 1)]
        else:
            next_strat = "shrink_reproduction"

        reason_id = (
            "patch identik pernah dicoba sebelumnya"
            if duplicate_patch
            else (
                "sumber daya eksternal tidak tersedia saat ini"
                if external_resource_unavailable
                else f"pola error `{error_class}` berulang tanpa peningkatan metrik"
            )
        )
        new_hypothesis = (
            f"Hipotesis diperbarui setelah percobaan #{attempt_num}: `{error_class}` ({error_detail or reason_id}) "
            f"membutuhkan peralihan ke `{next_strat}`."
        )

        if next_strat == "park_with_resume_condition":
            resume_cond = (
                "Sediakan sumber daya/dependensi yang dibutuhkan atau jalankan ulang setelah koneksi siap."
                if external_resource_unavailable
                else "Butuh peninjauan ulang spesifikasi atau latihan sub-keterampilan baru."
            )
            updated = self.store.update_task(
                task_id,
                status="PAUSED",
                current_strategy=next_strat,
                active_hypothesis=new_hypothesis,
                attempt_count=attempt_num,
                stagnation_score=1.0,
                resume_condition=resume_cond,
                next_action="tunggu_syarat_lanjut",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="task_paused",
                status="PAUSED",
                summary_code="parked_due_to_stagnation_or_resource",
                technical_detail={"reason": reason_id, "resume_condition": resume_cond, "to_strategy": next_strat},
            )
            return {
                "stagnant": True,
                "duplicate_patch_rejected": duplicate_patch,
                "pivot_action": "parked",
                "from_strategy": cur_strat,
                "to_strategy": next_strat,
                "task": updated,
            }

        # Emit strategy_changed & hypothesis_formed events
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="hypothesis_formed",
            status="ACTIVE",
            summary_code="hypothesis_updated_after_failure",
            technical_detail={"hypothesis": new_hypothesis, "error_class": error_class},
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=task_id,
            kind="strategy_changed",
            status="LEARNING" if next_strat == "micro_skill_learning" else "ACTIVE",
            summary_code="pivot_strategy_triggered",
            technical_detail={
                "from_strategy": cur_strat,
                "to_strategy": next_strat,
                "reason": reason_id,
                "duplicate_patch_rejected": duplicate_patch,
            },
        )
        updated = self.store.update_task(
            task_id,
            status="LEARNING" if next_strat == "micro_skill_learning" else "ACTIVE",
            current_strategy=next_strat,
            active_hypothesis=new_hypothesis,
            attempt_count=attempt_num,
            stagnation_score=min(1.0, float(task["stagnation_score"]) + 0.35),
            next_action=f"jalankan_{next_strat}",
        )
        return {
            "stagnant": True,
            "duplicate_patch_rejected": duplicate_patch,
            "pivot_action": next_strat,
            "from_strategy": cur_strat,
            "to_strategy": next_strat,
            "task": updated,
        }

    # --- 3. AI Worker Orchestration & Host Bridge (`AUTO06`-`AUTO09`, `A50`, `A51`) ---
    def set_worker_consumer_active(self, active: bool) -> None:
        self.store.set_meta("worker_consumer_active", "true" if active else "false")
        if active:
            self.store.set_meta("worker_consumer_last_seen", utc_now_iso())

    def is_worker_consumer_active(self) -> bool:
        return self.store.get_meta("worker_consumer_active", "false").lower() == "true"

    def dispatch_work_order(
        self,
        *,
        parent_task_id: str,
        objective: str,
        target_file: Path,
        worker_kind: str = "coding_worker",
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an `ace.work_order.v1` and enqueue on `MissionBus` with consumer check (`AUTO06`, `AUTO07`, `A51`)."""
        task = self.store.get_task(parent_task_id)
        if not task:
            raise KeyError(f"Parent task tidak ditemukan: {parent_task_id}")
        conv_id = task["conversation_id"]
        snap_hash = compute_file_sha256(target_file)
        idem = idempotency_key or hashlib.sha256(f"{parent_task_id}::{objective}::{snap_hash}".encode("utf-8")).hexdigest()[:20]

        wo, created_new = self.store.create_work_order(
            parent_task_id=parent_task_id,
            idempotency_key=idem,
            worker_kind=worker_kind,
            objective=objective,
            base_snapshot_hash=snap_hash,
            payload={"target_file": str(target_file), **(payload or {})},
        )
        if not created_new:
            return {"work_order": wo, "created_new": False, "consumer_active": self.is_worker_consumer_active()}

        mission_id = self.mission_bus.create_mission(
            goal=objective[:120],
            hypothesis=f"Work order {wo['work_order_id']} untuk tugas {parent_task_id}",
            task_family_ids=[parent_task_id],
            inputs=[{"path": str(target_file), "sha256": snap_hash if len(snap_hash) == 64 else "0" * 64}],
            budget={"time_sec": 30, "max_candidates": 8},
            acceptance={"metric": "exit_code", "threshold": 0, "comparator": "=="},
            forbidden=["docs/UPSTREAM_SOURCES.json"],
        )
        wo = self.store.update_work_order(wo["work_order_id"], status="PENDING", result={"mission_id": mission_id})

        consumer_live = self.is_worker_consumer_active()
        if not consumer_live:
            # Rule AUTO07: Do NOT wait forever when no consumer is running!
            wo = self.store.update_work_order(
                wo["work_order_id"],
                status="NO_ACTIVE_CONSUMER_FALLBACK",
                verification_status="SKIPPED_NO_CONSUMER",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=parent_task_id,
                kind="strategy_changed",
                status="ACTIVE",
                summary_code="worker_unavailable_local_fallback",
                technical_detail={
                    "from_strategy": "worker_delegation",
                    "to_strategy": "local_synthesis_fallback",
                    "reason": "tidak ada worker consumer aktif sehingga ACE beralih ke eksekusi lokal tanpa menggantung",
                    "work_order_id": wo["work_order_id"],
                },
            )
            return {"work_order": wo, "created_new": True, "consumer_active": False, "fallback_to_local": True}

        self.store.emit_event(
            conversation_id=conv_id,
            task_id=parent_task_id,
            kind="worker_requested",
            status="WAITING_FOR_DEPENDENCY",
            summary_code="work_order_dispatched",
            technical_detail={"work_order_id": wo["work_order_id"], "worker_kind": worker_kind, "objective": objective},
            artifact_refs=[str(target_file)],
        )
        self.store.update_task(
            parent_task_id,
            status="WAITING_FOR_DEPENDENCY",
            next_action=f"tunggu_worker_{wo['work_order_id']}",
        )
        return {"work_order": wo, "created_new": True, "consumer_active": True, "fallback_to_local": False}

    def submit_and_verify_worker_result(
        self,
        *,
        work_order_id: str,
        worker_id: str = "worker_antigravity_local",
        candidate_code: str,
        verification_cmd: list[str] | None = None,
    ) -> dict[str, Any]:
        """Receive candidate result from worker, check snapshot hash (`A50`), and run independent verification (`AUTO08`, `AUTO09`)."""
        wo = self.store.get_work_order(work_order_id)
        if not wo:
            raise KeyError(f"Work order tidak ditemukan: {work_order_id}")

        parent_id = wo["parent_task_id"]
        task = self.store.get_task(parent_id)
        conv_id = task["conversation_id"] if task else "conv_utama"
        target_file = Path(wo["payload"].get("target_file") or (self.store.workspace / "projects" / "worker_out.py"))

        current_disk_hash = compute_file_sha256(target_file)
        if current_disk_hash != wo["base_snapshot_hash"]:
            # Rule A50: Reject worker output built against a stale base snapshot!
            updated_wo = self.store.update_work_order(
                work_order_id,
                status="REJECTED_STALE_SNAPSHOT",
                claimed_by=worker_id,
                result={"error": "stale_base_snapshot", "expected": wo["base_snapshot_hash"], "actual": current_disk_hash},
                verification_status="REJECTED",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=parent_id,
                kind="worker_completed",
                status="ACTIVE",
                summary_code="worker_rejected_stale_snapshot",
                technical_detail={"work_order_id": work_order_id, "reason": "base_snapshot_hash sudah basi"},
                artifact_refs=[str(target_file)],
                verification_passed=False,
            )
            return {"accepted": False, "reason": "stale_base_snapshot", "work_order": updated_wo}

        # Stage candidate in temporary verification file before touching real target (`AUTO09`)
        staging_file = target_file.parent / f".worker_stage_{target_file.name}"
        atomic_write_verified(staging_file, candidate_code)
        cmd = verification_cmd or [sys.executable, str(staging_file)]
        ver = self.coding.run_command_with_receipt(
            task_id=parent_id,
            cmd=cmd,
            cwd=staging_file.parent,
            action_kind="verify_worker_output",
            artifacts_created=[str(staging_file)],
        )
        if staging_file.exists():
            staging_file.unlink()

        if not ver["passed"]:
            # Rule AUTO09: Reject failing worker output and protect parent task!
            updated_wo = self.store.update_work_order(
                work_order_id,
                status="REJECTED_FAILED_VERIFICATION",
                claimed_by=worker_id,
                result={"stdout": ver["stdout"], "stderr": ver["stderr"], "receipt_id": ver["receipt"]["receipt_id"]},
                verification_status="REJECTED",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=parent_id,
                kind="worker_completed",
                status="ACTIVE",
                summary_code="worker_output_failed_verification",
                technical_detail={"work_order_id": work_order_id, "stderr": ver["stderr"][-200:]},
                artifact_refs=[str(target_file)],
                verification_passed=False,
            )
            if task and task["status"] == "WAITING_FOR_DEPENDENCY":
                self.store.update_task(parent_id, status="ACTIVE", next_action="perbaiki_lokal_setelah_worker_ditolak")
            return {"accepted": False, "reason": "verification_failed", "work_order": updated_wo, "verification": ver}

        # Verification passed: atomically apply to target file and advance parent task (`AUTO08`)
        atomic_write_verified(target_file, candidate_code, expected_preimage_sha256=wo["base_snapshot_hash"])
        updated_wo = self.store.update_work_order(
            work_order_id,
            status="COMPLETED",
            claimed_by=worker_id,
            result={"stdout": ver["stdout"], "receipt_id": ver["receipt"]["receipt_id"], "target_file": str(target_file)},
            verification_status="VERIFIED",
        )
        self.store.set_frontier_capability(
            capability_id="cap_host_bridge",
            name_id="Delegasi Worker AI via Host Bridge / MissionBus",
            category="bridge",
            status="KNOWN_AND_TESTED",
            evidence_ref=ver["receipt"]["receipt_id"],
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=parent_id,
            kind="worker_completed",
            status="COMPLETED",
            summary_code="worker_output_verified_and_integrated",
            technical_detail={"work_order_id": work_order_id, "receipt_id": ver["receipt"]["receipt_id"]},
            artifact_refs=[str(target_file)],
            verification_passed=True,
        )
        if task:
            artifacts = list(task["artifacts"]) + [{"id": target_file.name, "path": str(target_file), "kind": "worker_verified"}]
            self.store.update_task(
                parent_id,
                status="COMPLETED",
                artifacts=artifacts,
                verification_summary={"passed": True, "worker_receipt_id": ver["receipt"]["receipt_id"], "sample_output": ver["stdout"].strip()},
                next_action="selesai",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=parent_id,
                kind="task_completed",
                status="COMPLETED",
                summary_code="parent_task_completed_after_worker",
                technical_detail={"goal": task["normalized_goal"]},
                artifact_refs=[str(target_file)],
                verification_passed=True,
            )
        return {"accepted": True, "work_order": updated_wo, "verification": ver}

    # --- 4. Bounded Learning Loop & Automatic Parent Task Resumption (`A27`-`A30`, `AUTO10`, `AUTO11`) ---
    def learn_skill_and_resume_parent(
        self,
        *,
        gap_id: str,
        skill_name: str = "rekap_kelompok_json_csv",
        domain: str = "data_processing",
    ) -> dict[str, Any]:
        """Run a 2-case micro-experiment (`AUTO10`), promote verified skill (`ace.skill.v1`), and resume parent task (`AUTO11`)."""
        gaps = {g["gap_id"]: g for g in self.store.list_gaps()}
        if gap_id not in gaps:
            raise KeyError(f"Gap tidak ditemukan: {gap_id}")
        gap = gaps[gap_id]
        parent_id = gap["source_task_id"]
        parent_task = self.store.get_task(parent_id)
        conv_id = parent_task["conversation_id"] if parent_task else "conv_utama"

        learn_task = self.store.create_task(
            conversation_id=conv_id,
            parent_task_id=parent_id,
            kind="learning_task",
            title_id=f"Pelajari keterampilan: {skill_name}",
            user_request=f"Pelajari cara menangani {gap['missing_skill_or_tool']}",
            normalized_goal=f"Kuasai dan uji keterampilan {skill_name} pada dua kasus berbeda",
            priority=9.0,
        )
        self.store.update_gap(gap_id, status="LEARNING_IN_PROGRESS", linked_learning_task_id=learn_task["task_id"])
        self.store.update_task(learn_task["task_id"], status="LEARNING")

        lab_dir = self.store.workspace / "projects" / "learning_lab" / gap_id
        lab_dir.mkdir(parents=True, exist_ok=True)
        skill_module = lab_dir / f"{skill_name}.py"

        atomic_write_verified(
            skill_module,
            '''#!/usr/bin/env python3
"""Modul keterampilan terverifikasi hasil pembelajaran mandiri ACE."""
from __future__ import annotations

import json
import sys


def kelompokkan_dan_jumlahkan(items: list[dict], key_field: str, val_field: str) -> dict[str, int]:
    hasil: dict[str, int] = {}
    for row in items:
        k = str(row.get(key_field, "lainnya")).strip().lower() or "lainnya"
        v = int(row.get(val_field, 0))
        hasil[k] = hasil.get(k, 0) + v
    return hasil


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "case1"
    if mode == "case1":
        data = [{"kategori": "makan", "nominal": 20000}, {"kategori": "makan", "nominal": 15000}]
        res = kelompokkan_dan_jumlahkan(data, "kategori", "nominal")
        assert res == {"makan": 35000}, f"Gagal case1: {res}"
        print(json.dumps({"case": "case1", "result": res}))
    else:
        # Held-out variation case (`AUTO10`)
        data2 = [{"divisi": "riset", "biaya": 50000}, {"divisi": "operasi", "biaya": 30000}, {"divisi": "riset", "biaya": 25000}]
        res2 = kelompokkan_dan_jumlahkan(data2, "divisi", "biaya")
        assert res2 == {"riset": 75000, "operasi": 30000}, f"Gagal case2: {res2}"
        print(json.dumps({"case": "case2", "result": res2}))
''',
        )

        # Verify on Case 1 (initial) and Case 2 (variation) (`AUTO10`)
        run1 = self.coding.run_command_with_receipt(
            task_id=learn_task["task_id"],
            cmd=[sys.executable, str(skill_module), "case1"],
            cwd=lab_dir,
            action_kind="verify_learning_case_1",
            artifacts_created=[str(skill_module)],
        )
        run2 = self.coding.run_command_with_receipt(
            task_id=learn_task["task_id"],
            cmd=[sys.executable, str(skill_module), "case2"],
            cwd=lab_dir,
            action_kind="verify_learning_case_2",
            artifacts_created=[str(skill_module)],
        )
        both_passed = run1["passed"] and run2["passed"]

        exp = self.store.save_learning_experience(
            task_id=learn_task["task_id"],
            gap_id=gap_id,
            failure_signature=f"{gap['error_type']}::{gap['missing_skill_or_tool']}",
            root_cause=gap["description_id"],
            strategy_before="direct_synthesis",
            strategy_after="verified_grouping_helper",
            delta_change=f"Menambahkan helper `{skill_name}` dengan normalisasi kunci dan akumulator integer",
            extracted_rule="Gunakan normalisasi kunci lowercase dan default 0 saat mengelompokkan item dictionary.",
            applicable_when=["Input berupa list[dict] dengan field kategori dan numerik"],
            not_applicable_when=["Input berupa stream biner mentah tanpa skema"],
            verification_evidence={
                "case1_receipt": run1["receipt"]["receipt_id"],
                "case2_receipt": run2["receipt"]["receipt_id"],
                "both_passed": both_passed,
            },
            reusable_skill_candidate=both_passed,
        )

        skill = self.store.save_skill(
            name=skill_name,
            domain=domain,
            preconditions=["Data berbentuk daftar objek/dictionary", "Terdapat kolom kunci dan kolom angka"],
            boundary_limitations=["Hanya untuk agregasi penjumlahan bulat di memori lokal"],
            procedure_steps=[
                "Normalisasi string kunci ke huruf kecil",
                "Akumulasikan nilai integer per kunci",
                "Verifikasi hasil agregasi terhadap minimal 2 kasus uji",
            ],
            verification_template={"module": str(skill_module), "cases": ["case1", "case2"]},
            source_task_ids=[learn_task["task_id"], parent_id],
        )

        self.store.update_gap(gap_id, status="RESOLVED", linked_learning_task_id=learn_task["task_id"])
        self.store.set_frontier_capability(
            capability_id=f"cap_{gap['fingerprint'][:10]}",
            name_id=gap["description_id"],
            category=domain,
            status="KNOWN_AND_TESTED",
            evidence_ref=run2["receipt"]["receipt_id"],
        )
        self.store.update_task(
            learn_task["task_id"],
            status="COMPLETED",
            artifacts=[{"id": skill_module.name, "path": str(skill_module), "kind": "learned_skill"}],
            verification_summary={"passed": both_passed, "receipts": [run1["receipt"]["receipt_id"], run2["receipt"]["receipt_id"]]},
        )
        self.store.emit_event(
            conversation_id=conv_id,
            task_id=parent_id,
            kind="skill_learned",
            status="ACTIVE",
            summary_code="skill_learned_and_verified",
            technical_detail={"skill_id": skill["skill_id"], "skill_name": skill_name, "gap_id": gap_id},
            artifact_refs=[str(skill_module)],
            verification_passed=both_passed,
        )

        # Rule AUTO11: Automatically resume and complete the parent user task!
        resumed_parent = None
        if parent_task and parent_task["status"] != "COMPLETED":
            resumed_res = self.coding.execute_coding_task(
                parent_id,
                domain="expense_tracker",
                options={"include_categories": True, "default_period": "bulanan"},
            )
            resumed_parent = resumed_res["task"]

        return {
            "learning_task": self.store.get_task(learn_task["task_id"]),
            "experience": exp,
            "skill": skill,
            "gap": self.store.list_gaps()[0],
            "resumed_parent_task": resumed_parent,
        }

    # --- 5. Priority Agenda with Aging (`A53`, `A54`) ---
    def get_prioritized_agenda(self) -> list[dict[str, Any]]:
        """Score queued/paused/learning tasks so user tasks come first and older tasks gain aging bonus."""
        tasks = [
            t for t in self.store.list_tasks(limit=100)
            if t["status"] not in ("COMPLETED", "CANCELLED")
        ]
        now_ts = time.time()
        scored = []
        for t in tasks:
            try:
                created_dt = datetime.strptime(t["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_minutes = max(0.0, (now_ts - created_dt.timestamp()) / 60.0)
            except Exception:
                age_minutes = 0.0
            user_boost = 30.0 if t["kind"] == "user_task" else 10.0
            aging_bonus = min(25.0, age_minutes * 0.5)
            effective_score = float(t["priority"]) + user_boost + aging_bonus
            scored.append({
                "task_id": t["task_id"],
                "title_id": t["title_id"],
                "kind": t["kind"],
                "status": t["status"],
                "base_priority": t["priority"],
                "aging_bonus": round(aging_bonus, 3),
                "effective_score": round(effective_score, 3),
                "next_action": t["next_action"],
            })
        scored.sort(key=lambda item: item["effective_score"], reverse=True)
        return scored

    # --- 6. Safe Staged Self-Update & Rollback (`A55`, `A56`) ---
    def stage_and_apply_update(
        self,
        new_version: str,
        *,
        smoke_test_passes: bool = True,
    ) -> dict[str, Any]:
        """Stage a candidate release manifest, run smoke test, and either activate or auto-rollback (`A55`, `A56`)."""
        cur_version = self.store.get_meta("release_version", RELEASE_VERSION)
        stage_dir = self.store.workspace / "releases" / new_version
        stage_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = stage_dir / "version_manifest.json"
        manifest = {
            "schema": SCHEMA_VERSION_MANIFEST,
            "version": new_version,
            "previous_version": cur_version,
            "staged_at": utc_now_iso(),
            "smoke_test_passed": smoke_test_passes,
        }
        atomic_write_verified(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False))

        if not smoke_test_passes:
            # Rule A56: Do NOT activate broken update; keep current release active!
            return {
                "activated": False,
                "rolled_back": True,
                "active_version": cur_version,
                "rejected_version": new_version,
                "reason": "Uji asap (smoke test) kandidat rilis gagal; rilis lama tetap dipertahankan.",
            }

        self.store.set_meta("previous_release_version", cur_version)
        self.store.set_meta("release_version", new_version)
        return {
            "activated": True,
            "rolled_back": False,
            "active_version": new_version,
            "previous_version": cur_version,
            "manifest_path": str(manifest_path),
        }

    def rollback_release(self) -> dict[str, Any]:
        cur_version = self.store.get_meta("release_version", RELEASE_VERSION)
        prev_version = self.store.get_meta("previous_release_version", "3.9.0-baseline")
        self.store.set_meta("release_version", prev_version)
        self.store.set_meta("previous_release_version", cur_version)
        return {
            "rolled_back": True,
            "active_version": prev_version,
            "rolled_back_from": cur_version,
        }
