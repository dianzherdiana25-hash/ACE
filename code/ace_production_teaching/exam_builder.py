"""Rakit ujian bertingkat dari bank held-out dan pisahkan kunci mekanis dari naskah."""
import argparse
from pathlib import Path
from random import Random
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         identity, integer, items, obj, read, schema, text)
from .document_builder import make_document
from .exercise_generator import generate


def exam(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.exam-plan.v1", ("title", "bank", "targets", "seed", "minutes", "formats"))
    label = text(plan["title"], "Judul ujian", 150)
    clock = integer(plan["minutes"], "Waktu ujian", 1, 250)
    seed = integer(plan["seed"], "Seed penyusunan", 0, 2**63 - 1)
    source = generate(plan["bank"], identity(plan["bank"]))
    keys = {row["id"]: row for row in source["held_out_key"]}
    bank = [item for item in source["questions"] if item["id"] in keys and item["split"] == "held_out"]
    selection = []
    scope = set()
    random = Random(seed)
    for row in items(plan["targets"], 40, 1):
        obj(row, ("topic", "level", "count", "points_each"))
        topic = identifier(row["topic"], "Topik ujian")
        difficulty = integer(row["level"], "Tingkat", 1, 8)
        count = integer(row["count"], "Butir sesuai tingkat", 1, 60)
        points = integer(row["points_each"], "Poin per soal", 1, 50)
        if (topic, difficulty) in scope:
            raise ProductionError("Kisi ujian memuat kelompok duplikat.")
        scope.add((topic, difficulty))
        samples = sorted((item for item in bank if (item["topic"], item["level"]) == (topic, difficulty)),
                         key=lambda item: item["id"])
        if len(samples) < count:
            raise ProductionError("Bank held-out tidak cukup untuk satu kelompok.")
        selection.extend((item, points) for item in random.sample(samples, count))
    if len(selection) > 150 or clock < len(selection):
        raise ProductionError("Kisi ujian melebihi jumlah butir atau waktu minimum.")
    rows = [{"kind": "paragraph", "body": f"Waktu {clock} menit."}]
    answer_key = []
    for index, (item, points) in enumerate(selection, 1):
        rows.append({"kind": "paragraph", "body": f"{index}. {item['prompt']} ({points} poin)"})
        answer_key.append({"number": index, "item_id": item["id"], "points": points,
                           "answer": keys[item["id"]]["answer"], "unit": keys[item["id"]]["unit"],
                           "question_sha256": identity(item), "source_ref": item["source_ref"]})
    doc = {"schema": "ace.production.document-plan.v1", "title": label, "bindings": [],
           "blocks": rows, "formats": plan["formats"]}
    artifacts, proof = make_document(doc, identity(doc))
    key = {"schema": "ace.teaching.exam-key.v1", "plan_sha256": expected, "answers": answer_key}
    return artifacts, key, {"schema": "ace.teaching.exam-receipt.v1", "plan_sha256": expected,
                            "document": proof, "selected_ids": [item["item_id"] for item in answer_key],
                            "total_points": sum(item["points"] for item in answer_key), "key_sha256": identity(key),
                            "bank_held_out_sha256": source["held_out_key_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--key-output", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, key, proof = exam(decode(read(args.plan)), args.expect_sha256)
        if args.key_output.resolve().is_relative_to(args.output.resolve()):
            raise ProductionError("Kunci harus di lokasi yang terpisah dari naskah.")
        args.output.mkdir()
        with args.key_output.open("xb") as stream:
            stream.write(canonical(key) + b"\n")
        for name, data in files.items():
            (args.output / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(proof) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
