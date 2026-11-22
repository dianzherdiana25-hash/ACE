"""Sesuaikan tingkat penjelasan dengan kartu sumber dan binding fakta yang dipertahankan."""
import re

from ._contracts import ProductionError, anchor, cli, decode, identifier, items, obj, schema, source_bytes, text


LABEL = re.compile(r"\{\{([a-z][a-z0-9_]{0,63})\}\}")
NUMERALS = re.compile(r"(?<!\w)[+-]?[0-9]+(?:[.,][0-9]+)?(?!\w)")


def adapt(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.explanation-plan.v1", ("source", "level", "variants"))
    level = plan["level"]
    if level not in ("intro", "intermediate", "technical"):
        raise ProductionError("Tingkat penjelasan belum didukung.")
    ref = obj(plan["source"], ("path", "sha256"))
    source = decode(source_bytes(root, ref["path"], ref["sha256"], 600000))
    schema(source, "ace.teaching.explanation-card.v1", ("topic", "facts"))
    facts = {}
    for row in items(source["facts"], 80, 1):
        obj(row, ("id", "render", "source_ref", "essential"))
        key = identifier(row["id"], "Fakta yang ditahan")
        if key in facts or type(row["essential"]) is not bool:
            raise ProductionError("ID fakta ganda atau essential tidak boolean.")
        statement = text(row["render"], "Kalimat fakta", 210)
        pointer = text(row["source_ref"], "Pointer fakta")
        if "{{" in statement or "}}" in statement:
            raise ProductionError("Isi fakta tidak boleh memasukkan placeholder.")
        facts[key] = {"id": key, "statement": statement, "source_ref": pointer, "essential": row["essential"]}
    choices = obj(plan["variants"], ("intro", "intermediate", "technical"))
    variants = {}
    for key, collection in choices.items():
        blocks = []
        needed = set()
        for row in items(collection, 60, 1):
            line = text(row, "Frasa penjelasan", 850)
            if NUMERALS.search(LABEL.sub("", line)):
                raise ProductionError("Angka baru pada versi penjelasan perlu fakta asal.")
            used = LABEL.findall(line)
            if any(label not in facts for label in used):
                raise ProductionError("Variasi menjanjikan fakta belum terdaftar.")
            carried = LABEL.sub(lambda value: facts[value[1]]["statement"], line)
            if "{{" in carried or "}}" in carried:
                raise ProductionError("Placeholder penjelasan tidak terisi.")
            needed.update(used)
            blocks.append({"text": carried, "sources": [facts[label]["source_ref"] for label in dict.fromkeys(used)]})
        if not {label for label, fact in facts.items() if fact["essential"]} <= needed:
            raise ProductionError(f"Fakta esensial hilang pada tingkat {key}.")
        variants[key] = blocks
    return {"schema": "ace.teaching.explanation.v1", "plan_sha256": expected, "source": ref,
            "topic": identifier(source["topic"], "Topik"), "level": level, "blocks": variants[level],
            "basis": "source_bound_variants", "essential_facts": [facts[key] for key in sorted(facts) if facts[key]["essential"]]}


if __name__ == "__main__":
    raise SystemExit(cli(adapt, __doc__, rooted=True))
