"""Auditable, deterministic, crash-recoverable ACE goal executor.

Prototype security contract: trusted builtin tools only, trusted workspace and
host-held local key. Not a sandbox, hosted agent, or scientific AI advance.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

SCHEMA = "ace.autonomy.v01"
ALLOWED_TOOLS = frozenset({"inspect_file", "ace_status", "ace_demo"})
MAX_STEPS = 8
MAX_FILE_BYTES = 64 * 1024


class IntegrityError(ValueError):
    pass


class PolicyError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_goal(goal):
    if type(goal) is not dict or set(goal) != {"schema", "name", "steps"}:
        raise PolicyError("goal must have schema, name and steps only")
    if goal["schema"] != "ace.goal.v01" or type(goal["name"]) is not str or not 1 <= len(goal["name"]) <= 80:
        raise PolicyError("invalid goal schema or name")
    steps = goal["steps"]
    if type(steps) is not list or not 1 <= len(steps) <= MAX_STEPS:
        raise PolicyError("invalid step budget")
    for item in steps:
        if type(item) is not dict or type(item.get("tool")) is not str or item["tool"] not in ALLOWED_TOOLS:
            raise PolicyError("unauthorized tool")
        if item["tool"] == "inspect_file":
            if set(item) != {"tool", "path"} or type(item["path"]) is not str or not item["path"]:
                raise PolicyError("inspect_file requires a relative path")
            p = Path(item["path"])
            if p.is_absolute() or any(x in (".", "..") for x in p.parts):
                raise PolicyError("absolute or traversal path forbidden")
        elif set(item) != {"tool"}:
            raise PolicyError("unknown tool parameters")
    return digest(goal)


class Autonomy:
    """One-step transactional dispatcher; restart and multi-worker safe for local tools.

    ace_demo has a separate SQLite workspace, and is replay-idempotent for its
    fixed public tasks but not a general external exactly-once guarantee.
    """

    def __init__(self, workspace, source_root=None):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.root = Path(source_root or Path(__file__).resolve().parents[2]).resolve()
        if not (self.root / "ace.py").is_file():
            raise PolicyError("source root must be an actual ACE checkout")
        key_path = self.workspace / ".host_key"
        try:
            fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(32))
                f.flush()
                os.fsync(f.fileno())
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise IntegrityError("host key missing or corrupt")
        paths = [Path(__file__), self.root / "code/ace_runtime/engine.py"]
        if any(not p.is_file() for p in paths):
            raise PolicyError("ACE engine source missing")
        self.source_digest = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        self.db = sqlite3.connect(self.workspace / "goals.sqlite3", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS goals(
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                next_step INTEGER NOT NULL, results TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY, goal_id TEXT NOT NULL, status TEXT NOT NULL,
                next_step INTEGER NOT NULL, results_digest TEXT NOT NULL,
                previous TEXT NOT NULL, signature TEXT NOT NULL);
        """)
        try:
            with self.transaction():
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', ?)", (SCHEMA,))
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('source', ?)", (self.source_digest,))
                self._verify()
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    from contextlib import contextmanager

    @contextmanager
    def transaction(self, write=True):
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def _sign(self, data):
        return hmac.new(self.key, canonical(data).encode(), hashlib.sha256).hexdigest()

    def _append(self, row):
        last = self.db.execute("SELECT seq, signature FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        payload = {"seq": 1 if last is None else last["seq"] + 1,
                   "goal_id": row["id"], "status": row["status"],
                   "next_step": row["next_step"],
                   "results_digest": digest(json.loads(row["results"])),
                   "previous": "0" * 64 if last is None else last["signature"]}
        sig = self._sign(payload)
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                        (payload["seq"], payload["goal_id"], payload["status"],
                         payload["next_step"], payload["results_digest"],
                         payload["previous"], sig))

    def _verify(self):
        metadata = dict(self.db.execute("SELECT key, value FROM metadata"))
        if metadata != {"schema": SCHEMA, "source": self.source_digest}:
            raise IntegrityError("source/schema mismatch: use a reviewed migration")
        goals = {r["id"]: r for r in self.db.execute("SELECT * FROM goals")}
        latest = {}
        prev = "0" * 64
        for seq, e in enumerate(self.db.execute("SELECT * FROM events ORDER BY seq"), 1):
            payload = {k: e[k] for k in ("seq", "goal_id", "status", "next_step", "results_digest", "previous")}
            if e["seq"] != seq or e["previous"] != prev or not hmac.compare_digest(self._sign(payload), e["signature"]):
                raise IntegrityError("receipt chain tampered")
            if e["goal_id"] not in goals:
                raise IntegrityError("orphan receipt")
            latest[e["goal_id"]] = e
            prev = e["signature"]
        if len(latest) != len(goals):
            raise IntegrityError("goal missing receipt")
        for goal_id, row in goals.items():
            payload = json.loads(row["payload"])
            if validate_goal(payload) != goal_id:
                raise IntegrityError("goal payload tampered")
            results = json.loads(row["results"])
            e = latest[goal_id]
            if (row["status"] != e["status"] or row["next_step"] != e["next_step"] or
                digest(results) != e["results_digest"] or
                row["next_step"] != len(results) or row["next_step"] > len(payload["steps"])):
                raise IntegrityError("state/receipt mismatch")
            if row["status"] not in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}:
                raise IntegrityError("invalid state")
            if row["status"] == "QUEUED" and row["next_step"] != 0:
                raise IntegrityError("invalid queued state")
            if row["status"] == "SUCCEEDED" and row["next_step"] != len(payload["steps"]):
                raise IntegrityError("unfinished goal marked successful")

    def enqueue(self, goal):
        gid = validate_goal(goal)
        with self.transaction():
            self._verify()
            if self.db.execute("SELECT 1 FROM goals WHERE id=?", (gid,)).fetchone():
                return gid
            self.db.execute("INSERT INTO goals VALUES (?,?,'QUEUED',0,'[]',?)",
                            (gid, canonical(goal), time.time()))
            self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone())
        return gid

    def _dispatch(self, action):
        tool = action["tool"]
        if tool == "inspect_file":
            p = (self.root / action["path"]).resolve()
            if not p.is_relative_to(self.root) or not p.is_file() or p.is_symlink():
                raise PolicyError("file is outside authorized checkout")
            if p.stat().st_size > MAX_FILE_BYTES:
                raise PolicyError("file size budget exceeded")
            raw = p.read_bytes()
            return {"tool": tool, "path": action["path"], "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest()}
        if tool in {"ace_status", "ace_demo"}:
            from ace_runtime.engine import Runtime
            if tool == "ace_demo":
                from ace_runtime.cli import demo
            with Runtime(self.workspace / "real_ace_workspace") as runtime:
                if tool == "ace_status":
                    z = runtime.status()
                    return {"tool": tool, "implementation": z["implementation"],
                            "completed": z["completed"], "capabilities": z["capabilities"],
                            "scientific_decision": z["scientific_decision"]}
                result = demo(runtime)
                if any(v["correct"] != v["total"] for v in result["evaluation"].values()):
                    raise IntegrityError("real ACE public demo failed")
                z = result["status"]
                return {"tool": tool, "tasks": z["completed"],
                        "capabilities": z["capabilities"], "events": z["events"],
                        "implementation": z["implementation"],
                        "scientific_decision": z["scientific_decision"]}
        raise PolicyError("unauthorized tool")

    def run_one(self, goal_id=None):
        """Process at most one deterministic action atomically.

        Pure read-only actions may be replayed after process crash. The ACE demo's
        separate workspace is idempotent for fixed public examples, not arbitrary
        external side effects. This prototype does not dispatch external tools.
        """
        with self.transaction():
            self._verify()
            if goal_id is None:
                row = self.db.execute("SELECT * FROM goals WHERE status IN ('QUEUED','RUNNING') ORDER BY created,id LIMIT 1").fetchone()
            else:
                row = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
            if row is None or row["status"] not in {"QUEUED", "RUNNING"}:
                return None
            goal = json.loads(row["payload"])
            step = row["next_step"]
            try:
                evidence = self._dispatch(goal["steps"][step])
                verdict = "SUCCEEDED" if step + 1 == len(goal["steps"]) else "RUNNING"
                detail = {"step": step, "ok": True, "evidence": evidence}
            except (PolicyError, ValueError, RuntimeError, OSError) as e:
                verdict = "FAILED"
                detail = {"step": step, "ok": False, "error_type": type(e).__name__, "message": str(e)}
            results = json.loads(row["results"])
            results.append(detail)
            self.db.execute("UPDATE goals SET status=?, next_step=?, results=? WHERE id=?",
                            (verdict, step + 1, canonical(results), row["id"]))
            self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (row["id"],)).fetchone())
            return self.report_in_transaction(row["id"])

    def report_in_transaction(self, goal_id):
        r = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        if r is None:
            raise ValueError("unknown goal")
        return {"goal_id": goal_id, "status": r["status"],
                "next_step": r["next_step"], "results": json.loads(r["results"]),
                "source": self.source_digest, "schema": SCHEMA}

    def report(self, goal_id):
        with self.transaction(write=False):
            self._verify()
            return self.report_in_transaction(goal_id)

    def cancel(self, goal_id):
        with self.transaction():
            self._verify()
            row = self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
            if row is None:
                raise ValueError("unknown goal")
            if row["status"] in {"QUEUED", "RUNNING"}:
                self.db.execute("UPDATE goals SET status='CANCELLED' WHERE id=?", (goal_id,))
                self._append(self.db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone())
            return self.report_in_transaction(goal_id)
