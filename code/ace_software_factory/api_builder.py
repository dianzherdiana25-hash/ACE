"""Bangun API JSON SQLite dari model data dan batas operasi eksplisit.

Generator memvalidasi nama resource, tipe kolom, dan metode
sebelum membuat backend. SQL runtime memakai parameter. Server
yang dihasilkan memakai loopback dan berkas database yang baru
atau terbukti memiliki identitas skema produk yang sama.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import schema_designer
from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, obj, read, schema, text
from .repo_scaffolder import materialize


METHODS = {"GET", "POST", "PATCH", "DELETE"}
CELL_TYPES = {"text", "integer", "boolean"}

RUNTIME = r'''"""Backend JSON dari kontrak factory terverifikasi."""
import argparse
from base64 import b64encode
from hashlib import sha256
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit


DIRECTORY = Path(__file__).resolve().parent
CONTRACT = json.loads((DIRECTORY/"api.json").read_text(encoding="utf-8"))
SCHEMA = (DIRECTORY/"schema.sql").read_text(encoding="utf-8")
MAX_BODY = 128_000
ROUTE = re.compile(r"/([a-z][a-z0-9_]{0,63})(?:/([0-9]{1,19}))?")


class RequestError(ValueError):
    def __init__(self, code, message):
        self.code, self.message = code, message


def _json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RequestError(400, "duplicate_fields")
        result[key] = value
    return result


def _open(path):
    db = sqlite3.connect(path, timeout=3)
    db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    return db


def initialize(path):
    try:
        with path.open("xb"):
            pass
    except FileExistsError:
        with closing(_open(path)) as db:
            result = db.execute("SELECT schema_sha256 FROM _factory_api_identity").fetchone()
            if result is None or result[0] != CONTRACT["model_sha256"]:
                raise ValueError("Identitas database tidak sesuai.")
        return
    try:
        with closing(_open(path)) as db, db:
            db.executescript(SCHEMA)
            db.execute("CREATE TABLE _factory_api_identity (schema_sha256 TEXT NOT NULL)")
            db.execute("INSERT INTO _factory_api_identity VALUES (?)", (CONTRACT["model_sha256"],))
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _quote(column):
    return '"' + column + '"'


def _values(data, spec):
    if not isinstance(data, dict) or not set(data) <= set(spec["write"]):
        raise RequestError(400, "unexpected_fields")
    result = {}
    for field, value in sorted(data.items()):
        column = spec["columns"][field]
        kind = column["kind"]
        valid = (
            value is None and column["nullable"]
            or kind == "text" and isinstance(value, str) and len(value) <= 16384
            or kind == "integer" and type(value) is int and -2**63 <= value < 2**63
            or kind == "boolean" and type(value) is bool
        )
        if not valid:
            raise RequestError(400, "wrong_field_type")
        result[field] = value
    return result


def _show(row, spec):
    if row is None:
        raise RequestError(404, "record_missing")
    result = dict(row)
    for key, value in result.items():
        if value is not None and spec["columns"][key]["kind"] == "boolean":
            result[key] = bool(value)
    return result


def _pagination(raw):
    values = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=4) if raw else {}
    if set(values)-{"limit","offset"} or any(len(items) != 1 for items in values.values()):
        raise RequestError(400, "bad_pagination")
    cap, start = (values.get(field, [default])[0] for field, default in (("limit","50"),("offset","0")))
    if not cap.isascii() or not start.isascii() or not cap.isdigit() or not start.isdigit() or max(len(cap),len(start)) > 8:
        raise RequestError(400, "bad_pagination")
    cap,start = int(cap),int(start)
    if not 1 <= cap <= 200 or start > 1000000:
        raise RequestError(400, "bad_pagination")
    return cap,start


def dispatch(db, method, url, body):
    split = urlsplit(url)
    matched = ROUTE.fullmatch(split.path)
    if not matched or split.netloc or split.scheme or split.fragment:
        raise RequestError(404,"route_unknown")
    resource, literal = matched.groups()
    spec = CONTRACT["resources"].get(resource)
    if spec is None:
        raise RequestError(404,"route_unknown")
    if method not in spec["methods"] or (method == "POST" and literal is not None) or (
            method in {"PATCH","DELETE"} and literal is None):
        raise RequestError(405,"method_not_allowed")
    row_id = int(literal) if literal is not None else None
    if row_id is not None and not 1 <= row_id < 2**63:
        raise RequestError(400,"bad_record_id")
    table, pk = _quote(spec["table"]), _quote(spec["primary"])
    fields = ", ".join(map(_quote,spec["read"]))
    collection = f"SELECT {fields} FROM {table}"
    one = collection+f" WHERE {pk}=?"
    if method == "GET" and row_id is None:
        limit, offset = _pagination(split.query)
        rows = db.execute(collection+f" ORDER BY {pk} LIMIT ? OFFSET ?",(limit,offset))
        return 200, {"items":[_show(item,spec) for item in rows],"limit":limit,"offset":offset}
    if split.query:
        raise RequestError(400,"query_not_supported")
    if method == "GET":
        return 200,_show(db.execute(one,(row_id,)).fetchone(),spec)
    if method == "DELETE":
        change=db.execute(f"DELETE FROM {table} WHERE {pk}=?",(row_id,))
        if not change.rowcount:
            raise RequestError(404,"record_missing")
        return 200,{"deleted":row_id}
    data=_values(body,spec)
    if method == "POST":
        if data:
            keys=", ".join(map(_quote,data))
            places=", ".join("?" for _ in data)
            change=db.execute(f"INSERT INTO {table} ({keys}) VALUES ({places})",tuple(data.values()))
        else:
            change=db.execute(f"INSERT INTO {table} DEFAULT VALUES")
        return 201,_show(db.execute(one,(change.lastrowid,)).fetchone(),spec)
    if not data:
        raise RequestError(400,"empty_patch")
    changes=", ".join(_quote(key)+"=?" for key in data)
    db.execute(f"UPDATE {table} SET {changes} WHERE {pk}=?",(*data.values(),row_id))
    return 200,_show(db.execute(one,(row_id,)).fetchone(),spec)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _homepage(self):
        page=self.server.home_page
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(page)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Security-Policy",self.server.home_csp)
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(page)

    def _serve(self):
        try:
            host=self.headers.get("Host","")
            if host != f"127.0.0.1:{self.server.server_port}":
                raise RequestError(400,"bad_host")
            if self.headers.get("Transfer-Encoding"):
                raise RequestError(400,"unsupported_transfer")
            if self.path == "/" and self.command == "GET" and self.server.home_page is not None:
                self._homepage()
                return
            data=None
            if self.command in {"POST","PATCH"}:
                cap=self.headers.get("Content-Length","")
                if not cap.isascii() or not cap.isdigit() or len(cap)>6 or not 0 < int(cap) <= MAX_BODY:
                    raise RequestError(413,"body_size")
                if self.headers.get_content_type() != "application/json":
                    raise RequestError(415,"json_required")
                raw=self.rfile.read(int(cap))
                data=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique)
            with closing(_open(self.server.database)) as db,db:
                code,result=dispatch(db,self.command,self.path,data)
        except RequestError as exc:
            code,result=exc.code,{"error":exc.message}
        except (ValueError,UnicodeError,OverflowError,RecursionError):
            code,result=400,{"error":"invalid_input"}
        except sqlite3.IntegrityError:
            code,result=409,{"error":"constraint_conflict"}
        except sqlite3.Error:
            code,result=503,{"error":"database_unavailable"}
        payload=_json(result)
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(payload)

    do_GET=_serve
    do_POST=_serve
    do_PATCH=_serve
    do_DELETE=_serve


def _csp(page):
    data={"script-src": [], "style-src": []}
    for tag, directive in (("script","script-src"), ("style","style-src")):
        for payload in re.findall(rb"<"+tag.encode()+rb">(.+?)</"+tag.encode()+rb">",page,re.S):
            data[directive].append("'sha256-"+b64encode(sha256(payload).digest()).decode()+"'")
    return ("default-src 'none'; base-uri 'none'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; "
            +"; ".join(key+" "+(" ".join(values) or "'none'") for key,values in data.items()))


def server(database,port=0,home_page=None):
    if home_page is not None and (not isinstance(home_page,bytes) or len(home_page)>750_000):
        raise ValueError("Halaman produk terlalu besar atau bukan byte.")
    initialize(database)
    endpoint=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    endpoint.database=database
    endpoint.home_page=home_page
    endpoint.home_csp=_csp(home_page) if home_page is not None else None
    return endpoint


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    parser.add_argument("--port",type=int,default=8000)
    parser.add_argument("--home-page",type=Path)
    args=parser.parse_args(argv)
    home_page=None
    if args.home_page:
        with args.home_page.open("rb") as stream:
            home_page=stream.read(750_001)
    with server(args.database,args.port,home_page=home_page) as endpoint:
        try:
            endpoint.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__=="__main__":
    main()
'''


def _fields(raw, columns, title):
    ids = [identifier(item, title) for item in entries(raw, 96)]
    if len(set(ids)) != len(ids) or any(key not in columns or columns[key]["kind"] not in CELL_TYPES for key in ids):
        raise ContractError("Kolom resource ganda, tak dikenal, atau tak didukung JSON.")
    return ids


def build(model, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-api-plan.v1", ("model_sha256", "resources", "plan_ref"))
    relational = schema_designer.design(model, plan["model_sha256"])
    known = {row["name"]: row for row in relational["entities"]}
    resources = {}
    for row in entries(plan["resources"], 128, minimum=1):
        obj(row, ("route", "table", "read", "write", "methods", "source_ref"))
        key = identifier(row["route"], "Nama rute")
        table = identifier(row["table"], "Nama tabel")
        entity = known.get(table)
        if entity is None or key in resources:
            raise ContractError("Tabel belum dikenal atau rute ganda.")
        columns = {item["name"]: item for item in entity["columns"]}
        primary = entity["primary_key"]
        if len(primary) != 1 or columns[primary[0]]["kind"] != "integer":
            raise ContractError("Resource membutuhkan satu kunci primer integer.")
        visible = _fields(row["read"], columns, "Kolom terlihat")
        writable = _fields(row["write"], columns, "Kolom tulis")
        methods = [text(item, "Metode", 8) for item in entries(row["methods"], 4, minimum=1)]
        if (primary[0] not in visible or primary[0] in writable or set(methods)-METHODS
                or len(set(methods)) != len(methods)):
            raise ContractError("Metode ganda, ID tidak terlihat, atau ID ikut ditulis.")
        resources[key] = {"table": table, "primary": primary[0], "read": visible, "write": writable,
                          "methods": sorted(methods), "source_ref": text(row["source_ref"],"Rujukan resource",200),
                          "columns": {name:columns[name] for name in sorted(set(visible)|set(writable))}}
    result = {"schema":"ace.factory-generated-api.v1","plan_sha256":expected,
              "model_sha256":relational["model_sha256"],"plan_ref":text(plan["plan_ref"],"Rujukan rencana",200),
              "resources":resources}
    files = {"backend.py": RUNTIME.encode(), "api.json": canonical(result)+b"\n", "schema.sql": relational["sql"].encode()}
    return files, {**result,"files":[{"path":name,"sha256":sha256(value).hexdigest()} for name,value in sorted(files.items())]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("model","plan","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.model)),decode(read(args.plan)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
