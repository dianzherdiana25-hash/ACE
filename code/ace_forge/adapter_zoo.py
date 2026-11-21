"""Katalogkan adaptor kecil yang bentuk matematis dan asalnya diperiksa.

Nama dan versi memberi identitas logis. SHA-256 menambatkan payload
kanonis, basis, dan artefak yang diganti. Review qualified memberi
bukti held-out yang wajib dicatat. Riwayat menunjukkan versi lama
yang tetap memenuhi review saat versi baru belum qualified.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES
from .multitask_merge import Factor


MAX_ADAPTERS = 2000
MAX_VERSION = 10**9
REVIEW_STATES = ("unreviewed", "qualified", "rejected", "retired")


def tags(raw, label):
    words = [string(value, label) for value in entries(raw, 64)]
    if not words or len(set(words)) != len(words):
        raise InputError(f"{label} kosong atau ganda.")
    return sorted(words)


def _snapshot_index(snapshots):
    result = {}
    for raw in entries(snapshots, MAX_ADAPTERS):
        key = identity(raw)
        if key in result:
            raise InputError("Payload adaptor ganda.")
        factor = Factor.read(raw)
        result[key] = {"base_sha256": factor.base, "layer": factor.layer, "rank": factor.rank,
                       "features": factor.features, "outputs": factor.outputs}
    return result


def _review(row):
    if row is None:
        return "unreviewed", None
    object_fields(row, ("status", "review_ref", "held_out_sha256"))
    status = row["status"]
    if status not in REVIEW_STATES[1:]:
        raise InputError("Status review adaptor tak dikenal.")
    return status, {"review_ref": string(row["review_ref"], "rujukan review"),
                    "held_out_sha256": digest(row["held_out_sha256"])}


def catalog(raw, snapshots, expected):
    object_fields(raw, ("catalog_ref", "entries"))
    if identity(raw) != digest(expected):
        raise InputError("Katalog adaptor berbeda dari anchor.")
    source = string(raw["catalog_ref"], "rujukan katalog")
    payloads = _snapshot_index(snapshots)
    catalogued = set()
    versions = defaultdict(dict)
    refs = {source}
    for item in entries(raw["entries"], MAX_ADAPTERS):
        object_fields(item, ("name", "version", "domain", "capabilities", "artifact_sha256", "artifact_ref",
                             "recipe_ref", "previous_sha256", "review"))
        name = string(item["name"], "nama adaptor")
        domain = string(item["domain"], "domain adaptor")
        version = integer(item["version"], 1, MAX_VERSION)
        caps = tags(item["capabilities"], "label kemampuan")
        key = digest(item["artifact_sha256"])
        parent = None if item["previous_sha256"] is None else digest(item["previous_sha256"])
        ref = string(item["artifact_ref"], "rujukan artefak")
        recipe = string(item["recipe_ref"], "rujukan resep")
        if key not in payloads or key in catalogued or ref in refs or version in versions[name]:
            raise InputError("Adaptor hilang, ganda, atau memakai rujukan ulang.")
        status, review = _review(item["review"])
        if review is not None:
            pointer = review["review_ref"]
            if pointer == ref or pointer in refs:
                raise InputError("Rujukan review adaptor ganda.")
            refs.add(pointer)
        refs.add(ref)
        catalogued.add(key)
        versions[name][version] = {"name": name, "domain": domain, "version": version, "capabilities": caps,
                                   "artifact_sha256": key, "artifact_ref": ref, "recipe_ref": recipe,
                                   "previous_sha256": parent, "status": status, "review": review, **payloads[key]}
    if catalogued != payloads.keys():
        raise InputError("Ada payload adaptor di luar katalog.")

    rows = []
    groups = []
    for name, by_version in sorted(versions.items()):
        history = [item for _, item in sorted(by_version.items())]
        baseline = tuple(history[0][key] for key in ("domain", "base_sha256", "layer", "features", "outputs"))
        previous = None
        eligible = None
        for index, item in enumerate(history, 1):
            target = tuple(item[key] for key in ("domain", "base_sha256", "layer", "features", "outputs"))
            if (item["version"] != index or item["previous_sha256"] != previous or target != baseline):
                raise InputError("Riwayat adaptor putus atau berpindah layout/domain.")
            previous = item["artifact_sha256"]
            if item["status"] == "qualified":
                eligible = item["version"]
            rows.append(item)
        groups.append({"name": name, "domain": baseline[0], "latest_version": len(history),
                       "latest_qualified_version": eligible})
    return {"schema": "ace.forge-adapter-zoo.v1", "catalog_sha256": expected, "catalog_ref": source,
            "adapters": rows, "histories": groups}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("payloads", type=Path)
    parser.add_argument("--expect-catalog-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = catalog(decode(read_bytes(args.catalog, MAX_BYTES)), decode(read_bytes(args.payloads, MAX_BYTES)),
                         args.expect_catalog_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
