"""Kontrak kehadiran untuk menjaga angka, referensi, dan input tetap dapat diperiksa ulang."""
import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys


HEX = re.compile(r"[0-9a-f]{64}")
ID = re.compile(r"[a-z][a-z0-9_]{0,63}")
NUMERIC = re.compile(r"[+-]?[0-9]{1,15}(?:\.[0-9]{1,12})?")
TOKENS = re.compile(r"[^\W_]+", re.UNICODE)


class PresenceError(ValueError):
    """Data kehadiran tidak mendukung operasi yang diminta."""


def canonical(value):
    return json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def identity(value):
    return sha256(canonical(value)).hexdigest()


def digest(value):
    if not isinstance(value, str) or HEX.fullmatch(value) is None:
        raise PresenceError("Hash harus SHA-256 heksadesimal kanonis.")
    return value


def anchor(value, expected):
    if identity(value) != digest(expected):
        raise PresenceError("Kontrak berbeda dari anchor.")
    return value


def obj(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise PresenceError("Kolom data kehadiran tidak sesuai schema.")
    return value


def schema(value, name, fields):
    obj(value, ("schema", *fields))
    if value["schema"] != name:
        raise PresenceError("Versi schema belum didukung.")
    return value


def identifier(value, label):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise PresenceError(f"{label} perlu ID huruf kecil yang kanonis.")
    return value


def text(value, label, maximum=400):
    if not isinstance(value, str) or not value.strip() or not value.isprintable() or len(value) > maximum:
        raise PresenceError(f"{label} perlu teks cetak dalam batas.")
    return value


def integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PresenceError(f"{label} di luar batas.")
    return value


def items(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise PresenceError("Panjang daftar kehadiran di luar batas.")
    return value


def day(value):
    try:
        stamp = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise PresenceError("Tanggal perlu YYYY-MM-DD.") from error
    if value != stamp.isoformat():
        raise PresenceError("Tanggal perlu bentuk kanonis.")
    return stamp


def number(value, label):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not NUMERIC.fullmatch(value):
        raise PresenceError(f"{label} perlu desimal tertulis dan terbatas.")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise PresenceError(f"{label} tidak dapat dibaca sebagai desimal.") from error


def fmt(value):
    return "0" if not value else format(Decimal(value).normalize(), "f")


def words(value):
    return {token.casefold() for token in TOKENS.findall(value) if len(token) >= 2}


def unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PresenceError("Kunci JSON ganda.")
        value[key] = item
    return value


def _nonfinite(_):
    raise PresenceError("Angka nonfinite tidak sah.")


def decode(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_json, parse_constant=_nonfinite)


def read(path, limit=2_000_000):
    with path.open("rb") as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise PresenceError("Berkas kehadiran melewati batas ukuran.")
    return data


def source_bytes(root, relative, expected, maximum=1_000_000):
    if not isinstance(relative, str) or len(relative) > 400 or not relative.isprintable():
        raise PresenceError("Penunjuk sumber tidak sah.")
    pieces = relative.split("/")
    if any(piece in ("", ".", "..") for piece in pieces) or "\\" in relative:
        raise PresenceError("Penunjuk sumber harus relatif dan tidak boleh keluar root.")
    digest(expected)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in pieces[:-1]:
            following = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        leaf = os.open(pieces[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(leaf, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise PresenceError("Sumber harus berkas reguler dalam batas.")
            raw = stream.read(maximum + 1)
    finally:
        os.close(descriptor)
    if len(raw) > maximum or sha256(raw).hexdigest() != expected:
        raise PresenceError("Byte sumber berbeda dari anchor.")
    return raw


def cli(call, description, argv=None, *, rooted=False):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    if rooted:
        parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan = decode(read(args.plan))
        report = call(plan, args.expect_sha256, args.root) if rooted else call(plan, args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0
