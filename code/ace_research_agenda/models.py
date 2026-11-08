"""Typed Data Models & HMAC-Signed Research Archive for ACE Fase 9."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any

from ace_autonomy import IntegrityError, PolicyError, canonical, digest


@dataclass(frozen=True)
class ResearchCampaignBudget:
    max_cycles: int = 5
    max_total_steps: int = 32
    max_total_cpu_s: float = 25.0

    def validate(self) -> None:
        if type(self.max_cycles) is not int or not 1 <= self.max_cycles <= 10:
            raise PolicyError("max_cycles must be an int in 1..10")
        if type(self.max_total_steps) is not int or not 1 <= self.max_total_steps <= 64:
            raise PolicyError("max_total_steps must be an int in 1..64")
        if type(self.max_total_cpu_s) not in (int, float) or not 0.1 <= float(self.max_total_cpu_s) <= 120.0:
            raise PolicyError("max_total_cpu_s must be in [0.1, 120.0]")


@dataclass(frozen=True)
class CapabilityGap:
    gap_id: str
    source_subsystem: str
    source_artifact: str
    empirical_signal: str
    severity: float
    identifiable_from_available_probes: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "source_subsystem": self.source_subsystem,
            "source_artifact": self.source_artifact,
            "empirical_signal": self.empirical_signal,
            "severity": round(self.severity, 4),
            "identifiable_from_available_probes": self.identifiable_from_available_probes,
        }


@dataclass(frozen=True)
class ResearchHypothesis:
    hypothesis_id: str
    gap_id: str
    family_tag: str
    statement: str
    falsification_criterion: str
    research_value: float
    expected_info_gain: float
    experiment_kind: str
    goal_spec: dict[str, Any]
    epistemic_context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "gap_id": self.gap_id,
            "family_tag": self.family_tag,
            "statement": self.statement,
            "falsification_criterion": self.falsification_criterion,
            "research_value": round(self.research_value, 4),
            "expected_info_gain": round(self.expected_info_gain, 4),
            "experiment_kind": self.experiment_kind,
            "goal_digest": digest(self.goal_spec),
            "epistemic_context": dict(self.epistemic_context),
        }


@dataclass(frozen=True)
class ExperimentVerdict:
    hypothesis_id: str
    cycle_index: int
    outcome_status: str  # SUPPORTED_BOUNDED | REFUTED_NEGATIVE_ARCHIVED | ABSTAINED_UNIDENTIFIABLE | DEFERRED_OR_BLOCKED
    metric_name: str
    metric_value: float
    threshold: float
    falsified: bool
    summary: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "cycle_index": self.cycle_index,
            "outcome_status": self.outcome_status,
            "metric_name": self.metric_name,
            "metric_value": round(self.metric_value, 6),
            "threshold": round(self.threshold, 6),
            "falsified": self.falsified,
            "summary": self.summary,
            "details": self.details,
        }


class ResearchArchive:
    """Durable, hash-chained SQLite archive storing BOTH positive and negative research verdicts."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        key_path = self.workspace / ".agenda_key"
        if not key_path.exists():
            key_path.write_bytes(secrets.token_bytes(32))
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise IntegrityError("agenda archive key corrupt")

        self.db = sqlite3.connect(self.workspace / "research_archive.sqlite3", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS archived_cycles(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_index INTEGER NOT NULL,
                hypothesis_id TEXT NOT NULL,
                gap_id TEXT NOT NULL,
                outcome_status TEXT NOT NULL,
                falsified INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                prev_sig TEXT NOT NULL,
                signature TEXT NOT NULL
            );
        """)
        self.verify()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> ResearchArchive:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _sign(self, data: Any) -> str:
        return hmac.new(self.key, canonical(data).encode("utf-8"), hashlib.sha256).hexdigest()

    def append_cycle(self, record: dict[str, Any]) -> str:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.verify()
            last = self.db.execute(
                "SELECT signature FROM archived_cycles ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev = last["signature"] if last is not None else ("0" * 64)
            payload_str = canonical(record)
            body = {
                "cycle_index": int(record["cycle_index"]),
                "hypothesis_id": str(record["hypothesis_id"]),
                "gap_id": str(record["gap_id"]),
                "outcome_status": str(record["outcome_status"]),
                "falsified": bool(record["falsified"]),
                "payload_sha256": hashlib.sha256(payload_str.encode("utf-8")).hexdigest(),
                "prev_sig": prev,
            }
            sig = self._sign(body)
            self.db.execute(
                """INSERT INTO archived_cycles
                   (cycle_index, hypothesis_id, gap_id, outcome_status, falsified, payload_json, prev_sig, signature)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    body["cycle_index"],
                    body["hypothesis_id"],
                    body["gap_id"],
                    body["outcome_status"],
                    1 if body["falsified"] else 0,
                    payload_str,
                    prev,
                    sig,
                ),
            )
            self.db.commit()
            return sig
        except BaseException:
            self.db.rollback()
            raise

    def verify(self) -> None:
        prev = "0" * 64
        for row in self.db.execute("SELECT * FROM archived_cycles ORDER BY seq"):
            payload_str = row["payload_json"]
            body = {
                "cycle_index": int(row["cycle_index"]),
                "hypothesis_id": row["hypothesis_id"],
                "gap_id": row["gap_id"],
                "outcome_status": row["outcome_status"],
                "falsified": bool(row["falsified"]),
                "payload_sha256": hashlib.sha256(payload_str.encode("utf-8")).hexdigest(),
                "prev_sig": row["prev_sig"],
            }
            if row["prev_sig"] != prev or not hmac.compare_digest(self._sign(body), row["signature"]):
                raise IntegrityError("ResearchArchive HMAC chain tampered")
            prev = row["signature"]

    def list_records(self) -> list[dict[str, Any]]:
        self.verify()
        return [
            json.loads(r["payload_json"])
            for r in self.db.execute("SELECT payload_json FROM archived_cycles ORDER BY seq")
        ]
