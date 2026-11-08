"""Auditable, lease-scheduled, budget-enforced, crash-recoverable ACE Autonomous Runtime.

Implements Fase 3 (Lane A) requirements:
- Goal Manager & Deterministic Planner (``ace.goal.v01`` and ``ace.goal.v1``).
- Three-phase lease scheduler (short ``BEGIN IMMEDIATE`` claim -> unlocked bounded execution ->
  fenced ``BEGIN IMMEDIATE`` commit) preventing global SQLite lock contention and split-brain writes.
- Cold-start ``.init.lock`` ``fcntl.flock`` preventing concurrent ``.host_key`` / schema races.
- HMAC-SHA256 event journal + monotonic external ``.chain_anchor.json`` preventing valid-prefix
  tail rollback (RT-07) and database swap (RT-01).
- Strict state-transition automaton including ``STAGED_FOR_REVIEW``, ``ABSTAINED``,
  ``BUDGET_EXHAUSTED``, and ``HALT_UNCERTAIN`` (RT-02, RT-10).
- Two-phase ``ExternalActionEscrow`` halting on ambiguous external receipts with zero retries.
- Host-side ``IndependentVerifier`` and ``CapabilityRegistry`` before success admission.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any, Callable

from .broker import TypedToolBroker
from .budget import BudgetController, BudgetUsage
from .errors import (
    BudgetExhaustedError,
    IntegrityError,
    PolicyError,
    UncertainExternalEffectError,
)
from .escrow import ExternalActionEscrow
from .planner import plan_objective
from .policy import (
    ALLOWED_TRANSITIONS,
    BudgetCeiling,
    GOAL_STATES,
    GoalPolicy,
    TERMINAL_STATES,
    canonical,
    digest,
    is_strict_int,
    validate_goal,
    verify_no_ancestor_symlinks,
)
from .registry import CapabilityRegistry
from .verifier import IndependentVerifier

SCHEMA = "ace.autonomy.v1"
DEFAULT_LEASE_SECONDS = 30.0


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    fd = os.open(os.fspath(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    dir_fd = os.open(os.fspath(path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


class Autonomy:
    """Durable, bounded autonomous goal executor integrated with real ACE Runtime."""

    def __init__(
        self,
        workspace: str | os.PathLike[str],
        source_root: str | os.PathLike[str] | None = None,
        *,
        anchor_path: str | os.PathLike[str] | None = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        external_handler: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ):
        raw_ws = Path(workspace)
        verify_no_ancestor_symlinks(raw_ws)
        raw_ws.mkdir(parents=True, exist_ok=True)
        verify_no_ancestor_symlinks(raw_ws)
        self.workspace = raw_ws.resolve()

        raw_root = Path(source_root or Path(__file__).resolve().parents[2])
        verify_no_ancestor_symlinks(raw_root)
        self.root = raw_root.resolve()
        if not (self.root / "ace.py").is_file() or os.path.islink(self.root / "ace.py"):
            raise PolicyError("source root must be an actual ACE checkout")

        if anchor_path is not None:
            raw_anchor = Path(anchor_path)
            verify_no_ancestor_symlinks(raw_anchor)
            raw_anchor.parent.mkdir(parents=True, exist_ok=True)
            self.anchor_path = raw_anchor
        else:
            self.anchor_path = self.workspace / ".chain_anchor.json"

        self.lease_seconds = float(lease_seconds)
        self.worker_id = f"w-{os.getpid()}-{secrets.token_hex(6)}"
        self.source_digest = self._compute_source_digest()

        self.broker = TypedToolBroker(
            workspace=self.workspace,
            source_root=self.root,
            external_handler=external_handler,
        )
        self.verifier = IndependentVerifier(workspace=self.workspace, source_root=self.root)
        self._active_dispatch_ctx: dict[str, Any] = {}

        lock_path = self.workspace / ".init.lock"
        lock_fd = os.open(
            os.fspath(lock_path),
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            key_path = self.workspace / ".host_key"
            if os.path.islink(key_path):
                raise IntegrityError("host key symlink forbidden")
            if not key_path.exists():
                _atomic_write_bytes(key_path, secrets.token_bytes(32), 0o600)
            self.key = key_path.read_bytes()
            if len(self.key) != 32:
                raise IntegrityError("host key missing or corrupt")

            db_path = self.workspace / "goals.sqlite3"
            if os.path.islink(db_path):
                raise IntegrityError("SQLite database symlink forbidden")
            self.db = sqlite3.connect(db_path, timeout=30, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            try:
                self.db.execute("PRAGMA journal_mode=WAL")
                self.db.execute("PRAGMA synchronous=FULL")
                self._init_schema()
                self.escrow = ExternalActionEscrow(self.db, self._sign)
                self.registry = CapabilityRegistry(self.db, self._sign)
                with self.transaction():
                    self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', ?)", (SCHEMA,))
                    self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('source', ?)", (self.source_digest,))
                    self.db.execute(
                        "INSERT OR IGNORE INTO metadata VALUES ('db_uuid', ?)",
                        (secrets.token_hex(16),),
                    )
                    self._verify()
                self._sync_anchor_from_db()
            except BaseException:
                self.db.close()
                raise
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def _compute_source_digest(self) -> str:
        autonomy_dir = Path(__file__).resolve().parent
        autonomy_files = sorted(
            p for p in autonomy_dir.glob("*.py")
            if not p.name.startswith("test_")
        )
        engine_path = self.root / "code/ace_runtime/engine.py"
        if not engine_path.is_file() or os.path.islink(engine_path):
            raise PolicyError("ACE engine source missing")

        file_hashes: dict[str, str] = {}
        for p in autonomy_files:
            file_hashes[f"autonomy/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
        file_hashes["ace_runtime/engine.py"] = hashlib.sha256(engine_path.read_bytes()).hexdigest()
        for extra in ("cli.py", "__init__.py"):
            ep = self.root / "code/ace_runtime" / extra
            if ep.is_file() and not os.path.islink(ep):
                file_hashes[f"ace_runtime/{extra}"] = hashlib.sha256(ep.read_bytes()).hexdigest()
        return digest(file_hashes)

    def _init_schema(self) -> None:
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS goals(
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                planned_steps TEXT NOT NULL,
                status TEXT NOT NULL,
                next_step INTEGER NOT NULL,
                results TEXT NOT NULL,
                budget_usage TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                created REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY,
                goal_id TEXT NOT NULL,
                status TEXT NOT NULL,
                next_step INTEGER NOT NULL,
                results_digest TEXT NOT NULL,
                budget_digest TEXT NOT NULL,
                previous TEXT NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leases(
                goal_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                expires_at REAL NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS external_escrow(
                intent_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                receipt_json TEXT NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capability_registry(
                cap_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                kind TEXT NOT NULL,
                artifact_digest TEXT NOT NULL,
                domain_scope TEXT NOT NULL,
                status TEXT NOT NULL,
                event_signature TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                signature TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints(
                goal_id TEXT PRIMARY KEY,
                step_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                event_seq INTEGER NOT NULL,
                event_signature TEXT NOT NULL,
                state_digest TEXT NOT NULL,
                signature TEXT NOT NULL
            );
        """)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Autonomy:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @contextmanager
    def transaction(self, write: bool = True):
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()
            if write:
                self._sync_anchor_from_db()

    def _sign(self, data: Any) -> str:
        return hmac.new(self.key, canonical(data).encode("utf-8"), hashlib.sha256).hexdigest()

    def _read_anchor(self) -> dict[str, Any] | None:
        if not self.anchor_path.exists():
            return None
        if os.path.islink(self.anchor_path):
            raise IntegrityError("chain anchor symlink forbidden")
        try:
            raw = json.loads(self.anchor_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise IntegrityError(f"chain anchor corrupt: {exc}") from exc
        if type(raw) is not dict or set(raw) != {"db_uuid", "head_seq", "head_sig", "signature"}:
            raise IntegrityError("chain anchor schema invalid")
        body = {k: raw[k] for k in ("db_uuid", "head_seq", "head_sig")}
        if not is_strict_int(body["head_seq"]) or body["head_seq"] < 0:
            raise IntegrityError("chain anchor head_seq invalid")
        if not hmac.compare_digest(self._sign(body), raw["signature"]):
            raise IntegrityError("chain anchor HMAC tampered")
        return raw

    def _sync_anchor_from_db(self) -> None:
        row_uuid = self.db.execute("SELECT value FROM metadata WHERE key='db_uuid'").fetchone()
        if row_uuid is None:
            return
        db_uuid = row_uuid["value"]
        last = self.db.execute("SELECT seq, signature FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        head_seq = 0 if last is None else int(last["seq"])
        head_sig = "0" * 64 if last is None else str(last["signature"])

        existing = self._read_anchor()
        if existing is not None:
            if existing["db_uuid"] != db_uuid:
                raise IntegrityError("database UUID mismatch against chain anchor (DB swap detected)")
            if head_seq < existing["head_seq"]:
                raise IntegrityError("journal tail rollback detected against chain anchor")
            if head_seq == existing["head_seq"] and head_sig == existing["head_sig"]:
                return

        body = {"db_uuid": db_uuid, "head_seq": head_seq, "head_sig": head_sig}
        signed = {**body, "signature": self._sign(body)}
        _atomic_write_bytes(self.anchor_path, canonical(signed).encode("utf-8"), 0o600)

    def _append(self, row: sqlite3.Row) -> sqlite3.Row:
        last = self.db.execute("SELECT seq, signature FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        payload = {
            "seq": 1 if last is None else int(last["seq"]) + 1,
            "goal_id": row["id"],
            "status": row["status"],
            "next_step": row["next_step"],
            "results_digest": digest(json.loads(row["results"])),
            "budget_digest": digest(json.loads(row["budget_usage"])),
            "previous": "0" * 64 if last is None else last["signature"],
        }
        sig = self._sign(payload)
        self.db.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
            (
                payload["seq"],
                payload["goal_id"],
                payload["status"],
                payload["next_step"],
                payload["results_digest"],
                payload["budget_digest"],
                payload["previous"],
                sig,
            ),
        )
        cp_body = {
            "goal_id": row["id"],
            "step_index": row["next_step"],
            "status": row["status"],
            "event_seq": payload["seq"],
            "event_signature": sig,
            "state_digest": digest({
                "results": json.loads(row["results"]),
                "budget_usage": json.loads(row["budget_usage"]),
            }),
        }
        cp_sig = self._sign(cp_body)
        self.db.execute(
            "INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?,?,?,?)",
            (
                cp_body["goal_id"],
                cp_body["step_index"],
                cp_body["status"],
                cp_body["event_seq"],
                cp_body["event_signature"],
                cp_body["state_digest"],
                cp_sig,
            ),
        )
        return self.db.execute("SELECT * FROM events WHERE seq=?", (payload["seq"],)).fetchone()

    def _verify(self) -> None:
        metadata = dict(self.db.execute("SELECT key, value FROM metadata"))
        if (
            set(metadata) != {"schema", "source", "db_uuid"}
            or metadata["schema"] != SCHEMA
            or metadata["source"] != self.source_digest
        ):
            raise IntegrityError("source/schema mismatch: use a reviewed migration")

        anchor = self._read_anchor()
        if anchor is not None and anchor["db_uuid"] != metadata["db_uuid"]:
            raise IntegrityError("database swap detected: db_uuid differs from external anchor")

        goals = {r["id"]: r for r in self.db.execute("SELECT * FROM goals")}
        latest: dict[str, sqlite3.Row] = {}
        goal_prev_status: dict[str, str | None] = {gid: None for gid in goals}
        valid_event_sigs: set[str] = set()
        events_by_seq: dict[int, str] = {}
        prev = "0" * 64

        for seq, e in enumerate(self.db.execute("SELECT * FROM events ORDER BY seq"), 1):
            payload = {
                k: e[k]
                for k in (
                    "seq",
                    "goal_id",
                    "status",
                    "next_step",
                    "results_digest",
                    "budget_digest",
                    "previous",
                )
            }
            if (
                e["seq"] != seq
                or e["previous"] != prev
                or not hmac.compare_digest(self._sign(payload), e["signature"])
            ):
                raise IntegrityError("receipt chain tampered")
            gid = e["goal_id"]
            if gid not in goals:
                raise IntegrityError("orphan receipt")
            prior_st = goal_prev_status[gid]
            if e["status"] not in ALLOWED_TRANSITIONS.get(prior_st, frozenset()):
                raise IntegrityError(f"illegal state transition {prior_st} -> {e['status']}")
            goal_prev_status[gid] = e["status"]
            latest[gid] = e
            prev = e["signature"]
            valid_event_sigs.add(e["signature"])
            events_by_seq[seq] = e["signature"]

        max_seq = len(events_by_seq)
        if anchor is not None:
            if max_seq < anchor["head_seq"]:
                raise IntegrityError("journal tail rollback detected (events shorter than anchor)")
            if anchor["head_seq"] > 0 and events_by_seq.get(anchor["head_seq"]) != anchor["head_sig"]:
                raise IntegrityError("journal fork detected at anchored sequence")

        if len(latest) != len(goals):
            raise IntegrityError("goal missing receipt")

        for goal_id, row in goals.items():
            payload = json.loads(row["payload"])
            if canonical(payload) != row["payload"] or validate_goal(payload) != goal_id:
                raise IntegrityError("goal payload tampered or non-canonical")
            steps = json.loads(row["planned_steps"])
            if type(steps) is not list or not steps:
                raise IntegrityError("planned_steps corrupt")
            results = json.loads(row["results"])
            budget_usage = json.loads(row["budget_usage"])
            e = latest[goal_id]
            if (
                row["status"] != e["status"]
                or row["next_step"] != e["next_step"]
                or digest(results) != e["results_digest"]
                or digest(budget_usage) != e["budget_digest"]
                or row["next_step"] != len(results)
                or row["next_step"] > len(steps)
            ):
                raise IntegrityError("state/receipt mismatch")
            if row["status"] not in GOAL_STATES:
                raise IntegrityError("invalid state")
            if row["status"] == "QUEUED" and row["next_step"] != 0:
                raise IntegrityError("invalid queued state")
            if row["status"] in {"SUCCEEDED", "STAGED_FOR_REVIEW"} and row["next_step"] != len(steps):
                raise IntegrityError("unfinished goal marked successful/staged")

            cp = self.db.execute("SELECT * FROM checkpoints WHERE goal_id=?", (goal_id,)).fetchone()
            if cp is None:
                raise IntegrityError("missing goal checkpoint")
            cp_body = {
                k: cp[k]
                for k in ("goal_id", "step_index", "status", "event_seq", "event_signature", "state_digest")
            }
            if (
                not hmac.compare_digest(self._sign(cp_body), cp["signature"])
                or cp["event_signature"] != e["signature"]
                or cp["status"] != row["status"]
                or cp["step_index"] != row["next_step"]
            ):
                raise IntegrityError("checkpoint tampered or out of sync")

        for lrow in self.db.execute("SELECT * FROM leases"):
            lbody = {
                k: lrow[k]
                for k in ("goal_id", "worker_id", "pid", "step_index", "epoch", "expires_at")
            }
            if not hmac.compare_digest(self._sign(lbody), lrow["signature"]):
                raise IntegrityError("lease row tampered")

        self.escrow.verify_all()
        self.registry.verify_all(valid_event_sigs)

    def _resolve_steps_and_policy(self, goal: dict[str, Any]) -> tuple[list[dict[str, Any]], GoalPolicy, BudgetCeiling]:
        schema = goal["schema"]
        budget = BudgetCeiling.from_dict(goal.get("budget"))
        policy = GoalPolicy.from_dict(goal.get("policy"), schema=schema)
        if "objective" in goal:
            steps = plan_objective(goal["objective"], policy=policy, budget=budget)
        else:
            steps = list(goal["steps"])
        return steps, policy, budget

    def enqueue(self, goal: dict[str, Any]) -> str:
        gid = validate_goal(goal)
        steps, _, _ = self._resolve_steps_and_policy(goal)
        init_usage = BudgetUsage().to_dict()
        with self.transaction():
            self._verify()
            if self.db.execute("SELECT 1 FROM goals WHERE id=?", (gid,)).fetchone():
                return gid
            self.db.execute(
                "INSERT INTO goals VALUES (?,?,?,'QUEUED',0,'[]',?,0,?)",
                (gid, canonical(goal), canonical(steps), canonical(init_usage), time.time()),
            )
            self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone())
        return gid

    def _dispatch(self, action: dict[str, Any]) -> dict[str, Any]:
        ctx = self._active_dispatch_ctx
        goal_id = ctx.get("goal_id", "adhoc")
        policy = ctx.get("policy") or GoalPolicy.from_dict(None, schema="ace.goal.v1")
        rem_wall = float(ctx.get("remaining_wall_s", 180.0))
        rem_cpu = float(ctx.get("remaining_cpu_s", 60.0))
        return self.broker.dispatch(
            action,
            goal_id=goal_id,
            policy=policy,
            remaining_wall_s=rem_wall,
            remaining_cpu_s=rem_cpu,
        )

    def _halt_uncertain_in_tx(
        self,
        row: sqlite3.Row,
        step: int,
        reason: str,
        usage_dict: dict[str, Any],
    ) -> dict[str, Any]:
        esc = self.escrow.get_intent(row["id"], step)
        if esc is not None and esc["state"] == "DISPATCHED":
            self.escrow.update_state(row["id"], step, "HALT_UNCERTAIN", {"reason": reason})
        results = json.loads(row["results"])
        results.append({
            "step": step,
            "ok": False,
            "halted_uncertain": True,
            "error_type": "UncertainExternalEffectError",
            "message": reason,
        })
        self.db.execute("DELETE FROM leases WHERE goal_id=?", (row["id"],))
        self.db.execute(
            "UPDATE goals SET status='HALT_UNCERTAIN', next_step=?, results=?, budget_usage=? WHERE id=?",
            (step + 1, canonical(results), canonical(usage_dict), row["id"]),
        )
        self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (row["id"],)).fetchone())
        return self.report_in_transaction(row["id"])

    def _claim_step_lease(self, goal_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Phase 1: Acquire short transactional lease or recover orphaned lease."""
        now_mono = time.monotonic()
        with self.transaction():
            self._verify()
            if goal_id is None:
                candidates = self.db.execute(
                    "SELECT * FROM goals WHERE status IN ('QUEUED','RUNNING') ORDER BY created, id"
                ).fetchall()
            else:
                one = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
                candidates = [one] if one is not None and one["status"] in {"QUEUED", "RUNNING"} else []

            for row in candidates:
                gid = row["id"]
                step = int(row["next_step"])
                existing_lease = self.db.execute("SELECT * FROM leases WHERE goal_id=?", (gid,)).fetchone()
                if existing_lease is not None:
                    alive = _pid_is_alive(int(existing_lease["pid"]))
                    not_expired = float(existing_lease["expires_at"]) > now_mono
                    if alive and not_expired and existing_lease["worker_id"] != self.worker_id:
                        continue
                    # Orphaned or expired lease: check if external action was dispatched!
                    esc = self.escrow.get_intent(gid, step)
                    if esc is not None and esc["state"] == "DISPATCHED":
                        halted = self._halt_uncertain_in_tx(
                            row,
                            step,
                            "worker crashed or lease expired after external_action dispatch without receipt",
                            json.loads(row["budget_usage"]),
                        )
                        return None, halted
                    self.db.execute("DELETE FROM leases WHERE goal_id=?", (gid,))

                # Also guard against any pre-existing uncommitted DISPATCHED escrow even without lease row
                esc = self.escrow.get_intent(gid, step)
                if esc is not None and esc["state"] == "DISPATCHED":
                    halted = self._halt_uncertain_in_tx(
                        row,
                        step,
                        "unverified external_action escrow found on recovery; automatic retry forbidden",
                        json.loads(row["budget_usage"]),
                    )
                    return None, halted

                new_epoch = int(row["lease_epoch"]) + 1
                self.db.execute("UPDATE goals SET lease_epoch=? WHERE id=?", (new_epoch, gid))
                lbody = {
                    "goal_id": gid,
                    "worker_id": self.worker_id,
                    "pid": os.getpid(),
                    "step_index": step,
                    "epoch": new_epoch,
                    "expires_at": now_mono + self.lease_seconds,
                }
                lsig = self._sign(lbody)
                self.db.execute(
                    "INSERT INTO leases VALUES (?,?,?,?,?,?,?)",
                    (
                        lbody["goal_id"],
                        lbody["worker_id"],
                        lbody["pid"],
                        lbody["step_index"],
                        lbody["epoch"],
                        lbody["expires_at"],
                        lsig,
                    ),
                )
                steps = json.loads(row["planned_steps"])
                action = steps[step]
                if action.get("tool") == "external_action":
                    self.escrow.record_dispatched(gid, step, action, new_epoch)

                return {
                    "goal_id": gid,
                    "goal": json.loads(row["payload"]),
                    "steps": steps,
                    "step": step,
                    "epoch": new_epoch,
                    "budget_usage": json.loads(row["budget_usage"]),
                }, None
        return None, None

    def _release_lease_quietly(self, goal_id: str, epoch: int) -> None:
        try:
            with self.transaction():
                self.db.execute(
                    "DELETE FROM leases WHERE goal_id=? AND epoch=?",
                    (goal_id, epoch),
                )
        except Exception:
            pass

    def run_one(self, goal_id: str | None = None) -> dict[str, Any] | None:
        """Execute at most one bounded step under a fenced worker lease."""
        claim, immediate_report = self._claim_step_lease(goal_id)
        if immediate_report is not None:
            return immediate_report
        if claim is None:
            return None

        gid = claim["goal_id"]
        goal = claim["goal"]
        steps = claim["steps"]
        step = claim["step"]
        epoch = claim["epoch"]
        action = steps[step]
        _, policy, ceiling = self._resolve_steps_and_policy(goal)
        budget_ctrl = BudgetController(ceiling, BudgetUsage.from_dict(claim["budget_usage"]))

        is_external = action.get("tool") == "external_action"
        verdict = "RUNNING"
        detail: dict[str, Any]
        verification_meta: dict[str, Any] | None = None

        try:
            try:
                budget_ctrl.check_pre_step(step, action)
            except BudgetExhaustedError as exc:
                verdict = "BUDGET_EXHAUSTED"
                detail = {
                    "step": step,
                    "ok": False,
                    "budget_exhausted": True,
                    "error_type": "BudgetExhaustedError",
                    "message": str(exc),
                }
            else:
                tokens = budget_ctrl.begin_measurement()
                while True:
                    self._active_dispatch_ctx = {
                        "goal_id": gid,
                        "policy": policy,
                        "remaining_wall_s": budget_ctrl.remaining_wall_seconds(),
                        "remaining_cpu_s": budget_ctrl.remaining_cpu_seconds(),
                    }
                    try:
                        evidence = self._dispatch(action)
                        verification_meta = self.verifier.verify_step_evidence(
                            action,
                            evidence,
                            goal_id=gid,
                            policy=policy,
                        )
                        budget_ctrl.finish_measurement(
                            tokens,
                            step_completed=True,
                            staged_candidate=(action["tool"] == "stage_candidate"),
                        )
                        if action["tool"] == "abstain":
                            verdict = "ABSTAINED"
                        elif step + 1 == len(steps):
                            has_staged = any(s["tool"] == "stage_candidate" for s in steps)
                            if policy.review_policy == "stage-for-review" or has_staged:
                                verdict = "STAGED_FOR_REVIEW"
                            else:
                                verdict = "SUCCEEDED"
                        else:
                            verdict = "RUNNING"
                        detail = {
                            "step": step,
                            "ok": True,
                            "evidence": evidence,
                            "verified": True,
                        }
                        break
                    except IntegrityError:
                        raise
                    except BudgetExhaustedError as exc:
                        verdict = "BUDGET_EXHAUSTED"
                        detail = {
                            "step": step,
                            "ok": False,
                            "budget_exhausted": True,
                            "error_type": "BudgetExhaustedError",
                            "message": str(exc),
                        }
                        break
                    except UncertainExternalEffectError as exc:
                        verdict = "HALT_UNCERTAIN"
                        detail = {
                            "step": step,
                            "ok": False,
                            "halted_uncertain": True,
                            "error_type": "UncertainExternalEffectError",
                            "message": str(exc),
                        }
                        break
                    except PolicyError as exc:
                        try:
                            budget_ctrl.finish_measurement(tokens, step_completed=True)
                        except BudgetExhaustedError as bexc:
                            verdict = "BUDGET_EXHAUSTED"
                            detail = {
                                "step": step,
                                "ok": False,
                                "budget_exhausted": True,
                                "error_type": "BudgetExhaustedError",
                                "message": str(bexc),
                            }
                            break
                        verdict = "FAILED"
                        detail = {
                            "step": step,
                            "ok": False,
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                        break
                    except (ValueError, RuntimeError, OSError) as exc:
                        if (
                            goal.get("schema") == "ace.goal.v1"
                            and not is_external
                            and type(exc) in (RuntimeError, OSError)
                            and budget_ctrl.can_retry_local_step(step, is_external=False)
                        ):
                            budget_ctrl.record_retry(step)
                            continue
                        try:
                            budget_ctrl.finish_measurement(tokens, step_completed=True)
                        except BudgetExhaustedError as bexc:
                            verdict = "BUDGET_EXHAUSTED"
                            detail = {
                                "step": step,
                                "ok": False,
                                "budget_exhausted": True,
                                "error_type": "BudgetExhaustedError",
                                "message": str(bexc),
                            }
                            break
                        verdict = "FAILED"
                        detail = {
                            "step": step,
                            "ok": False,
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                        break
                    finally:
                        self._active_dispatch_ctx = {}

            with self.transaction():
                self._verify()
                cur_row = self.db.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
                cur_lease = self.db.execute("SELECT * FROM leases WHERE goal_id=?", (gid,)).fetchone()
                if (
                    cur_row is None
                    or cur_row["status"] not in {"QUEUED", "RUNNING"}
                    or int(cur_row["lease_epoch"]) != epoch
                    or cur_lease is None
                    or int(cur_lease["epoch"]) != epoch
                ):
                    raise IntegrityError("lease fencing epoch lost during step execution; commit rejected")

                if is_external:
                    if verdict in {"RUNNING", "SUCCEEDED", "STAGED_FOR_REVIEW"}:
                        self.escrow.update_state(gid, step, "COMPLETED", detail.get("evidence"))
                    elif verdict == "HALT_UNCERTAIN":
                        self.escrow.update_state(gid, step, "HALT_UNCERTAIN", {"message": detail["message"]})
                    else:
                        self.escrow.update_state(gid, step, "FAILED", {"message": detail.get("message", "")})

                results = json.loads(cur_row["results"])
                results.append(detail)
                self.db.execute("DELETE FROM leases WHERE goal_id=?", (gid,))
                self.db.execute(
                    "UPDATE goals SET status=?, next_step=?, results=?, budget_usage=? WHERE id=?",
                    (
                        verdict,
                        step + 1,
                        canonical(results),
                        canonical(budget_ctrl.usage.to_dict()),
                        gid,
                    ),
                )
                ev_row = self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone())

                if detail.get("ok") and verification_meta is not None:
                    cap_status = (
                        "STAGED_CANDIDATE_UNEXECUTED"
                        if action["tool"] == "stage_candidate"
                        else "VERIFIED_OPERATIONAL"
                    )
                    self.registry.register_verified(
                        goal_id=gid,
                        step_index=step,
                        kind=verification_meta["kind"],
                        artifact_digest=verification_meta["artifact_digest"],
                        domain_scope=action["tool"],
                        status=cap_status,
                        event_signature=ev_row["signature"],
                        metadata={"tool": action["tool"], "goal_status": verdict},
                    )
                return self.report_in_transaction(gid)
        except BaseException:
            if not is_external:
                self._release_lease_quietly(gid, epoch)
            raise

    def run_until_stopped(self, goal_id: str | None = None, *, max_iterations: int = 32) -> list[dict[str, Any]]:
        """Autonomously execute steps until terminal/halted/empty queue without human prompts."""
        if not is_strict_int(max_iterations) or not 1 <= max_iterations <= 128:
            raise PolicyError("max_iterations must be an int in 1..128")
        history: list[dict[str, Any]] = []
        for _ in range(max_iterations):
            rep = self.run_one(goal_id)
            if rep is None:
                break
            history.append(rep)
            if goal_id is not None and rep["status"] in TERMINAL_STATES:
                break
        return history

    def reconcile_external(
        self,
        goal_id: str,
        step_index: int,
        *,
        resolution: str,
        external_receipt_id: str | None = None,
    ) -> dict[str, Any]:
        """Explicit operator reconciliation for a goal stopped in ``HALT_UNCERTAIN``."""
        if resolution not in {"CONFIRMED_COMPLETED", "ABORT_FAILED"}:
            raise PolicyError("resolution must be CONFIRMED_COMPLETED or ABORT_FAILED")
        with self.transaction():
            self._verify()
            row = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
            if row is None:
                raise ValueError("unknown goal")
            if row["status"] != "HALT_UNCERTAIN":
                raise PolicyError("goal is not in HALT_UNCERTAIN")
            steps = json.loads(row["planned_steps"])
            if resolution == "CONFIRMED_COMPLETED":
                if not external_receipt_id or type(external_receipt_id) is not str:
                    raise PolicyError("CONFIRMED_COMPLETED requires external_receipt_id")
                self.escrow.update_state(
                    goal_id,
                    step_index,
                    "COMPLETED",
                    {"reconciled_receipt_id": external_receipt_id},
                )
                new_status = "SUCCEEDED" if int(row["next_step"]) == len(steps) else "RUNNING"
            else:
                self.escrow.update_state(
                    goal_id,
                    step_index,
                    "RECONCILED_ABORT",
                    {"resolution": "ABORT_FAILED"},
                )
                new_status = "FAILED"
            self.db.execute("UPDATE goals SET status=? WHERE id=?", (new_status, goal_id))
            self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone())
            return self.report_in_transaction(goal_id)

    def report_in_transaction(self, goal_id: str) -> dict[str, Any]:
        r = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        if r is None:
            raise ValueError("unknown goal")
        return {
            "goal_id": goal_id,
            "status": r["status"],
            "next_step": r["next_step"],
            "total_steps": len(json.loads(r["planned_steps"])),
            "results": json.loads(r["results"]),
            "budget_usage": json.loads(r["budget_usage"]),
            "source": self.source_digest,
            "schema": SCHEMA,
            "scientific_decision": "NOT_ASSESSED",
            "oaie_established": False,
        }

    def report(self, goal_id: str) -> dict[str, Any]:
        with self.transaction(write=False):
            self._verify()
            return self.report_in_transaction(goal_id)

    def status(self) -> dict[str, Any]:
        with self.transaction(write=False):
            self._verify()
            goals = []
            counts: dict[str, int] = {}
            for r in self.db.execute("SELECT * FROM goals ORDER BY created, id"):
                counts[r["status"]] = counts.get(r["status"], 0) + 1
                goals.append({
                    "goal_id": r["id"],
                    "name": json.loads(r["payload"])["name"],
                    "status": r["status"],
                    "next_step": r["next_step"],
                    "total_steps": len(json.loads(r["planned_steps"])),
                })
            ev_count = self.db.execute("SELECT count(*) FROM events").fetchone()[0]
            caps = self.registry.list_capabilities()
            return {
                "schema": SCHEMA,
                "source": self.source_digest,
                "goal_counts": counts,
                "goals": goals,
                "events": ev_count,
                "capabilities_registered": len(caps),
                "scientific_decision": "NOT_ASSESSED",
                "oaie_established": False,
            }

    def cancel(self, goal_id: str) -> dict[str, Any]:
        with self.transaction():
            self._verify()
            row = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
            if row is None:
                raise ValueError("unknown goal")
            if row["status"] in {"QUEUED", "RUNNING", "HALT_UNCERTAIN"}:
                self.db.execute("DELETE FROM leases WHERE goal_id=?", (goal_id,))
                self.db.execute("UPDATE goals SET status='CANCELLED' WHERE id=?", (goal_id,))
                self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone())
            return self.report_in_transaction(goal_id)
