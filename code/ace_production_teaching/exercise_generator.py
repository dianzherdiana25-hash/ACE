"""Buat latihan bertingkat dengan kunci eksak, disiplin unit, dan sampel tanpa duplikasi."""
from decimal import Decimal
from random import Random

from ._contracts import ProductionError, anchor, cli, fmt, identifier, identity, integer, items, obj, schema, text


OPERATIONS = {"addition": lambda a, b: a + b, "difference": lambda a, b: a - b,
              "multiplication": lambda a, b: a * b, "division": lambda a, b: a // b}


def generate(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.exercise-plan.v1", ("seed", "templates", "count_per_template", "held_out"))
    seed = integer(plan["seed"], "Seed latihan", 0, 2**63 - 1)
    count = integer(plan["count_per_template"], "Jumlah latihan", 1, 25)
    held = integer(plan["held_out"], "Jumlah held-out per jenis", 0, count - 1)
    generator = Random(seed)
    names = set()
    questions = []
    keys = []
    seen = set()
    for item in items(plan["templates"], 40, 1):
        obj(item, ("id", "topic", "level", "operation", "a", "b", "prompt", "unit", "source_ref"))
        name = identifier(item["id"], "Templat")
        topic = identifier(item["topic"], "Topik")
        if name in names or len(name) > 61 or item["operation"] not in OPERATIONS:
            raise ProductionError("Templat ganda atau operasi tidak didukung.")
        names.add(name)
        level = integer(item["level"], "Tingkat", 1, 8)
        prompt = text(item["prompt"], "Prompt latihan", 330)
        if prompt.count("{a}") != 1 or prompt.count("{b}") != 1:
            raise ProductionError("Template harus menampilkan tepat satu {a} dan satu {b}.")
        if "{" in prompt.replace("{a}", "").replace("{b}", "") or "}" in prompt.replace("{a}", "").replace("{b}", ""):
            raise ProductionError("Placeholder hanya mendukung {a} dan {b}.")
        unit = text(item["unit"], "Satuan", 40)
        source = text(item["source_ref"], "Pointer konsep")
        choices = []
        for bound in ("a", "b"):
            span = items(item[bound], 2, 2)
            start = integer(span[0], "Batas bawah", -10000, 10000)
            end = integer(span[1], "Batas atas", start, min(start + 200, 10000))
            choices.append(range(start, end + 1))
        feasible = []
        here = set()
        for a in choices[0]:
            for b in choices[1]:
                if item["operation"] == "division" and (not b or a % b):
                    continue
                pair = tuple(sorted((a, b))) if item["operation"] in ("addition", "multiplication") else (a, b)
                signature = (topic, item["operation"], *pair)
                if signature in seen or signature in here:
                    continue
                here.add(signature)
                feasible.append((a, b, signature))
        if len(feasible) < count:
            raise ProductionError("Kombinasi operand unik belum cukup.")
        selected = generator.sample(feasible, count)
        for index, (a, b, signature) in enumerate(selected, 1):
            seen.add(signature)
            body = prompt.replace("{a}", str(a)).replace("{b}", str(b))
            result = OPERATIONS[item["operation"]](a, b)
            key = f"{name}_{index:02}"
            split = "held_out" if index > count - held else "practice"
            question = {"id": key, "topic": topic, "level": level, "prompt": body,
                        "source_ref": source, "split": split, "unit": unit}
            questions.append(question)
            keys.append({"id": key, "answer": fmt(Decimal(result)), "unit": unit, "format": "decimal_text",
                         "question_sha256": identity(question), "method": item["operation"],
                         "operands": [a, b], "split": split})
    sorted_items = sorted(questions, key=lambda row: (row["level"], row["topic"], row["id"]))
    practice_keys = [row for row in keys if row["split"] == "practice"]
    held_out_keys = [row for row in keys if row["split"] == "held_out"]
    return {"schema": "ace.teaching.exercise-set.v1", "plan_sha256": expected, "questions": sorted_items,
            "practice_key": practice_keys, "held_out_key": held_out_keys, "held_out_key_sha256": identity(held_out_keys)}


if __name__ == "__main__":
    raise SystemExit(cli(generate, __doc__))
