"""Validasi kontrak, hash, dan origin loopback untuk laboratorium web."""
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit


ID = re.compile(r"[a-z][a-z0-9_]{0,63}")
SHA256 = re.compile(r"[0-9a-f]{64}")
WEB_PATH = re.compile(r"/(?:[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,79}(?:/[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,79})*/?)?")


class ContractError(ValueError):
    """Data tidak memenuhi batas yang disetujui."""


def canonical(record):
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def identity(record):
    return sha256(canonical(record)).hexdigest()


def digest(value):
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ContractError("Anchor perlu SHA-256 kanonis.")
    return value


def checked(record, expected):
    if digest(expected) != identity(record):
        raise ContractError("Isi kontrak berbeda dari anchor.")


def obj(record, fields):
    if not isinstance(record, dict) or record.keys() != set(fields):
        raise ContractError("Kolom kontrak tidak sesuai.")
    return record


def schema(record, name, fields):
    obj(record, ("schema", *fields))
    if record["schema"] != name:
        raise ContractError("Schema tidak didukung.")
    return record


def entries(record, maximum, minimum=0):
    if not isinstance(record, list) or not minimum <= len(record) <= maximum:
        raise ContractError("Ukuran daftar di luar batas.")
    return record


def identifier(value, label):
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        raise ContractError(f"{label} perlu identifier.")
    return value


def text(value, label, maximum=400):
    if not isinstance(value, str) or not value.strip() or not value.isprintable() or len(value) > maximum:
        raise ContractError(f"{label} perlu teks cetak berbatas.")
    return value


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(f"{label} di luar batas.")
    return value


def _unique(pairs):
    parsed = {}
    for key, value in pairs:
        if key in parsed:
            raise ContractError("Kunci JSON ganda.")
        parsed[key] = value
    return parsed


def _invalid_constant(token):
    raise ContractError("Angka nonfinite tidak didukung.")


def decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_invalid_constant)


def read(path, limit=2_000_000):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ContractError("Masukan melebihi batas byte.")
    return data


def origin(value):
    value = text(value, "Origin", 40)
    parsed = urlsplit(value)
    port = parsed.port
    if port is None or not 1024 <= port <= 65535 or value != f"http://127.0.0.1:{port}":
        raise ContractError("Origin harus HTTP IPv4 loopback dengan port nonprivileged.")
    return value, port


def web_path(value):
    if not isinstance(value, str) or len(value) > 250 or not WEB_PATH.fullmatch(value):
        raise ContractError("Rute harus path lokal kanonis.")
    return value


def relative_path(value):
    value = text(value, "Path artefak", 300)
    parts = value.split("/")
    if PurePosixPath(value).is_absolute() or any(
        not part or part in {".", ".."} or part.startswith(".") or "\\" in part for part in parts
    ):
        raise ContractError("Path artefak di luar scope.")
    return value
