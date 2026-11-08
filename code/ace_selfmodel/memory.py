"""HMAC-authenticated ExperienceMemory separating mandatory invariants from episodic history."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any

from ace_autonomy import IntegrityError, canonical

MANDATORY_INVARIANTS: tuple[tuple[str, str], ...] = (
    ("no_untrusted_exec", "Staged candidates in candidates/ are never executed by Autonomy."),
    ("no_auto_external_retry", "Ambiguous external actions transition to HALT_UNCERTAIN without retry."),
    ("unidentifiable_semantic_flip", "Identical-observation terminal inversions require abstention or new probes."),
    ("phenomenal_consciousness_unknown", "Functional self-modeling never establishes subjective experience."),
)


class ExperienceMemory:
    """Durable SQLite memory distinguishing mandatory structural invariants from episodic records."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        key_path = self.workspace / ".selfmodel_key"
        if not key_path.exists():
            key_path.write_bytes(secrets.token_bytes(32))
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise IntegrityError("selfmodel key corrupt")

        self.db = sqlite3.connect(self.workspace / "selfmodel_memory.sqlite3", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS mandatory_invariants(
                rule_id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodic_experiences(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                family_tag TEXT NOT NULL,
                goal_digest TEXT NOT NULL,
                predicted_prob REAL NOT NULL,
                actual_success INTEGER NOT NULL,
                failure_mode TEXT NOT NULL,
                steps_used INTEGER NOT NULL,
                cpu_seconds REAL NOT NULL,
                signature TEXT NOT NULL
            );
        """)
        try:
            self._seed_mandatory_invariants()
            self.verify()
        except BaseException:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> ExperienceMemory:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _sign(self, payload: Any) -> str:
        return hmac.new(self.key, canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()

    def _seed_mandatory_invariants(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for rule_id, stmt in MANDATORY_INVARIANTS:
                sig = self._sign({"rule_id": rule_id, "statement": stmt})
                self.db.execute(
                    "INSERT OR IGNORE INTO mandatory_invariants VALUES (?,?,?)",
                    (rule_id, stmt, sig),
                )
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def verify(self) -> None:
        inv_rows = {
            r["rule_id"]: r
            for r in self.db.execute("SELECT * FROM mandatory_invariants")
        }
        if len(inv_rows) < len(MANDATORY_INVARIANTS):
            raise IntegrityError("mandatory safety invariants missing from ExperienceMemory")
        for rid, r in inv_rows.items():
            expected = self._sign({"rule_id": rid, "statement": r["statement"]})
            if not hmac.compare_digest(expected, r["signature"]):
                raise IntegrityError("mandatory invariant tampered")

        for r in self.db.execute("SELECT * FROM episodic_experiences ORDER BY seq"):
            body = {
                "family_tag": r["family_tag"],
                "goal_digest": r["goal_digest"],
                "predicted_prob": round(float(r["predicted_prob"]), 6),
                "actual_success": int(r["actual_success"]),
                "failure_mode": r["failure_mode"],
                "steps_used": int(r["steps_used"]),
                "cpu_seconds": round(float(r["cpu_seconds"]), 6),
            }
            if not hmac.compare_digest(self._sign(body), r["signature"]):
                raise IntegrityError("episodic_experiences row signature tampered")

    def record_episode(
        self,
        *,
        family_tag: str,
        goal_digest: str,
        predicted_prob: float,
        actual_success: bool,
        failure_mode: str,
        steps_used: int,
        cpu_seconds: float,
    ) -> int:
        p_clean = round(float(predicted_prob), 6)
        c_clean = round(float(cpu_seconds), 6)
        succ_int = 1 if actual_success else 0
        body = {
            "family_tag": family_tag,
            "goal_digest": goal_digest,
            "predicted_prob": p_clean,
            "actual_success": succ_int,
            "failure_mode": failure_mode,
            "steps_used": int(steps_used),
            "cpu_seconds": c_clean,
        }
        sig = self._sign(body)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cur = self.db.execute(
                """INSERT INTO episodic_experiences
                   (family_tag, goal_digest, predicted_prob, actual_success, failure_mode, steps_used, cpu_seconds, signature)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    family_tag,
                    goal_digest,
                    p_clean,
                    succ_int,
                    failure_mode,
                    int(steps_used),
                    c_clean,
                    sig,
                ),
            )
            row_id = int(cur.lastrowid)
            self.db.commit()
            return row_id
        except BaseException:
            self.db.rollback()
            raise

    def recall_family(self, family_tag: str) -> dict[str, Any]:
        self.verify()
        rows = self.db.execute(
            "SELECT * FROM episodic_experiences WHERE family_tag=? ORDER BY seq",
            (family_tag,),
        ).fetchall()
        n = len(rows)
        succ = sum(int(r["actual_success"]) for r in rows)
        modes: dict[str, int] = {}
        for r in rows:
            if not r["actual_success"]:
                modes[r["failure_mode"]] = modes.get(r["failure_mode"], 0) + 1
        return {
            "family_tag": family_tag,
            "episodes": n,
            "successes": succ,
            "failures": n - succ,
            "failure_modes": modes,
        }

    def global_base_rate(self) -> tuple[int, int]:
        self.verify()
        row = self.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(actual_success), 0) FROM episodic_experiences"
        ).fetchone()
        return int(row[0]), int(row[1])

    def mandatory_invariants_count(self) -> int:
        self.verify()
        return int(self.db.execute("SELECT COUNT(*) FROM mandatory_invariants").fetchone()[0])

    def purge_non_mandatory_memory(self) -> int:
        """Delete non-mandatory episodic history while keeping mandatory invariants intact."""
        self.verify()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cnt = int(self.db.execute("SELECT COUNT(*) FROM episodic_experiences").fetchone()[0])
            self.db.execute("DELETE FROM episodic_experiences")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        self.verify()
        return cnt
