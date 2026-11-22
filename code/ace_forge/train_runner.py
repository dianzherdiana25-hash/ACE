"""Orkestrasi resep tempa numerik dengan checkpoint per pekerjaan.

Setiap resep dan sumbernya dikunci oleh rencana, lalu dijalankan berurutan
lewat optimizer lokal. Checkpoint yang tercetak mengikat receipt dan
head sebelumnya. Resume memerlukan head eksternal dan memeriksa seluruh
prefix sebelum melewati pekerjaan yang selesai. Pekerjaan terputus
sebelum checkpoint dijalankan kembali dari awal.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from . import lora_trainer, preference_trainer
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_JOBS = 16
MAX_LOG_BYTES = MAX_BYTES * 2
OPTIMIZERS = {"lora_dense": lora_trainer, "dpo_linear": preference_trainer}
SOURCE_FIELD = {"lora_dense": "dataset_sha256", "dpo_linear": "pairs_sha256"}
RECEIPT_SCHEMA = {"lora_dense": "ace.lora-train-receipt.v1", "dpo_linear": "ace.dpo-fit-receipt.v1"}


@dataclass(frozen=True, slots=True)
class Job:
    key: str
    kind: str
    recipe: str
    source: str

    @classmethod
    def read(cls, raw, refs):
        object_fields(raw, ("id", "optimizer", "recipe_sha256", "source_sha256"))
        key = reference(raw["id"], refs, "ID pekerjaan")
        kind = string(raw["optimizer"], "optimizer")
        if kind not in OPTIMIZERS:
            raise InputError("Optimizer tidak tersedia pada runner numerik.")
        return cls(key, kind, digest(raw["recipe_sha256"]), digest(raw["source_sha256"]))


def genesis(plan_sha256):
    return identity({"schema": "ace.forge-train-checkpoints.v1", "plan_sha256": digest(plan_sha256)})


def _prepare(raw, inputs, expected_plan):
    object_fields(raw, ("plan_ref", "jobs"))
    if identity(raw) != digest(expected_plan):
        raise InputError("Rencana pelatihan berubah sejak anchor.")
    string(raw["plan_ref"], "rujukan rencana")
    seen = set()
    jobs = [Job.read(row, seen) for row in entries(raw["jobs"], MAX_JOBS)]
    if not jobs:
        raise InputError("Rencana pelatihan kosong.")
    bundled = {}
    for item in entries(inputs, MAX_JOBS):
        object_fields(item, ("id", "recipe", "source"))
        key = string(item["id"], "ID bundel pekerjaan")
        if key in bundled or key not in seen:
            raise InputError("Bundel pekerjaan ganda atau tidak dikenal.")
        bundled[key] = item
    if bundled.keys() != seen:
        raise InputError("Daftar pekerjaan dan bundel berbeda.")
    for job in jobs:
        bundle = bundled[job.key]
        if identity(bundle["recipe"]) != job.recipe or identity(bundle["source"]) != job.source:
            raise InputError(f"Bundel pekerjaan {job.key} berubah sejak rencana.")
    return jobs, bundled


def _validate_receipt(receipt, job):
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA[job.kind]:
        raise InputError("Skema receipt optimizer tidak sah.")
    if (receipt.get("recipe_sha256") != job.recipe or receipt.get(SOURCE_FIELD[job.kind]) != job.source
            or not isinstance(receipt.get("adapter"), dict)
            or receipt.get("adapter_sha256") != identity(receipt["adapter"])):
        raise InputError("Receipt optimizer tidak cocok dengan resep, sumber, atau adaptor.")


def _replay(records, jobs, plan_hash, expected_head):
    previous = genesis(plan_hash)
    entries(records, MAX_JOBS)
    if len(records) > len(jobs):
        raise InputError("Checkpoint lebih panjang dari rencana.")
    for index, (record, job) in enumerate(zip(records, jobs), 1):
        object_fields(record, ("sequence", "id", "optimizer", "plan_sha256", "previous_sha256", "receipt", "sha256"))
        header = {field: value for field, value in record.items() if field != "sha256"}
        if (integer(record["sequence"], 1, MAX_JOBS) != index or record["id"] != job.key
                or record["optimizer"] != job.kind or record["plan_sha256"] != plan_hash
                or record["previous_sha256"] != previous or digest(record["sha256"]) != identity(header)):
            raise InputError(f"Rantai atau urutan checkpoint {index} tidak cocok.")
        _validate_receipt(record["receipt"], job)
        previous = record["sha256"]
    if previous != digest(expected_head):
        raise InputError("Head checkpoint berbeda dari anchor.")
    return previous


def run(plan, bundles, expected_plan_sha256, *, checkpoints=None, expected_head=None):
    """Yield checkpoint baru, setelah seluruh input dan prefix divalidasi."""
    jobs, inputs = _prepare(plan, bundles, expected_plan_sha256)
    if (checkpoints is None) != (expected_head is None):
        raise InputError("Resume memerlukan checkpoint dan anchor head.")
    history = [] if checkpoints is None else checkpoints
    head = genesis(expected_plan_sha256) if expected_head is None else expected_head
    previous = _replay(history, jobs, expected_plan_sha256, head)
    for index, job in enumerate(jobs[len(history):], len(history) + 1):
        request = inputs[job.key]
        try:
            receipt = OPTIMIZERS[job.kind].fit(request["recipe"], request["source"], job.source)
            _validate_receipt(receipt, job)
        except (ValueError, OverflowError, RecursionError) as exc:
            raise InputError(f"Pekerjaan {job.key} gagal: {exc}") from exc
        header = {"sequence": index, "id": job.key, "optimizer": job.kind, "plan_sha256": expected_plan_sha256,
                  "previous_sha256": previous, "receipt": receipt}
        previous = identity(header)
        yield {**header, "sha256": previous}


def _load(path):
    data = read_bytes(path, MAX_LOG_BYTES)
    if data and not data.endswith(b"\n"):
        raise InputError("Record checkpoint tidak lengkap.")
    records = []
    for index, line in enumerate(data.splitlines(), 1):
        row = decode(line)
        if canonical(row) != line or index > MAX_JOBS:
            raise InputError("Checkpoint harus JSONL kanonis dengan batas pekerjaan.")
        records.append(row)
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("bundles", type=Path)
    parser.add_argument("--expect-plan-sha256", required=True)
    parser.add_argument("--checkpoint-from", type=Path)
    parser.add_argument("--expect-head")
    args = parser.parse_args(argv)
    try:
        checkpoint = _load(args.checkpoint_from) if args.checkpoint_from else None
        for record in run(decode(read_bytes(args.plan, MAX_BYTES)), decode(read_bytes(args.bundles, MAX_BYTES)),
                          args.expect_plan_sha256, checkpoints=checkpoint, expected_head=args.expect_head):
            sys.stdout.write(canonical(record).decode("utf-8") + "\n")
            sys.stdout.flush()
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
