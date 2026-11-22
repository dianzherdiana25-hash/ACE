"""Berikan petunjuk bertahap dengan pemeriksaan kebocoran jawaban yang dicadangkan."""
import re
import unicodedata

from ._contracts import ProductionError, anchor, cli, identifier, integer, items, obj, schema, text


def _normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def leaks(body, reserved):
    trial = _normalized(body)
    return any(re.search(r"(?<!\w)" + re.escape(_normalized(value)) + r"(?!\w)", trial) for value in reserved)


def next_hint(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.hint-plan.v1", ("exercise", "provided_ids", "answer_forms", "chain"))
    task = identifier(plan["exercise"], "Latihan")
    hidden = [text(item, "Bentuk jawaban terlindungi", 90) for item in items(plan["answer_forms"], 30, 1)]
    previously = [identifier(item, "ID petunjuk sebelumnya") for item in items(plan["provided_ids"], 20)]
    chain = []
    known = set()
    for row in items(plan["chain"], 20, 1):
        obj(row, ("id", "level", "prompt", "source_ref"))
        name = identifier(row["id"], "Petunjuk")
        rank = integer(row["level"], "Tingkat petunjuk", 1, 20)
        if name in known or rank != len(chain) + 1:
            raise ProductionError("Petunjuk perlu ID unik dan tingkat berurutan.")
        known.add(name)
        tip = text(row["prompt"], "Isi petunjuk", 600)
        chain.append({"id": name, "level": rank, "prompt": tip,
                      "source_ref": text(row["source_ref"], "Pointer petunjuk"),
                      "unsafe": leaks(tip, hidden)})
    allowed = [row for row in chain if not row["unsafe"]]
    if previously != [row["id"] for row in allowed[:len(previously)]]:
        raise ProductionError("Riwayat petunjuk tidak seturut rantai aman.")
    selected = next((row for row in allowed if row["id"] not in previously), None)
    blocked = [{"id": row["id"], "reason": "reserved_answer_overlap"} for row in chain if row["unsafe"]]
    tip = {key: selected[key] for key in ("id", "level", "prompt", "source_ref")} if selected else None
    return {"schema": "ace.teaching.next-hint.v1", "plan_sha256": expected, "exercise": task,
            "status": "hint_available" if tip else "hints_exhausted", "hint": tip, "held": blocked,
            "basis": "explicit_answer_forms_and_literal_overlap"}


if __name__ == "__main__":
    raise SystemExit(cli(next_hint, __doc__))
