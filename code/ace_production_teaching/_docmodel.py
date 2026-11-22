"""Bentukkan templat dokumen agar semua placeholder dan batas tabel dapat diaudit."""
import re

from ._contracts import ProductionError, identifier, integer, items, obj, text


PLACEHOLDER = re.compile(r"\{\{([a-z][a-z0-9_]{0,63})\}\}")


def bind(value, bindings, used, limit=1400):
    raw = text(value, "Teks templat", limit)
    for key in PLACEHOLDER.findall(raw):
        if key not in bindings:
            raise ProductionError(f"Placeholder {key} tidak diisi.")
        used.add(key)
    resolved = PLACEHOLDER.sub(lambda item: bindings[item[1]], raw)
    if "{{" in resolved or "}}" in resolved:
        raise ProductionError("Token templat belum selesai diisi.")
    return text(resolved, "Teks setelah substitusi", limit)


def document_title(title, bindings, used):
    return bind(title, bindings, used, limit=180)


def document_blocks(raw, bindings, used):
    results = []
    for block in items(raw, 400, 1):
        if not isinstance(block, dict):
            raise ProductionError("Blok dokumen harus berupa objek.")
        kind = block.get("kind")
        if kind in ("heading", "paragraph"):
            columns = ("kind", "body", "level") if kind == "heading" else ("kind", "body")
            obj(block, columns)
            result = {"kind": kind, "body": bind(block["body"], bindings, used)}
            if kind == "heading":
                result["level"] = integer(block["level"], "Tingkat heading", 1, 5)
        elif kind == "break":
            obj(block, ("kind",))
            result = {"kind": kind}
        elif kind == "table":
            obj(block, ("kind", "columns", "rows"))
            columns = [bind(value, bindings, used, limit=180) for value in items(block["columns"], 10, 1)]
            if len(set(columns)) != len(columns):
                raise ProductionError("Nama kolom dokumen ganda.")
            rows = []
            for row in items(block["rows"], 80):
                if not isinstance(row, list) or len(row) != len(columns):
                    raise ProductionError("Lebar baris tabel dokumen tidak sama.")
                rows.append([bind(value, bindings, used, limit=180) if value != "" else "" for value in row])
            result = {"kind": kind, "columns": columns, "rows": rows}
        else:
            raise ProductionError("Jenis blok templat tidak didukung.")
        results.append(result)
    return results


def prepare_document(plan):
    variables = {}
    for row in items(plan["bindings"], 100):
        obj(row, ("id", "value", "source_ref"))
        key = identifier(row["id"], "Binding")
        if key in variables:
            raise ProductionError("ID binding templat ganda.")
        variables[key] = {"value": text(row["value"], "Nilai templat", 300),
                          "source_ref": text(row["source_ref"], "Rujukan templat")}
    bindings = {key: row["value"] for key, row in variables.items()}
    used = set()
    title = document_title(plan["title"], bindings, used)
    blocks = document_blocks(plan["blocks"], bindings, used)
    if used != variables.keys():
        raise ProductionError("Ada binding yang tidak dipakai pada dokumen.")
    return title, blocks, {key: row["source_ref"] for key, row in sorted(variables.items())}
