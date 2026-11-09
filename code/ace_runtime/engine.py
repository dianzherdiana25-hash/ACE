"""Durable task acquisition, validated inheritance and pure typed predictions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3

from ace_candidate_search import model
from ace_research_primitives import primitive_discovery as r1
from ace_capability_evolution import compositional as c, structural as s

MAX_TASKS = 256
MAX_MODELS = 128
SCHEMA = "ace.runtime.v1"


class IntegrityError(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def program_from_data(data):
    """Decode only the closed product grammar; never evaluate stored source."""
    keys = {"kind", "counter_ast", "weights", "dfa", "fixed_guard"}
    if type(data) is not dict or set(data) != keys:
        raise IntegrityError("invalid program schema")
    kind, weights, signature, fixed = (data[k] for k in ("kind", "weights", "dfa", "fixed_guard"))
    if kind not in ("counter", "dfa", "product", "fixed_product") or fixed not in c.GUARDS:
        raise IntegrityError("forbidden program kind/guard")
    has_counter = kind != "dfa"
    has_dfa = kind in ("dfa", "product")
    if has_counter:
        if (type(weights) is not list or len(weights) != 2 or
                any(type(w) is not int for w in weights) or
                tuple(weights) not in s.coefficient_grammar()):
            raise IntegrityError("forbidden counter coefficients")
        if s.digest(data["counter_ast"]) != s.digest(s.typed_ast(model, weights).data()):
            raise IntegrityError("counter AST differs from coefficients")
    elif weights is not None or data["counter_ast"] is not None:
        raise IntegrityError("DFA cannot contain counter AST")
    automaton = None
    if has_dfa:
        if type(signature) is not list or not 1 <= len(signature) <= 63:
            raise IntegrityError("DFA state budget exceeded")
        labels, edges = [], []
        for row in signature:
            if (type(row) is not list or len(row) != 2 or
                    (row[0] is not None and type(row[0]) is not bool) or type(row[1]) is not list):
                raise IntegrityError("invalid DFA state")
            edge_map = {}
            for edge in row[1]:
                if (type(edge) is not list or len(edge) != 2 or
                        edge[0] not in ("a", "b") or edge[0] in edge_map or
                        type(edge[1]) is not int or not 0 <= edge[1] < len(signature)):
                    raise IntegrityError("invalid DFA transition")
                edge_map[edge[0]] = edge[1]
            labels.append(row[0])
            edges.append(edge_map)
        automaton = r1.Automaton(labels, edges, list(range(len(labels))))
    elif signature is not None:
        raise IntegrityError("unexpected DFA")
    if kind != "fixed_product" and fixed != "true":
        raise IntegrityError("unexpected fixed guard")
    program = c.Program(kind, tuple(weights) if weights is not None else None, automaton, fixed)
    if s.digest(program.data()) != s.digest(data):
        raise IntegrityError("noncanonical program")
    return program


def validate_task(task):
    if type(task) is not dict or set(task) != {"name", "train", "validation"}:
        raise ValueError("task requires exactly name, train and validation")
    name = task["name"]
    if type(name) is not str or not 1 <= len(name) <= 80 or name.strip() != name:
        raise ValueError("task name must contain 1..80 characters")
    c.validate_rows(task["train"], 63)
    c.validate_rows(task["validation"], 128)
    if {w for w, _ in task["train"]} & {w for w, _ in task["validation"]}:
        raise ValueError("training and validation must be disjoint")
    prefixes = {w[:i] for w, _ in task["train"] for i in range(len(w) + 1)}
    if len(prefixes) > 63:
        raise ValueError("training prefix-tree budget exceeds 63 nodes")


class Runtime:
    """SQLite transactions make pure local trials resumable and serializable.

    A process interruption rolls back the active trial; replay may recompute that
    pure trial. This does not implement exactly-once external actions or oracles.
    """

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        root = Path(__file__).resolve().parents[2]
        files = [Path(__file__), Path(c.__file__), Path(s.__file__),
                 Path(r1.__file__), Path(model.__file__)]
        self.implementation = s.digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in files})
        self.db = sqlite3.connect(self.workspace / "ace.sqlite3", timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
                    result TEXT, ordinal INTEGER NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS library (
                    id TEXT PRIMARY KEY, program TEXT NOT NULL, acquired_task TEXT NOT NULL REFERENCES tasks(id));
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, task_id TEXT NOT NULL,
                    payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluations (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(id), data TEXT NOT NULL, report TEXT NOT NULL);
            """)
            with self._transaction():
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', ?)", (SCHEMA,))
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('implementation', ?)",
                                (self.implementation,))
                self._verify()
        except BaseException:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.db.close()

    @contextmanager
    def _transaction(self, write=True):
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _append(self, kind, task_id, payload):
        last = self.db.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        event = {"seq": last["seq"] + 1 if last else 1, "kind": kind,
                 "task_id": task_id, "payload": payload,
                 "previous": last["hash"] if last else "0" * 64}
        self.db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                        (event["seq"], kind, task_id, encoded(payload), event["previous"], s.digest(event)))

    def _verify(self):
        metadata = dict(self.db.execute("SELECT key, value FROM metadata").fetchall())
        if metadata != {"schema": SCHEMA, "implementation": self.implementation}:
            raise IntegrityError("runtime source/schema changed; use a new workspace or an explicit migration")
        tasks = {row["id"]: row for row in self.db.execute("SELECT * FROM tasks")}
        models = {row["id"]: row for row in self.db.execute("SELECT * FROM library")}
        evaluations = {row["task_id"]: row for row in self.db.execute("SELECT * FROM evaluations")}
        if len(tasks) > MAX_TASKS or len(models) > MAX_MODELS:
            raise IntegrityError("workspace budget exceeded")
        previous, seen, enqueue_count = "0" * 64, set(), 0
        for seq, row in enumerate(self.db.execute("SELECT * FROM events ORDER BY seq"), 1):
            payload = json.loads(row["payload"])
            event = {"seq": seq, "kind": row["kind"], "task_id": row["task_id"],
                     "payload": payload, "previous": previous}
            if row["seq"] != seq or row["previous"] != previous or s.digest(event) != row["hash"]:
                raise IntegrityError("event chain mismatch")
            key = (row["kind"], row["task_id"])
            if key in seen or row["task_id"] not in tasks:
                raise IntegrityError("duplicate or orphaned task event")
            seen.add(key)
            task = tasks[row["task_id"]]
            if row["kind"] == "enqueued":
                enqueue_count += 1
                if task["ordinal"] != enqueue_count:
                    raise IntegrityError("task order differs from enqueue receipts")
                expected = {"task_sha256": task["id"]}
            elif row["kind"] == "completed":
                if ("enqueued", task["id"]) not in seen:
                    raise IntegrityError("completion precedes enqueue")
                expected = {"result": json.loads(task["result"])} if task["result"] else None
            elif row["kind"] == "evaluated":
                if ("completed", task["id"]) not in seen:
                    raise IntegrityError("evaluation precedes completion")
                evaluation = evaluations.get(task["id"])
                expected = {"report": json.loads(evaluation["report"])} if evaluation else None
            else:
                raise IntegrityError("unknown event kind")
            if encoded(payload) != encoded(expected):
                raise IntegrityError("event/state disagreement")
            previous = row["hash"]
        for task_id, row in tasks.items():
            task = json.loads(row["payload"])
            validate_task(task)
            if s.digest(task) != task_id or ("enqueued", task_id) not in seen:
                raise IntegrityError("task payload or enqueue receipt changed")
            if row["status"] not in ("pending", "completed", "failed"):
                raise IntegrityError("invalid task state")
            if row["status"] == "pending":
                if row["result"] is not None or ("completed", task_id) in seen:
                    raise IntegrityError("pending task has a result")
            else:
                if row["result"] is None or ("completed", task_id) not in seen:
                    raise IntegrityError("task lacks completion receipt")
                result = json.loads(row["result"])
                if result.get("task_id") != task_id or result.get("status") != row["status"]:
                    raise IntegrityError("task result changed")
                if result.get("staged") and result.get("model_id") not in models:
                    raise IntegrityError("staged model missing")
        for identity, row in models.items():
            program = program_from_data(json.loads(row["program"]))
            creator = tasks.get(row["acquired_task"])
            creator_result = json.loads(creator["result"]) if creator and creator["result"] else {}
            if program.identity != identity or creator_result.get("model_id") != identity:
                raise IntegrityError("capability fingerprint/provenance changed")
        for task_id, row in evaluations.items():
            if ("evaluated", task_id) not in seen:
                raise IntegrityError("evaluation lacks receipt")
            rows, report = json.loads(row["data"]), json.loads(row["report"])
            c.validate_rows(rows, 128)
            if s.digest(rows) != report.get("data_sha256"):
                raise IntegrityError("evaluation data changed")
            task_result = json.loads(tasks[task_id]["result"])
            saved = models.get(task_result.get("model_id"))
            if not task_result.get("staged") or saved is None:
                raise IntegrityError("evaluation lacks a staged model")
            program = program_from_data(json.loads(saved["program"]))
            predictions = [program.predict(w) for w, _ in rows]
            if (report.get("model_id") != program.identity or report.get("total") != len(rows) or
                    report.get("correct") != sum(p == y for p, (_, y) in zip(predictions, rows)) or
                    report.get("predictions_sha256") != s.digest(predictions)):
                raise IntegrityError("evaluation score differs from frozen program")

    def enqueue(self, task):
        validate_task(task)
        identity = s.digest(task)
        with self._transaction():
            self._verify()
            if self.db.execute("SELECT 1 FROM tasks WHERE id=?", (identity,)).fetchone():
                return identity
            count = self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            if count >= MAX_TASKS:
                raise ValueError("task budget exhausted")
            self.db.execute("INSERT INTO tasks VALUES (?, ?, 'pending', NULL, ?)",
                            (identity, encoded(task), count + 1))
            self._append("enqueued", identity, {"task_sha256": identity})
        return identity

    def _solve(self, task_id, task):
        train, validation = task["train"], task["validation"]
        inherited = [program_from_data(json.loads(row[0]))
                     for row in self.db.execute("SELECT program FROM library ORDER BY id")]
        reuse_report, chosen, fit_report = None, None, None
        if inherited:
            chosen, reuse_report = c.select(inherited, train, validation)
        reused = bool(reuse_report and reuse_report["admitted"])
        if not reused:
            learned, fit_report = c.fit(train, validation)
            # Sertakan seluruh kandidat yang berhasil disintesis (composition + fixed_product + dfa + counter)
            all_learned = list(learned.values())
            candidates = inherited + all_learned
            chosen, selection = c.select(candidates, train, validation)
        else:
            selection = reuse_report
        identity, staged = chosen.identity, selection["admitted"]
        if staged and not self.db.execute("SELECT 1 FROM library WHERE id=?", (identity,)).fetchone():
            if self.db.execute("SELECT COUNT(*) FROM library").fetchone()[0] >= MAX_MODELS:
                raise ValueError("capability library budget exhausted")
            self.db.execute("INSERT INTO library VALUES (?, ?, ?)",
                            (identity, encoded(chosen.data()), task_id))
        return {"task_id": task_id, "name": task["name"], "status": "completed",
                "phase": "REUSE_VALIDATED" if reused else "LEARNED_STAGED" if staged else "NO_VALIDATED_MODEL",
                "staged": staged, "model_id": identity if staged else None,
                "candidate_identity": identity, "learning_called": not reused,
                "inherited_candidates": len(inherited), "inherited_selection": reuse_report,
                "selection": selection, "fit_report": fit_report,
                "train_labels": len(train), "validation_labels": len(validation),
                "implementation": self.implementation, "open_world_safe": False}

    def run(self, max_tasks=16):
        if type(max_tasks) is not int or not 1 <= max_tasks <= MAX_TASKS:
            raise ValueError("max_tasks must be an integer in 1..256")
        results = []
        for _ in range(max_tasks):
            with self._transaction():
                self._verify()
                row = self.db.execute("SELECT * FROM tasks WHERE status='pending' ORDER BY ordinal LIMIT 1").fetchone()
                if row is None:
                    break
                self.db.execute("SAVEPOINT trial")
                try:
                    result = self._solve(row["id"], json.loads(row["payload"]))
                except (ValueError, RuntimeError, OverflowError) as error:
                    self.db.execute("ROLLBACK TO trial")
                    self.db.execute("RELEASE trial")
                    result = {"task_id": row["id"], "name": json.loads(row["payload"])["name"],
                              "status": "failed", "staged": False,
                              "error": {"type": type(error).__name__, "message": str(error)}}
                else:
                    self.db.execute("RELEASE trial")
                self.db.execute("UPDATE tasks SET status=?, result=? WHERE id=?",
                                (result["status"], encoded(result), row["id"]))
                self._append("completed", row["id"], {"result": result})
                results.append(result)
        return results

    def _staged_program(self, task_id):
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None or row["result"] is None:
            raise ValueError("unknown or unfinished task")
        result = json.loads(row["result"])
        if not result.get("staged"):
            raise ValueError("task has no validated staged model")
        saved = self.db.execute("SELECT program FROM library WHERE id=?", (result["model_id"],)).fetchone()
        return program_from_data(json.loads(saved[0])), json.loads(row["payload"])

    def predict(self, task_id, word):
        with self._transaction(write=False):
            self._verify()
            program, _ = self._staged_program(task_id)
            return program.predict(word)

    def report(self, task_id):
        with self._transaction(write=False):
            self._verify()
            row = self.db.execute("SELECT result FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None or row[0] is None:
                raise ValueError("unknown or unfinished task")
            return json.loads(row[0])

    def evaluate(self, task_id, rows):
        c.validate_rows(rows, 128)
        with self._transaction():
            self._verify()
            program, task = self._staged_program(task_id)
            existing = self.db.execute("SELECT report FROM evaluations WHERE task_id=?", (task_id,)).fetchone()
            if existing:
                report = json.loads(existing[0])
                if report["data_sha256"] != s.digest(rows):
                    raise ValueError("terminal evaluation already bound to different data")
                return report
            observed = {w for w, _ in task["train"] + task["validation"]}
            if observed & {w for w, _ in rows}:
                raise ValueError("terminal data overlap training/validation")
            predictions = [program.predict(w) for w, _ in rows]
            report = {"task_id": task_id, "model_id": program.identity,
                      "data_sha256": s.digest(rows), "total": len(rows),
                      "correct": sum(p == y for p, (_, y) in zip(predictions, rows)),
                      "predictions_sha256": s.digest(predictions),
                      "scientific_decision": "NOT_ASSESSED", "candidate_deployed": False}
            self.db.execute("INSERT INTO evaluations VALUES (?, ?, ?)",
                            (task_id, encoded(rows), encoded(report)))
            self._append("evaluated", task_id, {"report": report})
        return report

    def status(self):
        with self._transaction(write=False):
            self._verify()
            tasks = []
            for row in self.db.execute("SELECT * FROM tasks ORDER BY ordinal"):
                task, result = json.loads(row["payload"]), json.loads(row["result"]) if row["result"] else {}
                tasks.append({"id": row["id"], "name": task["name"], "status": row["status"],
                              "phase": result.get("phase"), "staged": result.get("staged", False),
                              "model_id": result.get("model_id")})
            return {"schema": SCHEMA, "tasks": tasks,
                    "pending": sum(t["status"] == "pending" for t in tasks),
                    "completed": sum(t["status"] == "completed" for t in tasks),
                    "failed": sum(t["status"] == "failed" for t in tasks),
                    "capabilities": self.db.execute("SELECT COUNT(*) FROM library").fetchone()[0],
                    "evaluations": self.db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0],
                    "events": self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                    "implementation": self.implementation,
                    "scientific_decision": "NOT_ASSESSED", "oaie_established": False,
                    "candidate_deployed": False}
