"""Samakan satuan dan konteks hanya jika transformasi fisiknya jelas."""
from decimal import Decimal

from ._contracts import ResearchError, identifier, number, obj


UNITS = {
    "ratio": ("fraction", "1"), "pct": ("fraction", "0.01"), "ppm": ("fraction", "0.000001"),
    "s": ("s", "1"), "ms": ("s", "0.001"), "min": ("s", "60"),
    "m": ("m", "1"), "cm": ("m", "0.01"), "mm": ("m", "0.001"),
    "g": ("g", "1"), "mg": ("g", "0.001"), "kg": ("g", "1000"),
    "count": ("count", "1"), "lux": ("lux", "1"), "celsius": ("celsius", "1"),
    "points": ("points", "1"),
}
DIMENSIONS = ("population", "outcome", "context")


def dimension(value):
    obj(value, DIMENSIONS)
    return tuple(identifier(value[key], key) for key in DIMENSIONS)


def quantity(value, unit):
    if not isinstance(unit, str) or unit not in UNITS:
        raise ResearchError("Satuan tidak didukung oleh pembanding penelitian.")
    dim, scalar = UNITS[unit]
    return dim, number(value, "Nilai") * Decimal(scalar)


def reviewed(source_plan, root):
    """Baca ulang tabel hasil hanya dari sumber yang lolos saringan dan anchor."""
    from ._contracts import identity, source_bytes
    from .paper_reader import extract
    from .source_collector import collect

    registry = collect(source_plan, identity(source_plan), root)
    claims = []
    held = []
    for source in registry["sources"]:
        if source["hold_reasons"]:
            continue
        raw = source_bytes(root, source["path"], source["sha256"])
        reading = extract(raw, source["title"], source["path"], source["independence_group"], source["sha256"])
        for claim in reading["claims"]:
            claims.append({**claim, "source_id": source["id"], "source_score": source["score"]})
        if reading["held"]:
            held.append({"source": source["id"], "rows": reading["held"]})
    return registry, claims, held
