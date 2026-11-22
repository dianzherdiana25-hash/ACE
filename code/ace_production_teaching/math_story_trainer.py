"""Terbitkan latihan cerita aritmetika lokal dengan model kuantitas yang eksplisit."""
from itertools import product
from random import Random

from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, text


def _make(context, place, unit, a, b):
    if context == "combine":
        return f"Di {place} ada {a} {unit}. Datang lagi {b} {unit}. Berapa jumlah sekarang?", a + b
    if context == "compare":
        return f"Rak pertama di {place} berisi {a} {unit}, rak kedua berisi {b} {unit}. Berapa selisih keduanya?", a - b
    if context == "group":
        return f"Di {place}, {a} kotak masing-masing berisi {b} {unit}. Berapa jumlah {unit}?", a * b
    return f"Di {place} tersedia {a * b} {unit} untuk dibagi rata ke {b} kelompok. Berapa {unit} per kelompok?", a


def create_stories(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.math-story-plan.v1", ("contexts", "seed", "each"))
    each = integer(plan["each"], "Soal per konteks", 1, 20)
    rand = Random(integer(plan["seed"], "Seed cerita", 0, 2**63 - 1))
    cards = []
    keys = []
    used = set()
    identifiers = set()
    for row in items(plan["contexts"], 30, 1):
        obj(row, ("id", "kind", "setting", "unit", "range", "source_ref"))
        key = identifier(row["id"], "Konteks")
        kind = row["kind"]
        if key in identifiers or len(key) > 61 or kind not in ("combine", "compare", "group", "share"):
            raise ProductionError("Konteks ganda atau jenis cerita tidak terdaftar.")
        identifiers.add(key)
        setting = text(row["setting"], "Latar cerita", 70)
        unit = text(row["unit"], "Nama benda hitung", 45)
        src = text(row["source_ref"], "Pointer konsep")
        bounds = items(row["range"], 2, 2)
        lo = integer(bounds[0], "Operand minimum", 1, 150)
        hi = integer(bounds[1], "Operand maksimum", lo, min(200, lo + 70))
        work = []
        for a, b in product(range(lo, hi + 1), repeat=2):
            if kind in ("compare", "combine", "group") and a < b:
                continue
            if (kind, a, b) not in used:
                work.append((a, b))
        if len(work) < each:
            raise ProductionError("Pasangan unik untuk kuantitas cerita belum cukup.")
        for index, (a, b) in enumerate(rand.sample(work, each), 1):
            used.add((kind, a, b))
            prompt, outcome = _make(kind, setting, unit, a, b)
            card = {"id": f"{key}_{index:02}", "context": kind, "prompt": prompt, "unit": unit, "source_ref": src}
            cards.append(card)
            keys.append({"id": card["id"], "prompt_sha256": identity(card), "value": outcome, "unit": unit,
                         "relationship": {"kind": kind, "a": a, "b": b}})
    return {"schema": "ace.teaching.math-stories.v1", "plan_sha256": expected,
            "items": cards, "key": keys, "key_sha256": identity(keys)}


if __name__ == "__main__":
    raise SystemExit(cli(create_stories, __doc__))
