"""Jaga sumber baris dan nilai kosong pada analisis CSV lokal."""
from dataclasses import dataclass
from csv import reader
from hashlib import sha256
from io import StringIO

from ._contracts import ResearchError, day, digest, fmt, identifier, integer, items, number, obj, text


TYPES = ("integer", "decimal", "category", "text", "date")
NUMBERS = ("integer", "decimal")


@dataclass(frozen=True)
class Table:
    columns: dict
    rows: tuple
    rejected: tuple
    sha256: str


def _spec(value):
    obj(value, ("name", "kind", "nullable", "normalize", "minimum", "maximum"))
    name = identifier(value["name"], "Kolom")
    kind = value["kind"]
    if kind not in TYPES or type(value["nullable"]) is not bool:
        raise ResearchError("Tipe atau nullable kolom belum didukung.")
    normalization = value["normalize"]
    if normalization not in ("exact", "strip", "casefold") or (normalization == "casefold" and kind not in ("category", "text")):
        raise ResearchError("Normalisasi kolom tidak sesuai tipe.")
    floor = None if value["minimum"] is None else number(value["minimum"], "Minimum kolom")
    ceiling = None if value["maximum"] is None else number(value["maximum"], "Maksimum kolom")
    if ((floor is not None or ceiling is not None) and kind not in NUMBERS
            or (floor is not None and ceiling is not None and floor > ceiling)):
        raise ResearchError("Rentang data kolom tidak sah.")
    return name, (kind, value["nullable"], normalization, floor, ceiling)


def decode_value(raw, spec):
    kind, nullable, normalization, floor, ceiling = spec
    value = raw if normalization == "exact" else raw.strip()
    if normalization == "casefold":
        value = value.casefold()
    if not value:
        if nullable:
            return None
        raise ResearchError("missing_required")
    if kind in NUMBERS:
        outcome = number(value, "Angka CSV")
        if kind == "integer" and outcome % 1 != 0:
            raise ResearchError("non_integer")
        if floor is not None and outcome < floor or ceiling is not None and outcome > ceiling:
            raise ResearchError("out_of_range")
        return outcome
    if kind == "date":
        return day(value)
    return text(value, "Data teks", 600)


def serialize(value, spec):
    if value is None:
        return ""
    if spec[0] in NUMBERS:
        return fmt(value)
    if spec[0] == "date":
        return value.isoformat()
    return str(value)


def load(raw, expected, plan):
    if not isinstance(raw, bytes) or len(raw) > 3_000_000 or sha256(raw).hexdigest() != digest(expected):
        raise ResearchError("CSV berbeda dari anchor atau melewati batas.")
    obj(plan, ("columns", "max_rows"))
    maximum = integer(plan["max_rows"], "Batas jumlah baris", 1, 100_000)
    declarations = dict(_spec(item) for item in items(plan["columns"], 80, 1))
    if len(declarations) != len(plan["columns"]):
        raise ResearchError("Deklarasi kolom CSV ganda.")
    csv = reader(StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if next(csv, None) != list(declarations):
        raise ResearchError("Header CSV tidak sama dengan urutan deklarasi.")
    records = []
    rejected = []
    previous = csv.line_num
    for index, current in enumerate(csv, 1):
        line = previous + 1
        previous = csv.line_num
        if index > maximum:
            raise ResearchError("Jumlah baris CSV melebihi batas.")
        if len(current) != len(declarations):
            rejected.append({"line": line, "end_line": previous, "issues": [{"column": None, "reason": "wrong_field_count"}]})
            continue
        mapped = {}
        normalized = []
        issues = []
        for (name, spec), value in zip(declarations.items(), current, strict=True):
            try:
                decoded = decode_value(value, spec)
                if serialize(decoded, spec) != value:
                    normalized.append(name)
                mapped[name] = decoded
            except ResearchError as error:
                issues.append({"column": name, "reason": str(error)})
        if issues:
            rejected.append({"line": line, "end_line": previous, "issues": issues})
        else:
            records.append({"line": line, "end_line": previous, "cells": mapped, "normalized": normalized})
    return Table(declarations, tuple(records), tuple(rejected), expected)


def values(table, field, *, numeric=False):
    if field not in table.columns or numeric and table.columns[field][0] not in NUMBERS:
        raise ResearchError("Kolom analisis tidak terdaftar atau tidak numerik.")
    return [row["cells"][field] for row in table.rows if row["cells"][field] is not None]


def quantile(series, numerator, denominator):
    if not series:
        return None
    ordered = sorted(series)
    index, fraction = divmod((len(series) - 1) * numerator, denominator)
    if not fraction:
        return ordered[index]
    return (ordered[index] * (denominator - fraction) + ordered[index + 1] * fraction) / denominator
