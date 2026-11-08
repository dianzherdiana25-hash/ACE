"""SQLite-backed Mission Bus implementation with cryptographic hash chain and escalation support."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from .schema import validate_mission, MissionSchemaError


class ForbiddenFileViolationError(PermissionError):
    """Raised when an agent attempts to access or submit changes to forbidden files."""
    pass


class MissionBus:
    """Persistent, transactional Mission Bus with cryptographic hash chaining."""

    def __init__(self, db_path: Path, escalation_file: Optional[Path] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.escalation_file = Path(escalation_file) if escalation_file else self.db_path.parent / "ESCALATION.md"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    claimed_by TEXT,
                    claimed_at TEXT,
                    submitted_at TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    artifact_sha TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(mission_id) REFERENCES missions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hash_chain (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    prev_hash TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    current_hash TEXT NOT NULL
                )
            """)
            # Initialize genesis block if hash chain is empty
            cur = conn.execute("SELECT COUNT(*) FROM hash_chain")
            if cur.fetchone()[0] == 0:
                genesis_payload = json.dumps({"event": "GENESIS", "time": "2026-11-08T00:00:00Z"}, sort_keys=True)
                genesis_hash = hashlib.sha256(f"0000000000000000000000000000000000000000000000000000000000000000:{genesis_payload}".encode()).hexdigest()
                conn.execute(
                    "INSERT INTO hash_chain (prev_hash, event_type, payload_json, timestamp, current_hash) VALUES (?, ?, ?, ?, ?)",
                    ("0000000000000000000000000000000000000000000000000000000000000000", "GENESIS", genesis_payload, "2026-11-08T00:00:00Z", genesis_hash)
                )
            conn.commit()

    def _append_hash_chain(self, conn: sqlite3.Connection, event_type: str, payload: dict) -> str:
        cur = conn.execute("SELECT current_hash FROM hash_chain ORDER BY seq DESC LIMIT 1")
        row = cur.fetchone()
        prev_hash = row[0] if row else "0" * 64
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True)
        block_content = f"{prev_hash}:{event_type}:{payload_json}:{timestamp}"
        current_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()
        conn.execute(
            "INSERT INTO hash_chain (prev_hash, event_type, payload_json, timestamp, current_hash) VALUES (?, ?, ?, ?, ?)",
            (prev_hash, event_type, payload_json, timestamp, current_hash)
        )
        return current_hash

    def create_mission(
        self,
        goal: str,
        hypothesis: str,
        task_family_ids: List[str],
        inputs: List[Dict[str, str]],
        budget: Dict[str, Any],
        acceptance: Dict[str, Any],
        forbidden: List[str],
        deadline_hours: int = 24,
    ) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        deadline = (now + datetime.timedelta(hours=deadline_hours)).isoformat()
        m_id = f"mission_{hashlib.sha256(f'{goal}:{hypothesis}:{now.isoformat()}'.encode()).hexdigest()[:16]}"

        mission_doc = {
            "schema_version": "ace.mission.v1",
            "id": m_id,
            "goal": goal,
            "hypothesis": hypothesis,
            "task_family_ids": task_family_ids,
            "inputs": inputs,
            "budget": budget,
            "acceptance": acceptance,
            "forbidden": forbidden,
            "deadline": deadline,
            "status": "PENDING",
        }
        validate_mission(mission_doc)

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO missions (id, goal, hypothesis, data_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (m_id, goal, hypothesis, json.dumps(mission_doc), "PENDING", now.isoformat())
            )
            self._append_hash_chain(conn, "MISSION_CREATED", {"mission_id": m_id, "goal": goal, "hypothesis": hypothesis})
            conn.commit()

        return m_id

    def next_mission(self, agent_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT id, data_json FROM missions WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            m_id = row[0]
            mission = json.loads(row[1])
            mission["status"] = "CLAIMED"
            mission["claimed_by"] = agent_id
            mission["claimed_at"] = now

            conn.execute(
                "UPDATE missions SET status = 'CLAIMED', claimed_by = ?, claimed_at = ?, data_json = ? WHERE id = ?",
                (agent_id, now, json.dumps(mission), m_id)
            )
            self._append_hash_chain(conn, "MISSION_CLAIMED", {"mission_id": m_id, "agent_id": agent_id})
            conn.commit()
            return mission

    def submit_mission(
        self,
        mission_id: str,
        artifact_path: str,
        agent_id: str,
        decision: str = "PENDING_EVALUATION",
        provenance: str = "ADVISOR_AGENT"
    ) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT data_json, status FROM missions WHERE id = ?", (mission_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Mission '{mission_id}' not found")
            mission = json.loads(row[0])

            # Check forbidden files pattern
            for forbidden_pat in mission.get("forbidden", []):
                if forbidden_pat in artifact_path or Path(artifact_path).name == Path(forbidden_pat).name:
                    raise ForbiddenFileViolationError(
                        f"Artifact '{artifact_path}' matches forbidden pattern '{forbidden_pat}'. Access denied."
                    )

            artifact_bytes = Path(artifact_path).read_bytes()
            artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            mission["status"] = "SUBMITTED"
            mission["submitted_at"] = now
            mission["artifact_sha"] = artifact_sha
            mission["decision"] = decision
            mission["provenance"] = provenance

            conn.execute(
                "UPDATE missions SET status = 'SUBMITTED', submitted_at = ?, data_json = ? WHERE id = ?",
                (now, json.dumps(mission), mission_id)
            )
            conn.execute(
                "INSERT INTO submissions (mission_id, agent_id, artifact_path, artifact_sha, decision, provenance, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mission_id, agent_id, artifact_path, artifact_sha, decision, provenance, now)
            )
            self._append_hash_chain(conn, "MISSION_SUBMITTED", {
                "mission_id": mission_id,
                "agent_id": agent_id,
                "artifact_sha": artifact_sha,
                "decision": decision,
                "provenance": provenance
            })
            conn.commit()

            return {
                "mission_id": mission_id,
                "status": "SUBMITTED",
                "artifact_sha": artifact_sha,
                "decision": decision,
                "provenance": provenance,
                "timestamp": now
            }

    def verify_hash_chain(self) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT seq, prev_hash, event_type, payload_json, timestamp, current_hash FROM hash_chain ORDER BY seq ASC")
            rows = cur.fetchall()
            for i, row in enumerate(rows):
                seq, prev_hash, event_type, payload_json, timestamp, current_hash = row
                if i == 0:
                    continue  # Genesis
                block_content = f"{prev_hash}:{event_type}:{payload_json}:{timestamp}"
                expected_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()
                if current_hash != expected_hash:
                    return False
                if i > 0 and prev_hash != rows[i - 1]["current_hash"]:
                    return False
            return True

    def check_saturation_and_escalate(self, hypothesis: str, patch_content: str) -> Dict[str, Any]:
        patch_sha = hashlib.sha256(patch_content.encode("utf-8")).hexdigest()
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE artifact_sha = ? AND decision IN ('REJECTED', 'DUPLICATE_PATCH_SKIPPED', 'STAGNATED')",
                (patch_sha,)
            )
            rejection_count = cur.fetchone()[0]

            if rejection_count >= 3:
                # Trigger escalation
                conn.execute(
                    "UPDATE missions SET status = 'ESCALATED' WHERE hypothesis = ?",
                    (hypothesis,)
                )
                self._append_hash_chain(conn, "MISSION_ESCALATED", {
                    "hypothesis": hypothesis,
                    "patch_sha": patch_sha,
                    "rejection_count": rejection_count
                })
                conn.commit()

                # Write ESCALATION.md
                escalation_content = f"""# ESCALATION — Penjenuhan Loop Hipotesis Terdeteksi

Tanggal: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
Hipotesis: {hypothesis}
Patch SHA256: {patch_sha}
Jumlah Percobaan Gagal Berturut-turut: {rejection_count}

## Bukti Penjenuhan
Hipotesis dan patch yang sama telah diajukan {rejection_count} kali tanpa kemajuan metrik terukur. Loop otonom dihentikan dari idle tidur-bangun tanpa akhir (fail-closed) sesuai aturan W1.

## Pilihan Keputusan untuk Pemilik
1. **PILIHAN A (Ganti Representasi DSL):** Perluas tata bahasa pembelajar dengan operator komposisi graf atau urutan bertipe di luar konstanta aritmatika dasar.
2. **PILIHAN B (Relaksasi Kuota Label):** Tambahkan kuota label terarah melalui oracle query aktif.
3. **PILIHAN C (Tolak Hipotesis Secara Permanen):** Catat hipotesis ini sebagai NEGATIF permanen pada ledger dan lanjutkan ke keluarga tugas held-out berikutnya.
"""
                self.escalation_file.write_text(escalation_content, encoding="utf-8")
                return {"escalated": True, "rejection_count": rejection_count, "escalation_file": str(self.escalation_file)}

            return {"escalated": False, "rejection_count": rejection_count}

    def status(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT status, COUNT(*) FROM missions GROUP BY status")
            counts = {row[0]: row[1] for row in cur.fetchall()}
            cur = conn.execute("SELECT COUNT(*) FROM submissions")
            sub_count = cur.fetchone()[0]
            chain_valid = self.verify_hash_chain()
            return {
                "mission_counts": counts,
                "total_submissions": sub_count,
                "hash_chain_valid": chain_valid,
            }
