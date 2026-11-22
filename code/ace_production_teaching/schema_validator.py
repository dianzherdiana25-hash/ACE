"""Validasi data bertingkat dan laporkan lokasi cacat tanpa mencetak nilai masukan."""
from decimal import Decimal
from math import isfinite
import re

from ._contracts import ProductionError, anchor, cli, day, decode, digest, integer, items, obj, schema, source_bytes


KINDS = {"object", "array", "integer", "number", "string", "boolean", "null"}
IDENT = re.compile(r"[a-z][a-z0-9_]{0,63}")


def _format(value, identifier):
    if identifier == "id":
        return IDENT.fullmatch(value) is not None
    try:
        (day if identifier == "date" else digest)(value)
        return True
    except ProductionError:
        return False


def _definition(raw, depth=0):
    if not isinstance(raw, dict) or depth > 20 or not isinstance(raw.get("type"), str) or raw.get("type") not in KINDS:
        raise ProductionError("Definisi schema bertipe wajib dan kedalaman maksimum 20.")
    kind = raw["type"]
    allowed = {"object": {"properties", "required", "additional"},
               "array": {"items", "min_items", "max_items"}, "string": {"min_len", "max_len", "format"},
               "integer": {"min", "max"}, "number": {"min", "max"}, "boolean": set(), "null": set()}
    if raw.keys() - {"type", "enum"} - allowed[kind]:
        raise ProductionError("Kata kunci schema tidak didukung.")
    if "enum" in raw:
        notice = items(raw["enum"], 60, 1)
        if any(isinstance(item, (dict, list)) for item in notice):
            raise ProductionError("Enum schema dibatasi pada nilai skalar.")
    if kind == "object":
        properties = raw.get("properties", {})
        required = items(raw.get("required", []), 100)
        if not isinstance(properties, dict) or len(properties) > 120 or any(not isinstance(name, str) for name in required):
            raise ProductionError("Properties atau required tidak sah.")
        if not set(required) <= properties.keys() or type(raw.get("additional", False)) is not bool:
            raise ProductionError("Required menunjuk property tak dikenal atau additional tidak boolean.")
        for item in properties.values():
            _definition(item, depth + 1)
    if kind == "array":
        _definition(raw.get("items"), depth + 1)
    if kind in ("string", "array"):
        a, b = ("min_len", "max_len") if kind == "string" else ("min_items", "max_items")
        low = integer(raw.get(a, 0), a, 0, 1000000)
        integer(raw.get(b, 1000000), b, low, 1000000)
    if kind == "string" and raw.get("format", "id") not in ("id", "date", "sha256"):
        raise ProductionError("Format string schema belum didukung.")
    if kind in ("integer", "number"):
        bounds = [raw[key] for key in ("min", "max") if key in raw]
        if any(type(value) not in (int, float) or isinstance(value, float) and not isfinite(value) for value in bounds):
            raise ProductionError("Minimum dan maksimum harus angka finite.")
        if len(bounds) == 2 and bounds[0] > bounds[1]:
            raise ProductionError("Rentang minimum/maksimum terbalik.")


def _segment(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def _compare(value, spec, path, defects):
    if len(defects) >= 2000:
        return
    at = lambda reason: defects.append({"path": path, "rule": reason})
    kind = spec["type"]
    match = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "integer": type(value) is int, "number": type(value) in (int, float),
             "string": isinstance(value, str), "boolean": type(value) is bool, "null": value is None}
    if not match[kind]:
        at("type")
        return
    if "enum" in spec and not any(type(val) is type(value) and val == value for val in spec["enum"]):
        at("enum")
    if kind == "object":
        properties = spec.get("properties", {})
        for field in sorted(set(spec.get("required", [])) - value.keys()):
            defects.append({"path": path + "/" + _segment(field), "rule": "required"})
        for key, item in sorted(value.items()):
            child = path + "/" + _segment(key)
            if key in properties:
                _compare(item, properties[key], child, defects)
            elif not spec.get("additional", False):
                defects.append({"path": child, "rule": "additional"})
            if len(defects) >= 2000:
                break
    elif kind == "array":
        if not spec.get("min_items", 0) <= len(value) <= spec.get("max_items", 1_000_000):
            at("array_size")
        for index, item in enumerate(value):
            _compare(item, spec["items"], path + "/" + str(index), defects)
            if len(defects) >= 2000:
                break
    elif kind == "string":
        if not spec.get("min_len", 0) <= len(value) <= spec.get("max_len", 1_000_000):
            at("string_length")
        if "format" in spec and not _format(value, spec["format"]):
            at("format")
    elif kind == "number" or kind == "integer":
        if isinstance(value, float) and not isfinite(value):
            at("nonfinite")
        elif ("min" in spec and Decimal(str(value)) < Decimal(str(spec["min"]))) or (
                "max" in spec and Decimal(str(value)) > Decimal(str(spec["max"]))):
            at("range")


def validate(data, structure):
    _definition(structure)
    findings = []
    _compare(data, structure, "", findings)
    return {"valid": not findings, "errors": findings[:2000], "truncated": len(findings) >= 2000}


def inspect_plan(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.schema-check-plan.v1", ("value", "definition"))
    location = obj(plan["value"], ("path", "sha256"))
    raw = source_bytes(root, location["path"], location["sha256"], 2_000_000)
    return {"schema": "ace.production.schema-check.v1", "plan_sha256": expected,
            "input": location, **validate(decode(raw), plan["definition"])}


if __name__ == "__main__":
    raise SystemExit(cli(inspect_plan, __doc__, rooted=True))
