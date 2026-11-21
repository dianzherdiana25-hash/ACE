"""Bangun worker lokal berantrean SQLite yang dapat dipanggil ulang.

Satu transaksi mengikat pengambilan antrean dan hasil hitung. CLI
memisahkan inisialisasi, enqueue, konsumsi terbatas dan observasi.
Identitas konfigurasi mencegah DB produk lain dibaca sebagai antreannya.
"""
import argparse
from hashlib import sha256
import keyword
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


OPERATIONS = {"sum", "minimum", "maximum", "count"}
RUNTIME = '''"""Worker background produk dengan antrean bertransaksi."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import sys
import time


JOB_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}")


class Rejected(ValueError):
    pass


def bounded_number(value):
    return type(value) is int and abs(value) <= 2 ** 63 - 1


def parse_input():
    data = sys.stdin.buffer.read(SETTINGS["max_payload_bytes"] + 1)
    if len(data) > SETTINGS["max_payload_bytes"]:
        raise Rejected("Ukuran payload melampaui batas.")
    return json.loads(data.decode("utf-8"))


def init(path):
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS worker_meta (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS jobs (seq INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, "
                           "route TEXT NOT NULL, payload TEXT NOT NULL, "
                           "state TEXT NOT NULL CHECK(state IN ('queued','done','failed')), result TEXT) STRICT")
        connection.execute("INSERT OR IGNORE INTO worker_meta VALUES (1, ?)", (SETTINGS["plan_sha256"],))
        check_db(connection)
        connection.execute("COMMIT")
    finally:
        connection.close()


def check_db(connection):
    row = connection.execute("SELECT plan FROM worker_meta WHERE id = 1").fetchone()
    if row is None or row[0] != SETTINGS["plan_sha256"]:
        raise Rejected("DB antrean memiliki identitas yang berbeda.")


@contextmanager
def connect(path, readonly=False):
    mode = "ro" if readonly else "rw"
    connection = sqlite3.connect(path.absolute().as_uri() + "?mode=" + mode, uri=True, timeout=5, isolation_level=None)
    try:
        check_db(connection)
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


def enqueue(connection, job_id, route, payload):
    if not JOB_ID.fullmatch(job_id):
        raise Rejected("ID job tidak sah.")
    if (not isinstance(payload, list) or len(payload) > SETTINGS["max_numbers"]
            or not all(bounded_number(value) for value in payload)):
        raise Rejected("Payload memerlukan array integer dalam batas.")
    serialized = encode(payload)
    with transaction(connection):
        current = connection.execute("SELECT route, payload, state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if current is not None:
            if current[:2] != (route, serialized):
                raise Rejected("ID job sudah dipakai untuk payload berbeda.")
            return {"id": job_id, "state": current[2], "reused": True}
        pending = connection.execute("SELECT count(*) FROM jobs WHERE state='queued'").fetchone()[0]
        if pending >= SETTINGS["max_pending"]:
            raise Rejected("Kapasitas antrean penuh.")
        connection.execute("INSERT INTO jobs(id,route,payload,state) VALUES(?,?,?,'queued')",
                           (job_id, route, serialized))
    return {"id": job_id, "state": "queued", "reused": False}


def handle(route, values):
    operation = SETTINGS["routes"][route]["operation"]
    if operation in {"minimum", "maximum"} and not values:
        return "failed", {"reason": "empty_operand"}
    functions = {"minimum": min, "maximum": max, "sum": sum, "count": len}
    return "done", {"value": functions[operation](values)}


def consume_one(connection):
    with transaction(connection):
        record = connection.execute("SELECT id, route, payload FROM jobs WHERE state='queued' ORDER BY seq LIMIT 1").fetchone()
        if record is None:
            return None
        job_id, route, payload = record
        state, result = handle(route, json.loads(payload))
        connection.execute("UPDATE jobs SET state=?,result=? WHERE id=?", (state, encode(result), job_id))
    return {"id": job_id, "state": state, "result": result}


def consume(path, limit, wait_seconds):
    results = []
    deadline = time.monotonic() + wait_seconds
    with connect(path) as connection:
        while len(results) < limit:
            result = consume_one(connection)
            if result is not None:
                results.append(result)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))
    return {"processed": len(results), "jobs": results}


def inspect(connection, job_id):
    if not JOB_ID.fullmatch(job_id):
        raise Rejected("ID job tidak sah.")
    row = connection.execute("SELECT route,state,result FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        return {"id": job_id, "state": "missing"}
    return {"id": job_id, "route": row[0], "state": row[1], "result": json.loads(row[2]) if row[2] else None}


def main(argv=None):
    parser = argparse.ArgumentParser(prog=SETTINGS["id"], description=SETTINGS["description"])
    parser.add_argument("--db", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    submit = commands.add_parser("enqueue")
    submit.add_argument("id")
    submit.add_argument("route", choices=sorted(SETTINGS["routes"]))
    worker = commands.add_parser("consume")
    worker.add_argument("--limit", type=int, default=20)
    worker.add_argument("--wait-seconds", type=int, default=0)
    observer = commands.add_parser("inspect")
    observer.add_argument("id")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init(args.db)
            result = {"state": "ready"}
        elif args.command == "consume":
            if not 1 <= args.limit <= 200 or not 0 <= args.wait_seconds <= 60:
                raise Rejected("Batas worker di luar rentang.")
            result = consume(args.db, args.limit, args.wait_seconds)
        elif args.command == "enqueue":
            with connect(args.db) as connection:
                result = enqueue(connection, args.id, args.route, parse_input())
        else:
            with connect(args.db, readonly=True) as connection:
                result = inspect(connection, args.id)
        print(encode(result))
    except (OSError, ValueError, RecursionError, sqlite3.Error) as error:
        print(f"Worker menolak: {error}", file=sys.stderr)
        return 2
    return int(result.get("state") == "missing")


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-service-plan.v1", ("id", "description", "max_payload_bytes", "max_numbers",
                                                "max_pending", "routes"))
    product = identifier(plan["id"], "ID worker")
    if keyword.iskeyword(product) or product in sys.stdlib_module_names:
        raise ContractError("Nama worker bertabrakan dengan Python.")
    routes = {}
    for row in entries(plan["routes"], 30, minimum=1):
        obj(row, ("id", "operation", "source_ref"))
        key = identifier(row["id"], "ID route")
        op = row["operation"]
        if key in routes or not isinstance(op, str) or op not in OPERATIONS:
            raise ContractError("Route ganda atau operasi belum didukung.")
        routes[key] = {"operation": op, "source_ref": text(row["source_ref"], "Rujukan route", 200)}
    config = {"id": product, "description": text(plan["description"], "Deskripsi worker", 200),
              "plan_sha256": expected, "routes": dict(sorted(routes.items())),
              "max_payload_bytes": integer(plan["max_payload_bytes"], "Batas byte", 16, 100_000),
              "max_numbers": integer(plan["max_numbers"], "Batas operand", 1, 5000),
              "max_pending": integer(plan["max_pending"], "Kapasitas antrean", 1, 10_000)}
    module = f"{product}/__main__.py"
    runtime = RUNTIME.replace("import time\n", f"import time\n\nSETTINGS = {config!r}\n", 1).encode()
    report = {"schema": "ace.factory-service-build.v1", "plan_sha256": expected, "product_id": product,
              "entrypoint": ["python3", "-m", product], "queue": "sqlite", "delivery": "local_atomic",
              "routes": [{"id": key, **value} for key, value in sorted(routes.items())],
              "runtime": {"path": module, "sha256": sha256(runtime).hexdigest()}}
    return {f"{product}/__init__.py": b"", module: runtime, "service_manifest.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
