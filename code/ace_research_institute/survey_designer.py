"""Bangun instrumen survei draf dengan codebook, logika cabang, dan minimisasi data."""
from collections import defaultdict
from random import Random

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, items, obj, schema, text


def _question(record, constructs):
    common = ("id", "kind", "prompt", "construct", "source_ref", "required", "visibility")
    kind = record.get("kind") if isinstance(record, dict) else None
    additions = {"likert": ("scale_min", "scale_max", "reverse"), "choice": ("options",),
                 "open": ("max_chars",), "screen": ("options",)}
    if kind not in additions:
        raise ResearchError("Jenis pertanyaan tidak terdaftar.")
    obj(record, (*common, *additions[kind]))
    key = identifier(record["id"], "Item")
    topic = identifier(record["construct"], "Konstruk")
    if topic not in constructs or type(record["required"]) is not bool:
        raise ResearchError("Konstruk atau penanda wajib tidak sah.")
    prompt = text(record["prompt"], "Pertanyaan", 250)
    ref = text(record["source_ref"], "Pointer pertanyaan")
    needs = record["visibility"]
    if needs is not None:
        obj(needs, ("depends_on", "equals"))
        needs = {key: identifier(value, "Gerbang survei") for key, value in needs.items()}
    properties = {}
    if kind == "likert":
        scale_start = integer(record["scale_min"], "Skala awal", 0, 4)
        scale_end = integer(record["scale_max"], "Skala akhir", scale_start + 1, 10)
        if type(record["reverse"]) is not bool:
            raise ResearchError("Butir reverse-score perlu boolean.")
        properties = {"scale": list(range(scale_start, scale_end + 1)), "reverse_score": record["reverse"]}
    if kind in ("choice", "screen"):
        options = {}
        for item in items(record["options"], 16, 2):
            obj(item, ("id", "label"))
            option = identifier(item["id"], "Opsi")
            if option in options:
                raise ResearchError("Opsi survei ganda.")
            options[option] = text(item["label"], "Label opsi", 110)
        properties = {"options": options}
    if kind == "open":
        properties = {"max_chars": integer(record["max_chars"], "Jawaban maksimum", 20, 1500)}
    return {"id": key, "kind": kind, "prompt": prompt, "construct": topic, "source_ref": ref, "visibility": needs,
            "required": record["required"], **properties}


def design_survey(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.survey-plan.v1", ("study", "purpose", "consent_text", "constructs", "seed", "questions"))
    study = identifier(plan["study"], "Survei")
    seed = integer(plan["seed"], "Seed", 0, 2**63 - 1)
    intents = {}
    for row in items(plan["constructs"], 25, 1):
        obj(row, ("id", "definition", "min_items"))
        name = identifier(row["id"], "Konstruk")
        if name in intents:
            raise ResearchError("Konstruk ganda.")
        intents[name] = {"definition": text(row["definition"], "Definisi konstruk"),
                         "minimum": integer(row["min_items"], "Item minimum", 1, 20)}
    earlier = {}
    groups = defaultdict(list)
    choices = []
    for row in items(plan["questions"], 140, 1):
        item = _question(row, intents)
        name = item["id"]
        if name in earlier:
            raise ResearchError("ID pertanyaan ganda.")
        test = item["visibility"]
        if item["kind"] == "screen":
            if test is not None:
                raise ResearchError("Screening tidak boleh tergantung pertanyaan lain.")
            choices.append(item)
        else:
            if test is not None:
                required = earlier.get(test["depends_on"])
                if required is None or required["kind"] != "screen" or test["equals"] not in required["options"]:
                    raise ResearchError("Cabang harus menunjuk opsi screening terdahulu.")
            groups[item["construct"]].append(item)
        earlier[name] = item
    order = []
    rand = Random(seed)
    for construct in sorted(intents):
        block = groups[construct]
        if len(block) < intents[construct]["minimum"]:
            raise ResearchError(f"Konstruk {construct} belum mencapai jumlah butir minimum.")
        rand.shuffle(block)
        order.extend(block)
    all_items = [*choices, *order]
    return {"schema": "ace.institute.survey-instrument.v1", "plan_sha256": expected, "study": study,
            "state": "draft_instrument", "purpose": text(plan["purpose"], "Tujuan survei"),
            "consent_text": text(plan["consent_text"], "Narasi persetujuan", 500), "constructs": intents,
            "item_bank_sha256": identity(all_items), "sequence": all_items}


if __name__ == "__main__":
    raise SystemExit(cli(design_survey, __doc__))
