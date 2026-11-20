"""Distilasi prosedur lokal dari contoh organ yang sudah direkam.

Dataset dan bukti per contoh harus lolos kustodi. Pemanggil menyertakan
langkah yang diekstrak dari tiap demonstrasi. Distilasi menahan lesson
ketika dukungan kurang atau urutan langkah bertentangan. Retrieval
latihan held-out berisi soal dan pointer ke bukti verifikasi.
"""
import argparse
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, entries, identity, integer, object_fields, read_bytes, string
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES


MAX_METADATA = 2_000


def _observations(protocol, dataset):
    metadata = {}
    receipts, steps_used = set(), defaultdict(list)
    for row in entries(protocol["observations"], MAX_METADATA):
        object_fields(row, ("event_id", "lesson_id", "teacher_ref", "steps"))
        key = string(row["event_id"], "ID contoh")
        lesson = string(row["lesson_id"], "ID lesson")
        teacher = string(row["teacher_ref"], "rujukan artefak organ")
        steps = tuple(string(item, "langkah", max_chars=500) for item in entries(row["steps"], 30))
        if key not in dataset:
            raise InputError("Metadata menunjuk contoh di luar dataset terverifikasi.")
        if key in metadata or teacher in receipts or len(steps) != len(set(steps)):
            raise InputError("Metadata contoh, rujukan organ, atau langkah ganda.")
        example = dataset[key]
        if (example["split"] == "train") != bool(steps):
            raise InputError("Langkah hanya diambil dari demonstrasi train dan wajib ada di setiap demonstrasi yang dipilih.")
        if teacher in (protocol["metadata_ref"], example["provenance"]["evidence_ref"],
                       example["provenance"]["index_ref"]):
            raise InputError("Rujukan artefak organ harus terpisah dari verifier dan metadata.")
        metadata[key] = row
        receipts.add(teacher)
        steps_used[lesson].append((key, teacher, steps, example))
    return steps_used, sorted(dataset.keys() - metadata.keys())


def _order(training, minimum):
    supports = defaultdict(set)
    edges = defaultdict(set)
    for key, _, steps, _ in training:
        for step in steps:
            supports[step].add(key)
        for first, second in combinations(steps, 2):
            edges[first, second].add(key)
    supported = {step: sorted(keys) for step, keys in supports.items() if len(keys) >= minimum}
    discarded = {step: sorted(supports[step]) for step in sorted(supports.keys() - supported.keys())}
    order_reasons = []
    successors = defaultdict(set)
    predecessors = dict.fromkeys(supported, 0)
    for (first, second), witnesses in sorted(edges.items()):
        if first not in supported or second not in supported:
            continue
        if (second, first) in edges:
            if first < second:
                order_reasons.append({"pair": [first, second], "forward_events": sorted(witnesses),
                                      "reverse_events": sorted(edges[second, first])})
        else:
            successors[first].add(second)
            predecessors[second] += 1
    ordering = []
    ready = {key for key, count in predecessors.items() if count == 0}
    while ready:
        first = min(ready)
        ready.remove(first)
        ordering.append({"instruction": first, "event_ids": supported[first]})
        for next_step in successors[first]:
            predecessors[next_step] -= 1
            if predecessors[next_step] == 0:
                ready.add(next_step)
    if order_reasons:
        return None, discarded, {"contradictions": order_reasons}
    if len(ordering) != len(supported):
        return None, discarded, {"cycle_remaining_steps": sorted(key for key, count in predecessors.items() if count)}
    return ordering, discarded, None


def _source(record):
    key, teacher, _, example = record
    proof = example["provenance"]
    return {"event_id": key, "teacher_ref": teacher, "evidence_ref": proof["evidence_ref"],
            "payload_sha256": proof["payload_sha256"]}


def _curriculum(records, training_size, quiz_size, step_minimum):
    training = sorted([row for row in records if row[3]["split"] == "train"])
    held = sorted([row for row in records if row[3]["split"] == "held_out"])
    reasons = []
    if len(training) < training_size:
        reasons.append("insufficient_training")
    if len(held) < quiz_size:
        reasons.append("insufficient_held_out")
    kinds = {row[3]["payload"]["task_kind"] for row in records}
    if len(kinds) != 1:
        reasons.append("mixed_task_kinds")
    sequence, discarded, problems = _order(training, step_minimum)
    if problems:
        reasons.append("conflicting_order")
    elif not sequence:
        reasons.append("no_supported_steps")
    audit = {"training": len(training), "held_out": len(held), "reasons": reasons,
             "discarded_steps": discarded, "ordering_conflicts": problems}
    if reasons:
        return None, audit
    demonstrations = [{**_source(row), "prompt": row[3]["payload"]["prompt"],
                       "expected_answer": row[3]["payload"]["target"]} for row in training]
    quiz = [{"event_id": row[0], "teacher_ref": row[1], "prompt": row[3]["payload"]["prompt"],
             "evidence_ref": row[3]["provenance"]["evidence_ref"]} for row in held]
    return {"task_kind": kinds.pop(), "steps": sequence, "demonstrations": demonstrations, "held_out": quiz}, audit


def distill(dataset, manifest, expected_head, protocol):
    custody = verify(dataset, manifest, expected_head)
    if not custody["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    object_fields(protocol, ("metadata_ref", "minimum_training", "minimum_held_out", "minimum_step_support", "observations"))
    meta_ref = string(protocol["metadata_ref"], "rujukan metadata")
    if meta_ref != protocol["metadata_ref"]:
        raise InputError("Rujukan metadata harus sudah dirapikan.")
    minimum_train = integer(protocol["minimum_training"], 1, MAX_METADATA)
    minimum_quiz = integer(protocol["minimum_held_out"], 1, MAX_METADATA)
    support = integer(protocol["minimum_step_support"], 1, MAX_METADATA)
    dataset_by_event = {}
    for line in dataset.splitlines():
        raw = decode(line)
        dataset_by_event[raw["payload"]["event_id"]] = raw
    groups, excluded = _observations(protocol, dataset_by_event)
    lessons, audits = [], []
    for lesson, records in sorted(groups.items()):
        product, audit = _curriculum(records, minimum_train, minimum_quiz, support)
        if product is not None:
            lessons.append({"lesson_id": lesson, **product})
        audits.append({"lesson_id": lesson, **audit})
    metadata_snapshot = {**protocol, "observations": sorted(protocol["observations"], key=lambda row: row["event_id"])}
    return {"schema": "ace.distilled-curriculum.v1", "dataset_head_sha256": expected_head,
            "metadata_ref": meta_ref, "metadata_sha256": identity(metadata_snapshot), "lessons": lessons,
            "audit": audits, "unmapped_events": excluded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expect-head", required=True)
    args = parser.parse_args(argv)
    try:
        report = distill(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                         args.expect_head, decode(read_bytes(args.metadata, MAX_BYTES)))
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
