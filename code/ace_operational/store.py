"""Durable SQLite Operational Store integrated with FencedStore lease fencing.

Implements Master Prompt Edition 4 Sections 18-24, 38, 53 and Appendices C, D, Z, AA, AB.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from typing import Any

from ace_self_dev.fenced_store import FencedStore, Lease, LeaseRejected

StaleLeaseError = LeaseRejected
from . import (
    RELEASE_VERSION,
    SCHEMA_ACTIVITY,
    SCHEMA_FRONTIER,
    SCHEMA_GAP,
    SCHEMA_LEARNING_EXPERIENCE,
    SCHEMA_PROBLEM_IR,
    SCHEMA_RECEIPT,
    SCHEMA_SKILL,
    SCHEMA_TASK,
    SCHEMA_WORK_ORDER,
)
from .story_projector import project_event_to_story


TASK_STATES = frozenset({
    "QUEUED",
    "ACTIVE",
    "WAITING_FOR_DEPENDENCY",
    "LEARNING",
    "VERIFYING",
    "READY_TO_INTEGRATE",
    "INTEGRATING",
    "COMPLETED",
    "PAUSED",
    "CANCELLED",
    "FAILED_WITH_RECOVERY_STATE",
})

TERMINAL_TASK_STATES = frozenset({
    "COMPLETED",
    "CANCELLED",
})

ALLOWED_TASK_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"ACTIVE", "LEARNING", "VERIFYING", "COMPLETED", "PAUSED", "CANCELLED", "WAITING_FOR_DEPENDENCY"},
    "ACTIVE": {
        "VERIFYING",
        "LEARNING",
        "WAITING_FOR_DEPENDENCY",
        "PAUSED",
        "CANCELLED",
        "FAILED_WITH_RECOVERY_STATE",
        "READY_TO_INTEGRATE",
        "COMPLETED",
    },
    "WAITING_FOR_DEPENDENCY": {"ACTIVE", "LEARNING", "VERIFYING", "COMPLETED", "PAUSED", "CANCELLED", "FAILED_WITH_RECOVERY_STATE"},
    "LEARNING": {"ACTIVE", "VERIFYING", "COMPLETED", "WAITING_FOR_DEPENDENCY", "PAUSED", "CANCELLED", "FAILED_WITH_RECOVERY_STATE"},
    "VERIFYING": {
        "READY_TO_INTEGRATE",
        "INTEGRATING",
        "COMPLETED",
        "ACTIVE",
        "LEARNING",
        "PAUSED",
        "CANCELLED",
        "FAILED_WITH_RECOVERY_STATE",
    },
    "READY_TO_INTEGRATE": {"INTEGRATING", "COMPLETED", "ACTIVE", "PAUSED", "CANCELLED", "FAILED_WITH_RECOVERY_STATE"},
    "INTEGRATING": {"COMPLETED", "ACTIVE", "PAUSED", "CANCELLED", "FAILED_WITH_RECOVERY_STATE"},
    "PAUSED": {"ACTIVE", "QUEUED", "CANCELLED"},
    "FAILED_WITH_RECOVERY_STATE": {"ACTIVE", "LEARNING", "QUEUED", "PAUSED", "CANCELLED"},
    "COMPLETED": {"ACTIVE", "VERIFYING", "WAITING_FOR_DEPENDENCY"},  # Allowed when user requests iterative modification on completed task
    "CANCELLED": {"QUEUED", "ACTIVE"},
}

FRONTIER_STATUSES = frozenset({
    "KNOWN_AND_TESTED",
    "KNOWN_BUT_WEAK",
    "AVAILABLE_UNVERIFIED",
    "UNKNOWN_TO_ACE",
    "MISSING_TOOL_OR_RESOURCE",
    "NEW_TASK_VARIANT",
    "LEARNING_IN_PROGRESS",
    "RETEST_REQUIRED",
})

DELIVERABLE_STATUSES = frozenset({
    "TODO",
    "IN_PROGRESS",
    "IMPLEMENTED_UNVERIFIED",
    "PASS",
    "FAILED",
    "BLOCKED_EXTERNAL",
})

F01_F24_CATALOG: list[tuple[str, str, list[str]]] = [
    ("F01", "Source, entry point, environment, model, dependency, dan versi aktif ditemukan secara nyata", []),
    ("F02", "Percakapan Indonesia beberapa giliran berjalan melalui backend aktual, termasuk koreksi, negasi, dan rujukan", ["F01"]),
    ("F03", "Perintah pengguna menghasilkan tindakan, perubahan, atau artefak yang sesuai", ["F02"]),
    ("F04", "ACE membuat program baru, menjalankannya, dan memenuhi kebutuhan perilakunya", ["F03"]),
    ("F05", "ACE memperbaiki bug nyata dan memeriksa regresi yang relevan", ["F03"]),
    ("F06", "ACE menyelesaikan masalah beberapa langkah serta merevisi keputusan berdasarkan bukti", ["F04", "F05"]),
    ("F07", "Memori, task, dan langkah berikut dapat dipulihkan setelah restart", ["F01"]),
    ("F08", "ACE menemukan kekurangan dari hasil kerja dan mengubahnya menjadi pekerjaan yang dapat dieksekusi", ["F06"]),
    ("F09", "ACE memilih serta menjalankan langkah relevan berikut tanpa instruksi setiap langkah", ["F07", "F08"]),
    ("F10", "Pengulangan tidak produktif terdeteksi dan menghasilkan perubahan pendekatan", ["F06"]),
    ("F11", "ACE mempelajari gap kemampuan, memeriksa hasil belajar, dan kembali mencoba tugas awal", ["F08", "F10"]),
    ("F12", "Kemampuan yang dipelajari membantu tugas berbeda setelah proses dimulai ulang", ["F07", "F11"]),
    ("F13", "ACE memilih worker AI, memberikan pekerjaan, menerima hasil, memeriksa, dan melanjutkan", ["F08"]),
    ("F14", "Bridge host menjalankan request, consumer, result, dan verification secara nyata", ["F13"]),
    ("F15", "Pertanyaan baru serta tugas coding dapat dikerjakan offline memakai model dan alat lokal", ["F02", "F04"]),
    ("F16", "Kontrak inti serta adapter tidak bergantung pada path atau API satu mesin", ["F01", "F15"]),
    ("F17", "Web anime localhost responsif untuk HP dan terhubung ke runtime yang sama dengan CLI", ["F02", "F07"]),
    ("F18", "Blok chatbot mengerjakan tugas; blok cerita merangkum aktivitas aktual secara singkat dan santai", ["F03", "F17"]),
    ("F19", "Installer menyiapkan dependency, runtime, model, konfigurasi, state, aset web, dan launcher", ["F16", "F17"]),
    ("F20", "ACE dapat digunakan dari sesi baru tanpa mengulang bootstrap manual", ["F19"]),
    ("F21", "Instalasi atau pembaruan yang terputus dapat dilanjutkan atau dipulihkan sambil menjaga data", ["F07", "F19"]),
    ("F22", "Satu perbaikan kemampuan dipilih ACE, diimplementasikan, diperiksa, diintegrasikan, diaktifkan, dan dipakai", ["F09", "F11"]),
    ("F23", "Riset menghasilkan keputusan atau eksperimen nyata, disertai evaluasi retensi atau transfer yang jujur", ["F12", "F22"]),
    ("F24", "Versi yang layak masuk target integrasi yang benar, ditunjuk installer, dan dapat dijalankan", ["F19", "F20", "F21", "F22", "F23"]),
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_workspace() -> Path:
    env_ws = os.environ.get("ACE_WORKSPACE")
    if env_ws:
        return Path(env_ws).expanduser().resolve()
    return (Path.home() / ".local" / "share" / "ace" / "workspace").resolve()


class OperationalStore:
    """Thread-safe, WAL-backed operational store with FencedStore lease protection."""

    def __init__(self, workspace: str | os.PathLike[str] | None = None):
        self.workspace = Path(workspace) if workspace is not None else default_workspace()
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "projects").mkdir(parents=True, exist_ok=True)
        (self.workspace / "artifacts").mkdir(parents=True, exist_ok=True)
        (self.workspace / "releases").mkdir(parents=True, exist_ok=True)

        # Bridge with FencedStore SQLite lease fencing (`code/ace_self_dev/fenced_store.py`)
        self.fenced = FencedStore(self.workspace / "fenced_leases.sqlite3")
        self._active_leases: dict[str, Lease] = {}
        self.db_path = self.workspace / "ace_operational.sqlite3"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._init_schema()
            self._seed_defaults()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "OperationalStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                client_message_id TEXT UNIQUE,
                task_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                parent_task_id TEXT,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                title_id TEXT NOT NULL,
                user_request TEXT NOT NULL,
                normalized_goal TEXT NOT NULL,
                constraints_json TEXT NOT NULL DEFAULT '[]',
                acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
                active_hypothesis TEXT NOT NULL DEFAULT '',
                current_strategy TEXT NOT NULL DEFAULT 'direct_synthesis',
                model_backend TEXT NOT NULL DEFAULT 'local-deterministic-v4',
                lease_owner TEXT NOT NULL DEFAULT '',
                lease_epoch INTEGER NOT NULL DEFAULT 0,
                lease_expires_at TEXT NOT NULL DEFAULT '',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                stagnation_score REAL NOT NULL DEFAULT 0.0,
                artifacts_json TEXT NOT NULL DEFAULT '[]',
                verification_summary_json TEXT NOT NULL DEFAULT '{}',
                resume_condition TEXT NOT NULL DEFAULT '',
                next_action TEXT NOT NULL DEFAULT '',
                error_summary TEXT NOT NULL DEFAULT '',
                checkpoint_json TEXT NOT NULL DEFAULT '{}',
                priority REAL NOT NULL DEFAULT 5.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS problem_irs (
                ir_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                schema_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                schema TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                actor TEXT NOT NULL,
                model_backend TEXT NOT NULL,
                summary_code TEXT NOT NULL,
                technical_detail_json TEXT NOT NULL DEFAULT '{}',
                artifact_refs_json TEXT NOT NULL DEFAULT '[]',
                verification_passed INTEGER,
                story_text TEXT NOT NULL DEFAULT '',
                avatar_state TEXT NOT NULL DEFAULT 'mendengar'
            );

            CREATE TABLE IF NOT EXISTS gaps (
                gap_id TEXT PRIMARY KEY,
                fingerprint TEXT UNIQUE NOT NULL,
                source_task_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                missing_skill_or_tool TEXT NOT NULL,
                description_id TEXT NOT NULL,
                reproduction_ref TEXT NOT NULL DEFAULT '',
                resolution_strategy TEXT NOT NULL DEFAULT 'micro_experiment',
                status TEXT NOT NULL DEFAULT 'OPEN',
                linked_learning_task_id TEXT NOT NULL DEFAULT '',
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS frontier (
                capability_id TEXT PRIMARY KEY,
                name_id TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence_ref TEXT NOT NULL DEFAULT '',
                failure_reason TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                preconditions_json TEXT NOT NULL DEFAULT '[]',
                boundary_limitations_json TEXT NOT NULL DEFAULT '[]',
                procedure_steps_json TEXT NOT NULL DEFAULT '[]',
                verification_template_json TEXT NOT NULL DEFAULT '{}',
                source_task_ids_json TEXT NOT NULL DEFAULT '[]',
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                negative_transfer_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learning_experiences (
                experience_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                gap_id TEXT NOT NULL DEFAULT '',
                failure_signature TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                strategy_before TEXT NOT NULL,
                strategy_after TEXT NOT NULL,
                delta_change TEXT NOT NULL,
                extracted_rule TEXT NOT NULL,
                applicable_when_json TEXT NOT NULL DEFAULT '[]',
                not_applicable_when_json TEXT NOT NULL DEFAULT '[]',
                verification_evidence_json TEXT NOT NULL DEFAULT '{}',
                reusable_skill_candidate INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS work_orders (
                work_order_id TEXT PRIMARY KEY,
                parent_task_id TEXT NOT NULL,
                mission_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT UNIQUE NOT NULL,
                worker_kind TEXT NOT NULL,
                objective TEXT NOT NULL,
                base_snapshot_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'PENDING',
                claimed_by TEXT NOT NULL DEFAULT '',
                result_json TEXT NOT NULL DEFAULT '{}',
                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action_kind TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                output_hash TEXT NOT NULL,
                command_or_operation TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                stdout_digest TEXT NOT NULL,
                stderr_digest TEXT NOT NULL,
                artifacts_created_json TEXT NOT NULL DEFAULT '[]',
                verified_by TEXT NOT NULL,
                passed INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                patch_hash TEXT NOT NULL,
                semantic_sig TEXT NOT NULL,
                error_class TEXT NOT NULL,
                strategy TEXT NOT NULL,
                metric_score REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS deliverables (
                deliverable_id TEXT PRIMARY KEY,
                title_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'TODO',
                remaining_work TEXT NOT NULL DEFAULT '',
                dependencies_json TEXT NOT NULL DEFAULT '[]',
                next_action TEXT NOT NULL DEFAULT '',
                artifacts_json TEXT NOT NULL DEFAULT '[]',
                source_version TEXT NOT NULL DEFAULT '',
                checks_executed_json TEXT NOT NULL DEFAULT '[]',
                blockers TEXT NOT NULL DEFAULT '',
                resume_condition TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                title_id TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                decision TEXT NOT NULL,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                retention_passed INTEGER NOT NULL DEFAULT 0,
                transfer_passed INTEGER NOT NULL DEFAULT 0,
                report_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proposer_staged_packages (
                staging_id TEXT PRIMARY KEY,
                request_id TEXT UNIQUE NOT NULL,
                proposal_id TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                identity_mode TEXT NOT NULL DEFAULT 'staging-only',
                blob_path TEXT NOT NULL,
                mission_id TEXT NOT NULL DEFAULT '',
                revoked INTEGER NOT NULL DEFAULT 0,
                revoked_by TEXT NOT NULL DEFAULT '',
                revoked_reason TEXT NOT NULL DEFAULT '',
                revocation_ledger_seq INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proposer_stage2_ratifications (
                ratification_id TEXT PRIMARY KEY,
                staging_id TEXT NOT NULL,
                audience TEXT NOT NULL,
                ratified_by TEXT NOT NULL,
                bound_payload_sha256 TEXT NOT NULL,
                issued_at_epoch REAL NOT NULL,
                expires_at_epoch REAL NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proposer_stage2_runs (
                execution_run_id TEXT PRIMARY KEY,
                staging_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                bound_payload_sha256 TEXT NOT NULL,
                ratification_id TEXT NOT NULL,
                identity_mode TEXT NOT NULL DEFAULT 'staging-only',
                status TEXT NOT NULL,
                stop_requested INTEGER NOT NULL DEFAULT 0,
                stop_reason TEXT NOT NULL DEFAULT '',
                stop_visible INTEGER NOT NULL DEFAULT 1,
                calls_used INTEGER NOT NULL DEFAULT 0,
                wall_seconds REAL NOT NULL DEFAULT 0.0,
                cost_units REAL NOT NULL DEFAULT 0.0,
                work_completed_units INTEGER NOT NULL DEFAULT 0,
                bundle_dir TEXT NOT NULL DEFAULT '',
                bundle_manifest_sha256 TEXT NOT NULL DEFAULT '',
                preaudit_report_sha256 TEXT NOT NULL DEFAULT '',
                preaudit_exit_code INTEGER NOT NULL DEFAULT -1,
                env_snapshot_json TEXT NOT NULL DEFAULT '{}',
                result_summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                finished_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS proposer_stage2_ledger (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                staging_id TEXT NOT NULL,
                execution_run_id TEXT NOT NULL DEFAULT '',
                payload_sha256 TEXT NOT NULL DEFAULT '',
                detail_json TEXT NOT NULL DEFAULT '{}',
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed_defaults(self) -> None:
        now = utc_now_iso()
        defaults = {
            "schema_version": "ace.operational.v5",
            "release_version": RELEASE_VERSION,
            "previous_release_version": "3.9.0-baseline",
            "profile": os.environ.get("ACE_PROFILE", "local-complete"),
            "offline_mode": "true" if os.environ.get("ACE_OFFLINE", "").lower() in ("1", "true", "yes") else "false",
            "allow_remote_in_offline_mode": "false",
            "active_conversation_id": "conv_utama",
            "egress_attempts_blocked": "0",
            "worker_consumer_active": "false",
            "worker_consumer_last_seen": "",
            "created_at": now,
        }
        for k, v in defaults.items():
            self._conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)", (k, v))

        self._conn.execute(
            """
            INSERT OR IGNORE INTO conversations(conversation_id, title, context_json, created_at, updated_at)
            VALUES ('conv_utama', 'Ruang Ngobrol ACE', '{}', ?, ?)
            """,
            (now, now),
        )

        initial_frontier = [
            ("cap_chat_id", "Percakapan Bahasa Indonesia & Pemahaman Niat", "bahasa", "KNOWN_AND_TESTED", "builtin:language_v4"),
            ("cap_coding_cli", "Pembuatan & Verifikasi Aplikasi CLI Python Lokal", "coding", "KNOWN_AND_TESTED", "builtin:coding_loop_v4"),
            ("cap_bug_repair", "Reproduksi, Diagnosis, & Perbaikan Bug Terverifikasi", "coding", "KNOWN_AND_TESTED", "builtin:bug_repair_v4"),
            ("cap_fenced_lease", "Penyimpanan Tugas Tahan-Crash & Fenced Lease", "runtime", "KNOWN_AND_TESTED", "builtin:fenced_store_v4"),
            ("cap_local_gguf", "Inferensi Model GGUF Lokal (llama.cpp)", "model", "AVAILABLE_UNVERIFIED", ""),
            ("cap_host_bridge", "Delegasi Worker AI via Host Bridge / MissionBus", "bridge", "AVAILABLE_UNVERIFIED", ""),
        ]
        for cap_id, name_id, cat, status, ev in initial_frontier:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO frontier(capability_id, name_id, category, status, evidence_ref, failure_reason, updated_at)
                VALUES (?, ?, ?, ?, ?, '', ?)
                """,
                (cap_id, name_id, cat, status, ev, now),
            )

        for deliv_id, title_id, deps in F01_F24_CATALOG:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO deliverables(
                    deliverable_id, title_id, status, remaining_work, dependencies_json,
                    next_action, artifacts_json, source_version, checks_executed_json,
                    blockers, resume_condition, updated_at
                ) VALUES (?, ?, 'TODO', 'Menunggu verifikasi penerimaan', ?, 'jalankan_verifikasi_f01_f24', '[]', ?, '[]', '', '', ?)
                """,
                (deliv_id, title_id, json.dumps(deps), RELEASE_VERSION, now),
            )
        self._conn.commit()

    # --- Meta helpers ---
    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
            self._conn.commit()

    def is_offline(self) -> bool:
        return self.get_meta("offline_mode", "false").lower() == "true"

    def set_offline(self, offline: bool) -> None:
        self.set_meta("offline_mode", "true" if offline else "false")

    def record_blocked_egress(self) -> int:
        with self._lock:
            cur = int(self.get_meta("egress_attempts_blocked", "0") or "0") + 1
            self.set_meta("egress_attempts_blocked", str(cur))
            return cur

    # --- Lease Management (bridged with FencedStore) ---
    def acquire_runtime_lease(self, owner: str = "ace-worker", ttl_sec: int = 120) -> int:
        with self._lock:
            if "runtime" in self._active_leases:
                try:
                    self.fenced.release(self._active_leases.pop("runtime"))
                except Exception:
                    pass
            lease = self.fenced.acquire("runtime", owner, ttl=float(ttl_sec))
            self._active_leases["runtime"] = lease
            return lease.epoch

    def release_runtime_lease(self, owner: str = "ace-worker") -> None:
        with self._lock:
            lease = self._active_leases.get("runtime")
            if lease and lease.owner == owner:
                self._active_leases.pop("runtime", None)
                try:
                    self.fenced.release(lease)
                except Exception:
                    pass

    def current_lease_epoch(self) -> int:
        with self.fenced._connect() as con:
            row = con.execute("SELECT epoch FROM counter WHERE id=1").fetchone()
            return int(row[0]) if row else 0

    # --- Conversation & Message Store ---
    def get_conversation(self, conversation_id: str = "conv_utama") -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if not row:
                now = utc_now_iso()
                self._conn.execute(
                    "INSERT INTO conversations(conversation_id, title, context_json, created_at, updated_at) VALUES (?, ?, '{}', ?, ?)",
                    (conversation_id, "Percakapan ACE", now, now),
                )
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
            msgs = self._conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC",
                (conversation_id,),
            ).fetchall()
            return {
                "conversation_id": row["conversation_id"],
                "title": row["title"],
                "context": json.loads(row["context_json"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "messages": [
                    {
                        "message_id": m["message_id"],
                        "conversation_id": m["conversation_id"],
                        "role": m["role"],
                        "text": m["text"],
                        "client_message_id": m["client_message_id"],
                        "task_id": m["task_id"],
                        "metadata": json.loads(m["metadata_json"] or "{}"),
                        "created_at": m["created_at"],
                    }
                    for m in msgs
                ],
            }

    def update_conversation_context(self, conversation_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            conv = self.get_conversation(conversation_id)
            ctx = conv["context"]
            ctx.update(updates)
            now = utc_now_iso()
            self._conn.execute(
                "UPDATE conversations SET context_json = ?, updated_at = ? WHERE conversation_id = ?",
                (json.dumps(ctx, ensure_ascii=False), now, conversation_id),
            )
            self._conn.commit()
            return ctx

    def find_message_by_client_id(self, client_message_id: str) -> dict[str, Any] | None:
        if not client_message_id:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM messages WHERE client_message_id = ?",
                (client_message_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "message_id": row["message_id"],
                "conversation_id": row["conversation_id"],
                "role": row["role"],
                "text": row["text"],
                "client_message_id": row["client_message_id"],
                "task_id": row["task_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "created_at": row["created_at"],
            }

    def add_message(
        self,
        conversation_id: str,
        role: str,
        text: str,
        *,
        client_message_id: str | None = None,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Insert a message or return existing if client_message_id already processed.
        Returns (message_dict, is_duplicate).
        """
        with self._lock:
            self.get_conversation(conversation_id)
            if client_message_id:
                existing = self.find_message_by_client_id(client_message_id)
                if existing is not None:
                    return existing, True
            msg_id = f"msg_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            meta_json = json.dumps(metadata or {}, ensure_ascii=False)
            self._conn.execute(
                """
                INSERT INTO messages(message_id, conversation_id, role, text, client_message_id, task_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, role, text, client_message_id, task_id, meta_json, now),
            )
            self._conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (now, conversation_id),
            )
            self._conn.commit()
            return {
                "message_id": msg_id,
                "conversation_id": conversation_id,
                "role": role,
                "text": text,
                "client_message_id": client_message_id,
                "task_id": task_id,
                "metadata": metadata or {},
                "created_at": now,
            }, False

    # --- Task Lifecycle & State Machine ---
    def create_task(
        self,
        *,
        conversation_id: str = "conv_utama",
        parent_task_id: str | None = None,
        kind: str = "user_task",
        title_id: str,
        user_request: str,
        normalized_goal: str,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        active_hypothesis: str = "Solusi langsung dengan stdlib Python dapat memenuhi permintaan pengguna.",
        current_strategy: str = "direct_synthesis",
        model_backend: str = "local-deterministic-v4",
        priority: float = 10.0,
        checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            task_id = f"task_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            epoch = self.current_lease_epoch()
            self._conn.execute(
                """
                INSERT INTO tasks(
                    task_id, conversation_id, parent_task_id, kind, status, title_id,
                    user_request, normalized_goal, constraints_json, acceptance_criteria_json,
                    active_hypothesis, current_strategy, model_backend, lease_owner, lease_epoch,
                    lease_expires_at, attempt_count, stagnation_score, artifacts_json,
                    verification_summary_json, resume_condition, next_action, error_summary,
                    checkpoint_json, priority, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?, ?, ?, ?, '', ?, '', 0, 0.0, '[]', '{}', '', 'mulai_eksekusi', '', ?, ?, ?, ?)
                """,
                (
                    task_id,
                    conversation_id,
                    parent_task_id,
                    kind,
                    title_id,
                    user_request,
                    normalized_goal,
                    json.dumps(constraints or [], ensure_ascii=False),
                    json.dumps(acceptance_criteria or ["Perintah berjalan dengan exit code 0", "Output sesuai permintaan"], ensure_ascii=False),
                    active_hypothesis,
                    current_strategy,
                    model_backend,
                    epoch,
                    json.dumps(checkpoint or {"stage": "queued"}, ensure_ascii=False),
                    float(priority),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return self.get_task(task_id)  # type: ignore[return-value]

    def _row_to_task(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": SCHEMA_TASK,
            "task_id": row["task_id"],
            "conversation_id": row["conversation_id"],
            "parent_task_id": row["parent_task_id"],
            "kind": row["kind"],
            "status": row["status"],
            "title_id": row["title_id"],
            "user_request": row["user_request"],
            "normalized_goal": row["normalized_goal"],
            "constraints": json.loads(row["constraints_json"] or "[]"),
            "acceptance_criteria": json.loads(row["acceptance_criteria_json"] or "[]"),
            "active_hypothesis": row["active_hypothesis"],
            "current_strategy": row["current_strategy"],
            "model_backend": row["model_backend"],
            "lease": {
                "owner": row["lease_owner"],
                "epoch": row["lease_epoch"],
                "expires_at": row["lease_expires_at"],
            },
            "attempt_count": row["attempt_count"],
            "stagnation_score": row["stagnation_score"],
            "artifacts": json.loads(row["artifacts_json"] or "[]"),
            "verification_summary": json.loads(row["verification_summary_json"] or "{}"),
            "resume_condition": row["resume_condition"],
            "next_action": row["next_action"],
            "error_summary": row["error_summary"],
            "checkpoint": json.loads(row["checkpoint_json"] or "{}"),
            "priority": row["priority"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(row) if row else None

    def list_tasks(self, conversation_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            if conversation_id:
                rows = self._conn.execute(
                    "SELECT * FROM tasks WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
                    (conversation_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def get_latest_task(self, conversation_id: str = "conv_utama", include_completed: bool = True) -> dict[str, Any] | None:
        with self._lock:
            if include_completed:
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE conversation_id = ? ORDER BY updated_at DESC, rowid DESC LIMIT 1",
                    (conversation_id,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM tasks WHERE conversation_id = ? AND status NOT IN ('COMPLETED', 'CANCELLED') ORDER BY updated_at DESC, rowid DESC LIMIT 1",
                    (conversation_id,),
                ).fetchone()
            return self._row_to_task(row) if row else None

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        active_hypothesis: str | None = None,
        current_strategy: str | None = None,
        model_backend: str | None = None,
        attempt_count: int | None = None,
        stagnation_score: float | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        verification_summary: dict[str, Any] | None = None,
        resume_condition: str | None = None,
        next_action: str | None = None,
        error_summary: str | None = None,
        checkpoint: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        normalized_goal: str | None = None,
        lease_epoch: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            current = self.get_task(task_id)
            if not current:
                raise KeyError(f"Task tidak ditemukan: {task_id}")

            # Verify lease epoch fencing if provided
            if lease_epoch is not None and lease_epoch < current["lease"]["epoch"]:
                raise StaleLeaseError(
                    f"Fenced epoch basi pada {task_id}: diberikan {lease_epoch}, saat ini {current['lease']['epoch']}"
                )

            new_status = status or current["status"]
            if new_status != current["status"]:
                if new_status not in TASK_STATES:
                    raise ValueError(f"Status tugas tidak valid: {new_status}")
                allowed = ALLOWED_TASK_TRANSITIONS.get(current["status"], set())
                if new_status not in allowed:
                    raise ValueError(f"Transisi status ilegal: {current['status']} -> {new_status}")

            now = utc_now_iso()
            merged_checkpoint = current["checkpoint"]
            if checkpoint is not None:
                merged_checkpoint.update(checkpoint)

            epoch_val = max(current["lease"]["epoch"], lease_epoch or self.current_lease_epoch())

            self._conn.execute(
                """
                UPDATE tasks SET
                    status = ?,
                    active_hypothesis = ?,
                    current_strategy = ?,
                    model_backend = ?,
                    lease_epoch = ?,
                    attempt_count = ?,
                    stagnation_score = ?,
                    artifacts_json = ?,
                    verification_summary_json = ?,
                    resume_condition = ?,
                    next_action = ?,
                    error_summary = ?,
                    checkpoint_json = ?,
                    constraints_json = ?,
                    acceptance_criteria_json = ?,
                    normalized_goal = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    new_status,
                    active_hypothesis if active_hypothesis is not None else current["active_hypothesis"],
                    current_strategy if current_strategy is not None else current["current_strategy"],
                    model_backend if model_backend is not None else current["model_backend"],
                    epoch_val,
                    attempt_count if attempt_count is not None else current["attempt_count"],
                    stagnation_score if stagnation_score is not None else current["stagnation_score"],
                    json.dumps(artifacts if artifacts is not None else current["artifacts"], ensure_ascii=False),
                    json.dumps(
                        verification_summary if verification_summary is not None else current["verification_summary"],
                        ensure_ascii=False,
                    ),
                    resume_condition if resume_condition is not None else current["resume_condition"],
                    next_action if next_action is not None else current["next_action"],
                    error_summary if error_summary is not None else current["error_summary"],
                    json.dumps(merged_checkpoint, ensure_ascii=False),
                    json.dumps(constraints if constraints is not None else current["constraints"], ensure_ascii=False),
                    json.dumps(
                        acceptance_criteria if acceptance_criteria is not None else current["acceptance_criteria"],
                        ensure_ascii=False,
                    ),
                    normalized_goal if normalized_goal is not None else current["normalized_goal"],
                    now,
                    task_id,
                ),
            )
            self._conn.commit()
            return self.get_task(task_id)  # type: ignore[return-value]

    def recover_interrupted_tasks(self) -> list[dict[str, Any]]:
        """Mark crashed ACTIVE/VERIFYING/INTEGRATING tasks as PAUSED with checkpoint recovery info."""
        recovered = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status IN ('ACTIVE', 'VERIFYING', 'INTEGRATING')"
            ).fetchall()
            for r in rows:
                t = self._row_to_task(r)
                updated = self.update_task(
                    t["task_id"],
                    status="PAUSED",
                    resume_condition="Dapat dilanjutkan dari checkpoint terakhir setelah restart.",
                    next_action="lanjutkan_dari_checkpoint",
                    checkpoint={"recovered_from_status": t["status"], "recovered_at": utc_now_iso()},
                )
                recovered.append(updated)
        return recovered

    # --- Problem IR ---
    def save_problem_ir(self, task_id: str, ir_data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            ir_id = ir_data.get("ir_id") or f"ir_{task_id}"
            now = utc_now_iso()
            payload = dict(ir_data)
            payload["schema"] = SCHEMA_PROBLEM_IR
            payload["ir_id"] = ir_id
            payload["task_id"] = task_id
            self._conn.execute(
                "INSERT OR REPLACE INTO problem_irs(ir_id, task_id, schema_json, created_at) VALUES (?, ?, ?, ?)",
                (ir_id, task_id, json.dumps(payload, ensure_ascii=False), now),
            )
            self._conn.commit()
            return payload

    def get_problem_ir(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT schema_json FROM problem_irs WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if not row or not row["schema_json"]:
                return None
            try:
                return json.loads(row["schema_json"])
            except Exception:
                return None

    # --- Activity Events & Story Projection ---
    def emit_event(
        self,
        *,
        conversation_id: str = "conv_utama",
        task_id: str = "system",
        kind: str,
        status: str = "ACTIVE",
        actor: str = "ace_controller",
        model_backend: str = "local-deterministic-v4",
        summary_code: str,
        technical_detail: dict[str, Any] | None = None,
        artifact_refs: list[str] | None = None,
        verification_passed: bool | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            event_id = f"evt_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            raw_event = {
                "schema": SCHEMA_ACTIVITY,
                "event_id": event_id,
                "timestamp": now,
                "conversation_id": conversation_id,
                "task_id": task_id,
                "kind": kind,
                "status": status,
                "actor": actor,
                "model_backend": model_backend,
                "summary_code": summary_code,
                "technical_detail": technical_detail or {},
                "artifact_refs": artifact_refs or [],
                "verification_passed": verification_passed,
            }
            projection = project_event_to_story(raw_event)
            story_text = projection["story_text"]
            avatar_state = projection["avatar_state"]

            cur = self._conn.execute(
                """
                INSERT INTO events(
                    event_id, schema, timestamp, conversation_id, task_id, kind, status,
                    actor, model_backend, summary_code, technical_detail_json,
                    artifact_refs_json, verification_passed, story_text, avatar_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    SCHEMA_ACTIVITY,
                    now,
                    conversation_id,
                    task_id,
                    kind,
                    status,
                    actor,
                    model_backend,
                    summary_code,
                    json.dumps(technical_detail or {}, ensure_ascii=False),
                    json.dumps(artifact_refs or [], ensure_ascii=False),
                    None if verification_passed is None else (1 if verification_passed else 0),
                    story_text,
                    avatar_state,
                ),
            )
            seq = cur.lastrowid
            if kind == "heartbeat":
                self.set_meta("last_heartbeat_at", now)
            self._conn.commit()
            raw_event["sequence"] = seq
            raw_event["story_text"] = story_text
            raw_event["avatar_state"] = avatar_state
            return raw_event

    def list_events(
        self,
        *,
        after_sequence: int = 0,
        conversation_id: str | None = None,
        include_heartbeats: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT * FROM events WHERE sequence > ?"
            params: list[Any] = [after_sequence]
            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)
            if not include_heartbeats:
                query += " AND kind != 'heartbeat'"
            query += " ORDER BY sequence ASC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                vp = r["verification_passed"]
                result.append({
                    "schema": r["schema"],
                    "sequence": r["sequence"],
                    "event_id": r["event_id"],
                    "timestamp": r["timestamp"],
                    "conversation_id": r["conversation_id"],
                    "task_id": r["task_id"],
                    "kind": r["kind"],
                    "status": r["status"],
                    "actor": r["actor"],
                    "model_backend": r["model_backend"],
                    "summary_code": r["summary_code"],
                    "technical_detail": json.loads(r["technical_detail_json"] or "{}"),
                    "artifact_refs": json.loads(r["artifact_refs_json"] or "[]"),
                    "verification_passed": None if vp is None else bool(vp),
                    "story_text": r["story_text"],
                    "avatar_state": r["avatar_state"],
                })
            return result

    # --- Receipts ---
    def record_receipt(
        self,
        *,
        task_id: str,
        action_kind: str,
        input_data: str | bytes,
        output_data: str | bytes,
        command_or_operation: str,
        exit_code: int,
        stdout_text: str = "",
        stderr_text: str = "",
        artifacts_created: list[str] | None = None,
        verified_by: str = "independent_verifier",
        passed: bool,
    ) -> dict[str, Any]:
        with self._lock:
            in_bytes = input_data.encode("utf-8") if isinstance(input_data, str) else input_data
            out_bytes = output_data.encode("utf-8") if isinstance(output_data, str) else output_data
            receipt_id = f"rcpt_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            in_hash = f"sha256:{hashlib.sha256(in_bytes).hexdigest()}"
            out_hash = f"sha256:{hashlib.sha256(out_bytes).hexdigest()}"
            stdout_dig = f"sha256:{hashlib.sha256(stdout_text.encode('utf-8')).hexdigest()}"
            stderr_dig = f"sha256:{hashlib.sha256(stderr_text.encode('utf-8')).hexdigest()}"
            self._conn.execute(
                """
                INSERT INTO receipts(
                    receipt_id, task_id, action_kind, input_hash, output_hash,
                    command_or_operation, exit_code, stdout_digest, stderr_digest,
                    artifacts_created_json, verified_by, passed, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    task_id,
                    action_kind,
                    in_hash,
                    out_hash,
                    command_or_operation,
                    int(exit_code),
                    stdout_dig,
                    stderr_dig,
                    json.dumps(artifacts_created or [], ensure_ascii=False),
                    verified_by,
                    1 if passed else 0,
                    now,
                ),
            )
            self._conn.commit()
            return {
                "schema": SCHEMA_RECEIPT,
                "receipt_id": receipt_id,
                "task_id": task_id,
                "action_kind": action_kind,
                "input_hash": in_hash,
                "output_hash": out_hash,
                "command_or_operation": command_or_operation,
                "exit_code": int(exit_code),
                "stdout_digest": stdout_dig,
                "stderr_digest": stderr_dig,
                "artifacts_created": artifacts_created or [],
                "verified_by": verified_by,
                "passed": bool(passed),
                "timestamp": now,
            }

    def list_receipts(self, task_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if task_id:
                rows = self._conn.execute(
                    "SELECT * FROM receipts WHERE task_id = ? ORDER BY timestamp ASC",
                    (task_id,),
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM receipts ORDER BY timestamp DESC LIMIT 50").fetchall()
            return [
                {
                    "schema": SCHEMA_RECEIPT,
                    "receipt_id": r["receipt_id"],
                    "task_id": r["task_id"],
                    "action_kind": r["action_kind"],
                    "input_hash": r["input_hash"],
                    "output_hash": r["output_hash"],
                    "command_or_operation": r["command_or_operation"],
                    "exit_code": r["exit_code"],
                    "stdout_digest": r["stdout_digest"],
                    "stderr_digest": r["stderr_digest"],
                    "artifacts_created": json.loads(r["artifacts_created_json"] or "[]"),
                    "verified_by": r["verified_by"],
                    "passed": bool(r["passed"]),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

    # --- Gaps & Capability Frontier ---
    def record_gap(
        self,
        *,
        source_task_id: str,
        error_type: str,
        missing_skill_or_tool: str,
        description_id: str,
        reproduction_ref: str = "",
        resolution_strategy: str = "micro_experiment",
    ) -> tuple[dict[str, Any], bool]:
        """Record or deduplicate an ace.gap.v1 item. Returns (gap_dict, created_new)."""
        fingerprint = hashlib.sha256(f"{error_type.strip().lower()}::{missing_skill_or_tool.strip().lower()}".encode("utf-8")).hexdigest()[:20]
        now = utc_now_iso()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM gaps WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if existing:
                new_count = int(existing["occurrence_count"]) + 1
                self._conn.execute(
                    "UPDATE gaps SET occurrence_count = ?, updated_at = ?, source_task_id = ? WHERE fingerprint = ?",
                    (new_count, now, source_task_id, fingerprint),
                )
                self._conn.commit()
                row = self._conn.execute("SELECT * FROM gaps WHERE fingerprint = ?", (fingerprint,)).fetchone()
                return self._row_to_gap(row), False
            gap_id = f"gap_{fingerprint[:10]}"
            self._conn.execute(
                """
                INSERT INTO gaps(
                    gap_id, fingerprint, source_task_id, error_type, missing_skill_or_tool,
                    description_id, reproduction_ref, resolution_strategy, status,
                    linked_learning_task_id, occurrence_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', '', 1, ?, ?)
                """,
                (
                    gap_id,
                    fingerprint,
                    source_task_id,
                    error_type,
                    missing_skill_or_tool,
                    description_id,
                    reproduction_ref,
                    resolution_strategy,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM gaps WHERE gap_id = ?", (gap_id,)).fetchone()
            return self._row_to_gap(row), True

    def _row_to_gap(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": SCHEMA_GAP,
            "gap_id": row["gap_id"],
            "fingerprint": row["fingerprint"],
            "source_task_id": row["source_task_id"],
            "error_type": row["error_type"],
            "missing_skill_or_tool": row["missing_skill_or_tool"],
            "description_id": row["description_id"],
            "reproduction_ref": row["reproduction_ref"],
            "resolution_strategy": row["resolution_strategy"],
            "status": row["status"],
            "linked_learning_task_id": row["linked_learning_task_id"],
            "occurrence_count": row["occurrence_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def update_gap(
        self,
        gap_id: str,
        *,
        status: str | None = None,
        linked_learning_task_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM gaps WHERE gap_id = ?", (gap_id,)).fetchone()
            if not row:
                raise KeyError(f"Gap tidak ditemukan: {gap_id}")
            now = utc_now_iso()
            self._conn.execute(
                "UPDATE gaps SET status = ?, linked_learning_task_id = ?, updated_at = ? WHERE gap_id = ?",
                (
                    status if status is not None else row["status"],
                    linked_learning_task_id if linked_learning_task_id is not None else row["linked_learning_task_id"],
                    now,
                    gap_id,
                ),
            )
            self._conn.commit()
            updated = self._conn.execute("SELECT * FROM gaps WHERE gap_id = ?", (gap_id,)).fetchone()
            return self._row_to_gap(updated)

    def list_gaps(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM gaps WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM gaps ORDER BY updated_at DESC").fetchall()
            return [self._row_to_gap(r) for r in rows]

    def set_frontier_capability(
        self,
        *,
        capability_id: str,
        name_id: str,
        category: str = "general",
        status: str,
        evidence_ref: str = "",
        failure_reason: str = "",
    ) -> dict[str, Any]:
        if status not in FRONTIER_STATUSES:
            raise ValueError(f"Status frontier tidak valid: {status}")
        if status == "KNOWN_AND_TESTED" and not evidence_ref.strip():
            raise ValueError("KNOWN_AND_TESTED membutuhkan evidence_ref terverifikasi (AUTO04)")
        now = utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO frontier(capability_id, name_id, category, status, evidence_ref, failure_reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capability_id) DO UPDATE SET
                    name_id = excluded.name_id,
                    category = excluded.category,
                    status = excluded.status,
                    evidence_ref = excluded.evidence_ref,
                    failure_reason = excluded.failure_reason,
                    updated_at = excluded.updated_at
                """,
                (capability_id, name_id, category, status, evidence_ref, failure_reason, now),
            )
            self._conn.commit()
            return {
                "schema": SCHEMA_FRONTIER,
                "capability_id": capability_id,
                "name_id": name_id,
                "category": category,
                "status": status,
                "evidence_ref": evidence_ref,
                "failure_reason": failure_reason,
                "updated_at": now,
            }

    def list_frontier(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM frontier ORDER BY capability_id ASC").fetchall()
            return [
                {
                    "schema": SCHEMA_FRONTIER,
                    "capability_id": r["capability_id"],
                    "name_id": r["name_id"],
                    "category": r["category"],
                    "status": r["status"],
                    "evidence_ref": r["evidence_ref"],
                    "failure_reason": r["failure_reason"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    # --- Skills & Learning Experiences ---
    def save_learning_experience(
        self,
        *,
        task_id: str,
        gap_id: str = "",
        failure_signature: str,
        root_cause: str,
        strategy_before: str,
        strategy_after: str,
        delta_change: str,
        extracted_rule: str,
        applicable_when: list[str],
        not_applicable_when: list[str],
        verification_evidence: dict[str, Any],
        reusable_skill_candidate: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            exp_id = f"exp_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO learning_experiences(
                    experience_id, task_id, gap_id, failure_signature, root_cause,
                    strategy_before, strategy_after, delta_change, extracted_rule,
                    applicable_when_json, not_applicable_when_json, verification_evidence_json,
                    reusable_skill_candidate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp_id,
                    task_id,
                    gap_id,
                    failure_signature,
                    root_cause,
                    strategy_before,
                    strategy_after,
                    delta_change,
                    extracted_rule,
                    json.dumps(applicable_when, ensure_ascii=False),
                    json.dumps(not_applicable_when, ensure_ascii=False),
                    json.dumps(verification_evidence, ensure_ascii=False),
                    1 if reusable_skill_candidate else 0,
                    now,
                ),
            )
            self._conn.commit()
            return {
                "schema": SCHEMA_LEARNING_EXPERIENCE,
                "experience_id": exp_id,
                "task_id": task_id,
                "gap_id": gap_id,
                "failure_signature": failure_signature,
                "root_cause": root_cause,
                "strategy_before": strategy_before,
                "strategy_after": strategy_after,
                "delta_change": delta_change,
                "extracted_rule": extracted_rule,
                "applicable_when": applicable_when,
                "not_applicable_when": not_applicable_when,
                "verification_evidence": verification_evidence,
                "reusable_skill_candidate": reusable_skill_candidate,
                "created_at": now,
            }

    def save_skill(
        self,
        *,
        skill_id: str | None = None,
        name: str,
        domain: str,
        preconditions: list[str],
        boundary_limitations: list[str],
        procedure_steps: list[str],
        verification_template: dict[str, Any],
        source_task_ids: list[str],
    ) -> dict[str, Any]:
        with self._lock:
            sid = skill_id or f"skill_{hashlib.sha256(name.encode('utf-8')).hexdigest()[:10]}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO skills(
                    skill_id, name, domain, preconditions_json, boundary_limitations_json,
                    procedure_steps_json, verification_template_json, source_task_ids_json,
                    success_count, failure_count, negative_transfer_count, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 'ACTIVE', ?, ?)
                ON CONFLICT(skill_id) DO UPDATE SET
                    name = excluded.name,
                    domain = excluded.domain,
                    preconditions_json = excluded.preconditions_json,
                    boundary_limitations_json = excluded.boundary_limitations_json,
                    procedure_steps_json = excluded.procedure_steps_json,
                    verification_template_json = excluded.verification_template_json,
                    source_task_ids_json = excluded.source_task_ids_json,
                    success_count = skills.success_count + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    sid,
                    name,
                    domain,
                    json.dumps(preconditions, ensure_ascii=False),
                    json.dumps(boundary_limitations, ensure_ascii=False),
                    json.dumps(procedure_steps, ensure_ascii=False),
                    json.dumps(verification_template, ensure_ascii=False),
                    json.dumps(source_task_ids, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return self.get_skill(sid)  # type: ignore[return-value]

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM skills WHERE skill_id = ?", (skill_id,)).fetchone()
            if not r:
                return None
            return self._row_to_skill(r)

    def _row_to_skill(self, r: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": SCHEMA_SKILL,
            "skill_id": r["skill_id"],
            "name": r["name"],
            "domain": r["domain"],
            "preconditions": json.loads(r["preconditions_json"] or "[]"),
            "boundary_limitations": json.loads(r["boundary_limitations_json"] or "[]"),
            "procedure_steps": json.loads(r["procedure_steps_json"] or "[]"),
            "verification_template": json.loads(r["verification_template_json"] or "{}"),
            "source_task_ids": json.loads(r["source_task_ids_json"] or "[]"),
            "success_count": r["success_count"],
            "failure_count": r["failure_count"],
            "negative_transfer_count": r["negative_transfer_count"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    def record_skill_outcome(self, skill_id: str, *, success: bool, negative_transfer: bool = False) -> dict[str, Any]:
        with self._lock:
            skill = self.get_skill(skill_id)
            if not skill:
                raise KeyError(f"Skill tidak ditemukan: {skill_id}")
            succ = int(skill["success_count"]) + (1 if success else 0)
            fail = int(skill["failure_count"]) + (0 if success else 1)
            neg = int(skill["negative_transfer_count"]) + (1 if negative_transfer else 0)
            status = skill["status"]
            if neg >= 2 or (fail >= 3 and fail > succ):
                status = "SUSPENDED"
            now = utc_now_iso()
            self._conn.execute(
                """
                UPDATE skills SET
                    success_count = ?,
                    failure_count = ?,
                    negative_transfer_count = ?,
                    status = ?,
                    updated_at = ?
                WHERE skill_id = ?
                """,
                (succ, fail, neg, status, now, skill_id),
            )
            self._conn.commit()
            return self.get_skill(skill_id)  # type: ignore[return-value]

    def list_skills(self, active_only: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            if active_only:
                rows = self._conn.execute("SELECT * FROM skills WHERE status = 'ACTIVE' ORDER BY updated_at DESC").fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM skills ORDER BY updated_at DESC").fetchall()
            return [self._row_to_skill(r) for r in rows]

    # --- Attempts (Anti-Stagnation Fingerprinting) ---
    def record_attempt(
        self,
        *,
        task_id: str,
        patch_hash: str,
        semantic_sig: str,
        error_class: str,
        strategy: str,
        metric_score: float = 0.0,
    ) -> dict[str, Any]:
        with self._lock:
            att_id = f"att_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO attempts(attempt_id, task_id, patch_hash, semantic_sig, error_class, strategy, metric_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (att_id, task_id, patch_hash, semantic_sig, error_class, strategy, float(metric_score), now),
            )
            self._conn.commit()
            return {
                "attempt_id": att_id,
                "task_id": task_id,
                "patch_hash": patch_hash,
                "semantic_sig": semantic_sig,
                "error_class": error_class,
                "strategy": strategy,
                "metric_score": float(metric_score),
                "created_at": now,
            }

    def list_attempts(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM attempts WHERE task_id = ? ORDER BY created_at ASC, rowid ASC",
                (task_id,),
            ).fetchall()
            return [
                {
                    "attempt_id": r["attempt_id"],
                    "task_id": r["task_id"],
                    "patch_hash": r["patch_hash"],
                    "semantic_sig": r["semantic_sig"],
                    "error_class": r["error_class"],
                    "strategy": r["strategy"],
                    "metric_score": r["metric_score"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    # --- Work Orders ---
    def create_work_order(
        self,
        *,
        parent_task_id: str,
        mission_id: str = "",
        idempotency_key: str,
        worker_kind: str = "coding_worker",
        objective: str,
        base_snapshot_hash: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Create or deduplicate an ace.work_order.v1 by idempotency_key."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM work_orders WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return self._row_to_work_order(existing), False
            wo_id = f"wo_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO work_orders(
                    work_order_id, parent_task_id, mission_id, idempotency_key,
                    worker_kind, objective, base_snapshot_hash, payload_json,
                    status, claimed_by, result_json, verification_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', '', '{}', 'UNVERIFIED', ?, ?)
                """,
                (
                    wo_id,
                    parent_task_id,
                    mission_id,
                    idempotency_key,
                    worker_kind,
                    objective,
                    base_snapshot_hash,
                    json.dumps(payload or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM work_orders WHERE work_order_id = ?", (wo_id,)).fetchone()
            return self._row_to_work_order(row), True

    def _row_to_work_order(self, r: sqlite3.Row) -> dict[str, Any]:
        return {
            "schema": SCHEMA_WORK_ORDER,
            "work_order_id": r["work_order_id"],
            "parent_task_id": r["parent_task_id"],
            "mission_id": r["mission_id"],
            "idempotency_key": r["idempotency_key"],
            "worker_kind": r["worker_kind"],
            "objective": r["objective"],
            "base_snapshot_hash": r["base_snapshot_hash"],
            "payload": json.loads(r["payload_json"] or "{}"),
            "status": r["status"],
            "claimed_by": r["claimed_by"],
            "result": json.loads(r["result_json"] or "{}"),
            "verification_status": r["verification_status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }

    def get_work_order(self, work_order_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,)).fetchone()
            return self._row_to_work_order(row) if row else None

    def list_work_orders(self, parent_task_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if parent_task_id:
                rows = self._conn.execute(
                    "SELECT * FROM work_orders WHERE parent_task_id = ? ORDER BY created_at DESC",
                    (parent_task_id,),
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM work_orders ORDER BY created_at DESC LIMIT 50").fetchall()
            return [self._row_to_work_order(r) for r in rows]

    def update_work_order(
        self,
        work_order_id: str,
        *,
        status: str | None = None,
        claimed_by: str | None = None,
        result: dict[str, Any] | None = None,
        verification_status: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            wo = self.get_work_order(work_order_id)
            if not wo:
                raise KeyError(f"Work order tidak ditemukan: {work_order_id}")
            now = utc_now_iso()
            self._conn.execute(
                """
                UPDATE work_orders SET
                    status = ?,
                    claimed_by = ?,
                    result_json = ?,
                    verification_status = ?,
                    updated_at = ?
                WHERE work_order_id = ?
                """,
                (
                    status if status is not None else wo["status"],
                    claimed_by if claimed_by is not None else wo["claimed_by"],
                    json.dumps(result if result is not None else wo["result"], ensure_ascii=False),
                    verification_status if verification_status is not None else wo["verification_status"],
                    now,
                    work_order_id,
                ),
            )
            self._conn.commit()
            return self.get_work_order(work_order_id)  # type: ignore[return-value]

    # --- F01-F24 Execution Contract Deliverables & OAIE Experiments ---
    def _row_to_deliverable(self, r: sqlite3.Row) -> dict[str, Any]:
        return {
            "deliverable_id": r["deliverable_id"],
            "title_id": r["title_id"],
            "status": r["status"],
            "remaining_work": r["remaining_work"],
            "dependencies": json.loads(r["dependencies_json"] or "[]"),
            "next_action": r["next_action"],
            "artifacts": json.loads(r["artifacts_json"] or "[]"),
            "source_version": r["source_version"],
            "checks_executed": json.loads(r["checks_executed_json"] or "[]"),
            "blockers": r["blockers"],
            "resume_condition": r["resume_condition"],
            "updated_at": r["updated_at"],
        }

    def get_deliverable(self, deliverable_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM deliverables WHERE deliverable_id = ?",
                (deliverable_id,),
            ).fetchone()
            return self._row_to_deliverable(row) if row else None

    def list_deliverables(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM deliverables ORDER BY deliverable_id ASC").fetchall()
            return [self._row_to_deliverable(r) for r in rows]

    def update_deliverable(
        self,
        deliverable_id: str,
        *,
        status: str,
        remaining_work: str = "",
        next_action: str = "tidak_ada",
        artifacts: list[str] | None = None,
        source_version: str | None = None,
        checks_executed: list[str] | None = None,
        blockers: str = "",
        resume_condition: str = "",
    ) -> dict[str, Any]:
        if status not in DELIVERABLE_STATUSES:
            raise ValueError(f"Status deliverable tidak valid: {status}")
        if status == "PASS" and not checks_executed:
            raise ValueError(f"Deliverable {deliverable_id} tidak boleh ditandai PASS tanpa bukti checks_executed")
        with self._lock:
            cur = self.get_deliverable(deliverable_id)
            if not cur:
                raise KeyError(f"Deliverable tidak dikenal: {deliverable_id}")
            now = utc_now_iso()
            self._conn.execute(
                """
                UPDATE deliverables SET
                    status = ?,
                    remaining_work = ?,
                    next_action = ?,
                    artifacts_json = ?,
                    source_version = ?,
                    checks_executed_json = ?,
                    blockers = ?,
                    resume_condition = ?,
                    updated_at = ?
                WHERE deliverable_id = ?
                """,
                (
                    status,
                    remaining_work,
                    next_action,
                    json.dumps(artifacts if artifacts is not None else cur["artifacts"], ensure_ascii=False),
                    source_version if source_version is not None else self.get_meta("release_version", RELEASE_VERSION),
                    json.dumps(checks_executed if checks_executed is not None else cur["checks_executed"], ensure_ascii=False),
                    blockers,
                    resume_condition,
                    now,
                    deliverable_id,
                ),
            )
            self._conn.commit()
            return self.get_deliverable(deliverable_id)  # type: ignore[return-value]

    def export_deliverables_snapshot(self, target_path: Path | None = None) -> dict[str, Any]:
        items = self.list_deliverables()
        counts: dict[str, int] = {}
        for item in items:
            st = item["status"]
            counts[st] = counts.get(st, 0) + 1
        snapshot = {
            "schema": "ace.execution_contract.f01_f24.v1",
            "release_version": self.get_meta("release_version", RELEASE_VERSION),
            "workspace": str(self.workspace),
            "updated_at": utc_now_iso(),
            "counts": counts,
            "all_passed": all(i["status"] == "PASS" for i in items),
            "deliverables": items,
        }
        out_file = target_path or (self.workspace / "f01_f24_status.json")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        return snapshot

    def save_experiment(
        self,
        *,
        title_id: str,
        hypothesis: str,
        decision: str,
        metrics: dict[str, Any],
        retention_passed: bool,
        transfer_passed: bool,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            exp_id = f"oaie_exp_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            now = utc_now_iso()
            self._conn.execute(
                """
                INSERT INTO experiments(
                    experiment_id, title_id, hypothesis, decision,
                    metrics_json, retention_passed, transfer_passed, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp_id,
                    title_id,
                    hypothesis,
                    decision,
                    json.dumps(metrics, ensure_ascii=False),
                    1 if retention_passed else 0,
                    1 if transfer_passed else 0,
                    json.dumps(report, ensure_ascii=False),
                    now,
                ),
            )
            self._conn.commit()
            return {
                "experiment_id": exp_id,
                "title_id": title_id,
                "hypothesis": hypothesis,
                "decision": decision,
                "metrics": metrics,
                "retention_passed": retention_passed,
                "transfer_passed": transfer_passed,
                "report": report,
                "created_at": now,
            }

    def list_experiments(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
            return [
                {
                    "experiment_id": r["experiment_id"],
                    "title_id": r["title_id"],
                    "hypothesis": r["hypothesis"],
                    "decision": r["decision"],
                    "metrics": json.loads(r["metrics_json"] or "{}"),
                    "retention_passed": bool(r["retention_passed"]),
                    "transfer_passed": bool(r["transfer_passed"]),
                    "report": json.loads(r["report_json"] or "{}"),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

