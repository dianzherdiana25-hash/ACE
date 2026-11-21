"""Bangun panel admin dengan boundary izin pada render dan mutasi produk.

Runtime memanggil pemeriksa izin host dan hanya menampilkan kolom yang
terdaftar. Handler aksi membutuhkan izin kembali dan CSRF yang cocok
sebelum memanggil callback dari host. Panel tidak memulai server.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


PATH = re.compile(r"/[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*")
RUNTIME = '''"""Panel admin lokal; host memasok izin, data, nonce dan handler."""
from hmac import compare_digest
from html import escape
import re


ROW_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}")


class Forbidden(PermissionError):
    pass


def _allowed(authorize, token, permission):
    if authorize(token, permission) is not True:
        raise Forbidden("Akses panel ditolak.")


def _value(raw):
    if raw is None:
        return "—"
    if type(raw) not in (str, int, bool) or len(str(raw)) > 400:
        raise ValueError("Nilai kolom tidak sah.")
    return escape(str(raw))


def _row_id(raw):
    if not isinstance(raw, str) or not ROW_ID.fullmatch(raw):
        raise ValueError("ID record tidak sah.")
    return raw


def _nonce(raw):
    if not isinstance(raw, str) or not 16 <= len(raw) <= 200 or not raw.isascii() or not raw.isprintable():
        raise ValueError("Nonce panel tidak sah.")
    return raw


class Panel:
    def __init__(self, authorize):
        self._authorize = authorize

    def render(self, view, token, rows, csrf):
        spec = CONFIG["views"][view]
        _allowed(self._authorize, token, spec["permission"])
        if not isinstance(rows, list) or len(rows) > 200:
            raise ValueError("Jumlah record panel di luar batas.")
        nonce = escape(_nonce(csrf), quote=True)
        columns = spec["columns"]
        actions = [row for row in spec["actions"] if self._authorize(token, row["permission"]) is True]
        header = "".join(f"<th scope='col'>{escape(c['label'])}</th>" for c in columns)
        if actions:
            header += "<th scope='col'>Tindakan</th>"
        body = []
        seen = set()
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("Record panel perlu objek.")
            key = _row_id(item.get(spec["key"]))
            if key in seen:
                raise ValueError("ID record panel ganda.")
            seen.add(key)
            if any(column["id"] not in item for column in columns):
                raise ValueError("Record panel kurang kolom.")
            cells = "".join(f"<td>{_value(item[column['id']])}</td>" for column in columns)
            if actions:
                forms = []
                for action in actions:
                    forms.append(f"<form method='post' action='{action['route']}'>"
                                 f"<input type='hidden' name='record_id' value='{key}'>"
                                 f"<input type='hidden' name='csrf' value='{nonce}'>"
                                 f"<button type='submit' aria-label='{escape(action['label'])} {key}'>"
                                 f"{escape(action['label'])}</button></form>")
                cells += "<td>" + "".join(forms) + "</td>"
            body.append("<tr>" + cells + "</tr>")
        title = escape(spec["title"])
        return ("<!doctype html><html lang='id'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title>"
                "<style>body{font:1rem system-ui;margin:2rem;color:#17212c;background:#f7f9fc}"
                "main{max-width:72rem;margin:auto}table{width:100%;border-collapse:collapse;background:white}"
                "th,td{padding:.8rem;border-bottom:1px solid #ccd6e0;text-align:left}"
                "form{display:inline-block;margin:.2rem}button{padding:.5rem .7rem}</style></head>"
                f"<body><main><h1>{title}</h1><table aria-label='{title}'><thead><tr>{header}</tr></thead>"
                f"<tbody>{''.join(body)}</tbody></table></main></body></html>")

    def dispatch(self, view, action_id, token, row_id, csrf, expected_nonce, handler):
        spec = CONFIG["views"][view]
        _allowed(self._authorize, token, spec["permission"])
        action = next((row for row in spec["actions"] if row["id"] == action_id), None)
        if action is None:
            raise Forbidden("Aksi panel ditolak.")
        _allowed(self._authorize, token, action["permission"])
        if not compare_digest(_nonce(csrf), _nonce(expected_nonce)):
            raise Forbidden("Aksi panel ditolak.")
        return handler(view, action["id"], _row_id(row_id))
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-admin-plan.v1", ("id", "source_ref", "views"))
    product = identifier(plan["id"], "ID produk")
    ref = text(plan["source_ref"], "Sumber panel")
    output = {}
    all_routes = set()
    for raw in entries(plan["views"], 30, minimum=1):
        obj(raw, ("id", "title", "key", "permission", "columns", "actions", "source_ref"))
        key = identifier(raw["id"], "ID tampilan")
        if key in output:
            raise ContractError("Tampilan ganda.")
        columns = {}
        for row in entries(raw["columns"], 30, minimum=1):
            obj(row, ("id", "label"))
            column = identifier(row["id"], "ID kolom")
            if column in columns:
                raise ContractError("Kolom ganda.")
            columns[column] = {"id": column, "label": text(row["label"], "Label kolom", 80)}
        row_key = identifier(raw["key"], "Field ID record")
        if row_key not in columns:
            raise ContractError("ID record harus menjadi kolom terdaftar.")
        actions = {}
        for row in entries(raw["actions"], 15):
            obj(row, ("id", "label", "permission", "route", "source_ref"))
            action = identifier(row["id"], "ID tindakan")
            route = text(row["route"], "Rute tindakan", 150)
            if action in actions or not PATH.fullmatch(route) or route in all_routes:
                raise ContractError("Tindakan ganda, rute ganda atau rute tidak lokal.")
            all_routes.add(route)
            actions[action] = {"id": action, "label": text(row["label"], "Label tindakan", 80),
                               "route": route, "permission": identifier(row["permission"], "Izin tindakan"),
                               "source_ref": text(row["source_ref"], "Sumber tindakan")}
        output[key] = {"title": text(raw["title"], "Judul tampilan", 110), "key": row_key,
                       "permission": identifier(raw["permission"], "Izin baca panel"), "columns": list(columns.values()),
                       "actions": [actions[name] for name in sorted(actions)],
                       "source_ref": text(raw["source_ref"], "Sumber tampilan")}
    views = dict(sorted(output.items()))
    runtime = RUNTIME.replace("import re\n", f"import re\n\nCONFIG = {{'views': {views!r}}}\n", 1).encode()
    report = {"schema": "ace.factory-admin-build.v1", "plan_sha256": expected, "product_id": product, "source_ref": ref,
              "views": [{"id": key, "permission": view["permission"], "source_ref": view["source_ref"],
                         "actions": [row["id"] for row in view["actions"]]} for key, view in views.items()],
              "runtime": {"path": "product_admin.py", "sha256": sha256(runtime).hexdigest()}}
    return {"product_admin.py": runtime, "admin_manifest.json": canonical(report) + b"\n"}, report


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
