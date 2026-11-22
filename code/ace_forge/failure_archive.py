"""Arsipkan kegagalan tempa dari replay ledger tertambat untuk telaah.

Hanya event terminal fail menambah catatan. Diagnosis yang dicatat
pemanggil harus menunjuk rujukan terminal yang sama. Kategori
menunjukkan pengelompokan yang diberikan sumber dan dapat belum
tersedia. Keluaran JSON/JSONL dapat diarsipkan tanpa mengubah input.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from . import experiment_tracker
from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES


MAX_SNAPSHOTS = 50


def _tag_index(raw):
    tags = {}
    refs = set()
    for row in entries(raw, experiment_tracker.MAX_EVENTS):
        object_fields(row, ("experiment_id", "diagnosis_ref", "category", "classification_ref"))
        key = string(row["experiment_id"], "ID eksperimen")
        pointer = string(row["classification_ref"], "rujukan klasifikasi")
        if key in tags or pointer in refs:
            raise InputError("Klasifikasi kegagalan ganda.")
        refs.add(pointer)
        tags[key] = {"category": string(row["category"], "kategori kegagalan"),
                     "diagnosis_ref": string(row["diagnosis_ref"], "rujukan diagnosis"),
                     "classification_ref": pointer}
    return tags


def _snapshot(raw):
    object_fields(raw, ("ledger", "ledger_sha256", "tags"))
    evidence = experiment_tracker.audit(raw["ledger"], raw["ledger_sha256"])
    tags = _tag_index(raw["tags"])
    runs = {}
    for item in evidence["experiments"]:
        key = item["experiment_id"]
        if item["status"] != "failed":
            continue
        tag = tags.pop(key, None)
        if tag is not None and tag["diagnosis_ref"] != item["terminal_ref"]:
            raise InputError("Klasifikasi memakai rujukan diagnosis berbeda dari receipt terminal.")
        last = item["events"][-1]
        content = {"experiment_id": key, "at": last["at"], "event_ref": last["event_ref"],
                   "diagnosis_ref": item["terminal_ref"], "plan_ref": item["plan_ref"],
                   "recipe_sha256": item["recipe_sha256"], "dataset_sha256": item["dataset_sha256"],
                   "attempts": item["attempts"], "spent_units": item["spent_units"],
                   "over_budget": item["over_budget"],
                   "last_checkpoint": item["checkpoints"][-1] if item["checkpoints"] else None}
        source = {"ledger_ref": evidence["ledger_ref"], "ledger_sha256": evidence["ledger_sha256"],
                  "line": last["index"]}
        runs[key] = (content, source, tag)
    if tags:
        raise InputError("Klasifikasi tidak terikat eksperimen gagal.")
    return runs


def archive(raw, expected):
    object_fields(raw, ("archive_ref", "snapshots"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana arsip berbeda dari anchor.")
    source = string(raw["archive_ref"], "rujukan arsip")
    runs = {}
    by_hash = {}
    for snapshot in entries(raw["snapshots"], MAX_SNAPSHOTS):
        for key, (content, pointer, tag) in _snapshot(snapshot).items():
            checksum = identity(content)
            if key in runs and runs[key] != checksum:
                raise InputError("Receipt terminal eksperimen bertentangan antar-snapshot.")
            runs[key] = checksum
            row = by_hash.setdefault(checksum, {"failure_sha256": checksum, "failure": content,
                                                  "sources": {}, "tags": {}})
            row["sources"][identity(pointer)] = pointer
            if tag is not None:
                ref = tag["classification_ref"]
                if ref in row["tags"] and tag != row["tags"][ref]:
                    raise InputError("Rujukan klasifikasi dipakai dengan isi berbeda.")
                row["tags"][ref] = tag

    rows = []
    groups = defaultdict(list)
    unclassified = []
    conflicts = []
    for row in sorted(by_hash.values(), key=lambda item: (item["failure"]["at"], item["failure"]["experiment_id"])):
        key = row["failure"]["experiment_id"]
        row["sources"] = sorted(row["sources"].values(), key=lambda item: (item["ledger_ref"], item["ledger_sha256"], item["line"]))
        row["tags"] = [item for _, item in sorted(row["tags"].items())]
        categories = {tag["category"] for tag in row["tags"]}
        if len(categories) == 1:
            groups[next(iter(categories))].append(row)
        elif not categories:
            unclassified.append(key)
        else:
            conflicts.append(key)
        row["archive_sha256"] = identity(row)
        rows.append(row)

    return {"schema": "ace.forge-failure-archive.v1", "archive_ref": source, "input_sha256": expected,
            "failed": len(rows), "unclassified": sorted(unclassified), "classification_conflicts": sorted(conflicts),
            "categories": [{"category": kind, "count": len(group),
                            "distinct_recipe_count": len({row["failure"]["recipe_sha256"] for row in group}),
                            "experiment_ids": [row["failure"]["experiment_id"] for row in group],
                            "failure_sha256": [row["failure_sha256"] for row in group]}
                           for kind, group in sorted(groups.items())], "failures": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    args = parser.parse_args(argv)
    try:
        product = archive(decode(read_bytes(args.plan, MAX_BYTES)), args.expect_sha256)
        if args.format == "jsonl":
            for record in product["failures"]:
                sys.stdout.write(canonical(record).decode("utf-8") + "\n")
        else:
            sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
