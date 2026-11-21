"""Validasi angka dan jejak sumber untuk optimizer berbatas."""
from math import isfinite

from ._forge_io import InputError, entries, integer, string


MAX_FEATURES = 128
MAX_SAMPLES = 512
MAX_STEPS = 256
MAX_OPERATIONS = 12_000_000


def real(raw, lower, upper):
    if type(raw) not in (int, float) or not lower <= raw <= upper:
        raise InputError(f"Angka harus finite dan berada pada rentang {lower}–{upper}.")
    return float(raw)


def vector(value, width, label, limit=10_000):
    if not isinstance(value, list) or len(value) != width:
        raise InputError(f"Panjang {label} berbeda dari resep.")
    return [real(item, -limit, limit) for item in value]


def sample_rows(raw):
    records = entries(raw, MAX_SAMPLES)
    if not records:
        raise InputError("Optimasi memerlukan contoh.")
    return records


def reference(value, seen, label):
    value = string(value, label)
    if value in seen:
        raise InputError(f"{label} ganda.")
    seen.add(value)
    return value


def steps_count(value):
    return integer(value, 1, MAX_STEPS)


def operation_budget(cost):
    if cost > MAX_OPERATIONS:
        raise InputError("Ukuran resep melampaui anggaran operasi offline.")


def stable(values):
    if not all(isfinite(value) and abs(value) <= 10**12 for value in values):
        raise InputError("Optimasi divergen pada resep yang diberikan.")
