"""Validasi bersama untuk alat analisis offline lanjutan."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _stamp


class InputError(ValueError):
    """Catatan masukan tidak dapat dipakai sebagai bukti terstruktur."""


def shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise InputError("Field masukan tidak sesuai skema.")


def text(value, label, limit=512):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or "\0" in value):
        raise InputError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise InputError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise InputError(f"Diperlukan integer antara {lower} dan {upper}.")
    return value


def rows(raw, lower, upper):
    if not isinstance(raw, list) or not lower <= len(raw) <= upper:
        raise InputError(f"Jumlah record harus antara {lower} dan {upper}.")
    return raw


def labels(raw, lower, upper, label="ID"):
    result = [text(value, label) for value in rows(raw, lower, upper)]
    if len(set(result)) != len(result):
        raise InputError(f"{label} ganda.")
    return result


def unique(value, seen, label="Rujukan"):
    if value in seen:
        raise InputError(f"{label} ganda.")
    seen.add(value)
    return value


def probability(raw):
    shape(raw, ("numerator", "denominator"))
    denominator = integer(raw["denominator"], 1, 10**9)
    return Fraction(integer(raw["numerator"], 0, denominator), denominator)


def stamp(value):
    try:
        return _stamp(value)
    except ValueError as exc:
        raise InputError("Cap waktu harus ISO 8601 berzona.") from exc


def read(path, limit):
    with path.open("rb") as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise InputError("Berkas masukan melampaui batas.")
    return json.loads(payload)


def json_main(argv, doc, transform, *, max_bytes=8_000_000):
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        result = transform(read(args.input, max_bytes))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0
