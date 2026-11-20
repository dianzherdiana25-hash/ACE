"""Pembacaan dan representasi kanonis agar hash fixture dapat direproduksi."""
import hashlib
import json
from pathlib import Path
import re


class InputError(ValueError):
    """Skema atau bukti masukan tidak cocok."""


def object_fields(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise InputError("Field tidak cocok dengan skema.")


def string(raw, label, *, max_chars=256, preserve=False):
    if not isinstance(raw, str) or not raw.strip() or "\0" in raw or len(raw) > max_chars:
        raise InputError(f"{label} tidak sah.")
    try:
        raw.encode("utf-8")
    except UnicodeError as exc:
        raise InputError(f"{label} bukan teks UTF-8.") from exc
    return raw if preserve else raw.strip()


def digest(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[a-f0-9]{64}", raw):
        raise InputError("SHA-256 harus ditulis sebagai 64 digit hex lowercase.")
    return raw


def entries(raw, maximum):
    if not isinstance(raw, list) or len(raw) > maximum:
        raise InputError("Daftar record tidak sah atau melebihi batas.")
    return raw


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise InputError(f"Angka harus integer di rentang {low}–{high}.")
    return value


def canonical(raw):
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def identity(raw):
    return hashlib.sha256(canonical(raw)).hexdigest()


def _parse(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("Kunci JSON ganda.")
        result[key] = value
    return result


def _reject_constant(value):
    raise InputError(f"Konstanta JSON non-finite {value}.")


def decode(buffer):
    return json.loads(buffer.decode("utf-8"), object_pairs_hook=_parse, parse_constant=_reject_constant)


def read_bytes(path: Path, maximum):
    with path.open("rb") as source:
        payload = source.read(maximum + 1)
    if len(payload) > maximum:
        raise InputError("Berkas masukan melebihi batas byte.")
    return payload
