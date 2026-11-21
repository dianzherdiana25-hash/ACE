"""Validasi kontrak input dan identitas artefak pabrik software."""
from hashlib import sha256
import json
import re


MAX_BYTES = 2_000_000
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,63}")
SHA = re.compile(r"[a-f0-9]{64}")


class ContractError(ValueError):
    """Input atau artefak gagal memenuhi kontrak."""


def obj(raw, fields):
    if not isinstance(raw, dict) or set(raw) != set(fields):
        raise ContractError("Kolom objek tidak sesuai kontrak.")
    return raw


def text(raw, name, maximum=500):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > maximum or not raw.isprintable():
        raise ContractError(f"{name} perlu teks cetak dalam batas.")
    return raw


def identifier(raw, name):
    if not isinstance(raw, str) or not IDENTIFIER.fullmatch(raw):
        raise ContractError(f"{name} perlu identifier huruf kecil yang sah.")
    return raw


def integer(raw, name, minimum, maximum):
    if type(raw) is not int or not minimum <= raw <= maximum:
        raise ContractError(f"{name} di luar batas integer.")
    return raw


def digest(raw):
    if not isinstance(raw, str) or not SHA.fullmatch(raw):
        raise ContractError("Anchor perlu SHA-256 lowercase.")
    return raw


def entries(raw, maximum, *, minimum=0):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise ContractError("Panjang daftar di luar batas.")
    return raw


def canonical(raw):
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def identity(raw):
    return sha256(canonical(raw)).hexdigest()


def _distinct(rows):
    output = {}
    for key, value in rows:
        if key in output:
            raise ContractError("Kunci JSON ganda.")
        output[key] = value
    return output


def _constant(value):
    raise ContractError("Konstanta JSON nonfinite tidak didukung.")


def decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_distinct, parse_constant=_constant)


def read(path, maximum=MAX_BYTES):
    with path.open("rb") as stream:
        data = stream.read(maximum+1)
    if len(data) > maximum:
        raise ContractError("Masukan melampaui ukuran maksimum.")
    return data


def schema(raw, name, fields):
    obj(raw, ("schema", *fields))
    if raw["schema"] != name:
        raise ContractError("Skema tidak didukung.")
    return raw


def checked(raw, expected):
    if digest(expected) != identity(raw):
        raise ContractError("Input berbeda dari anchor yang diberikan.")
