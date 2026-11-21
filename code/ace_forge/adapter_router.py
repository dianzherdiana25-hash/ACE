"""Rekomendasikan adaptor domain berdasarkan kemampuan dan budget lokal.

Setiap task menunjuk basis dan lapisan kompatibel. Hanya review
qualified yang masuk ranking. Domain eksplisit mendapat prioritas
atas domain umum saat fallback sudah diizinkan. Bukti tiap pilihan
dan alasan penolakan tercatat untuk dibandingkan secara offline.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

from . import adapter_zoo
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import MAX_FEATURES
from .dataset_forge import MAX_BYTES
from .multitask_merge import MAX_RANK


MAX_QUERIES = 2000


def _query(raw):
    object_fields(raw, ("id", "query_ref", "domain", "base_sha256", "layer", "capabilities",
                        "features", "outputs", "maximum_rank", "allow_general"))
    if type(raw["allow_general"]) is not bool:
        raise InputError("Izin fallback harus boolean.")
    return {"id": string(raw["id"], "ID tugas"), "query_ref": string(raw["query_ref"], "rujukan tugas"),
            "domain": string(raw["domain"], "domain"), "base_sha256": digest(raw["base_sha256"]),
            "layer": string(raw["layer"], "lapisan"),
            "features": integer(raw["features"], 1, MAX_FEATURES),
            "outputs": integer(raw["outputs"], 1, MAX_FEATURES),
            "capabilities": set(adapter_zoo.tags(raw["capabilities"], "label kemampuan")),
            "maximum_rank": integer(raw["maximum_rank"], 1, MAX_RANK), "allow_general": raw["allow_general"]}


def _decide(query, options):
    reject = Counter()
    valid = []
    required = query["capabilities"]
    domain = query["domain"]
    for item in options:
        if item["domain"] != domain and (item["domain"] != "*" or not query["allow_general"]):
            reject["domain_mismatch"] += 1
            continue
        if item["status"] != "qualified":
            reject["not_qualified"] += 1
            continue
        if item["rank"] > query["maximum_rank"]:
            reject["rank_limit"] += 1
            continue
        available = set(item["capabilities"])
        if not required <= available:
            reject["missing_capability"] += 1
            continue
        valid.append((item["domain"] != domain, len(available-required), item["rank"],
                      item["name"], -item["version"], item))
    base = {"id": query["id"], "query_ref": query["query_ref"], "domain": domain,
            "required_capabilities": sorted(required), "compatible_artifacts": len(options),
            "eligible_artifacts": len(valid), "rejection_counts": dict(sorted(reject.items()))}
    if not valid:
        return {**base, "status": "unrouted", "selection": None,
                "reason": "no_eligible_adapter" if options else "no_compatible_layout"}
    fallback, surplus, rank, name, neg_version, winner = min(valid)
    return {**base, "status": "general_fallback" if fallback else "exact_domain", "reason": None,
            "selection": {"name": name, "version": -neg_version, "artifact_ref": winner["artifact_ref"],
                          "artifact_sha256": winner["artifact_sha256"],
                          "rank": rank, "surplus_capabilities": surplus, **winner["review"]}}


def _layout(item):
    return tuple(item[key] for key in ("base_sha256", "layer", "features", "outputs"))


def route(raw, manifest, snapshots, expected):
    object_fields(raw, ("request_ref", "catalog_sha256", "queries"))
    if identity(raw) != digest(expected):
        raise InputError("Permintaan routing berbeda dari anchor.")
    source = string(raw["request_ref"], "rujukan routing")
    catalog = adapter_zoo.catalog(manifest, snapshots, raw["catalog_sha256"])
    options = defaultdict(list)
    for item in catalog["adapters"]:
        options[_layout(item)].append(item)
    ids, refs = set(), {source}
    rows = []
    stats = defaultdict(Counter)
    for record in entries(raw["queries"], MAX_QUERIES):
        query = _query(record)
        key, pointer = query["id"], query["query_ref"]
        if key in ids or pointer in refs:
            raise InputError("Identitas atau rujukan tugas ganda.")
        ids.add(key)
        refs.add(pointer)
        decision = _decide(query, options.get(_layout(query), []))
        stats[query["domain"]][decision["status"]] += 1
        rows.append(decision)
    return {"schema": "ace.forge-adapter-routing.v1", "request_ref": source, "request_sha256": expected,
            "catalog_ref": catalog["catalog_ref"], "catalog_sha256": catalog["catalog_sha256"],
            "routes": sorted(rows, key=lambda row: row["id"]),
            "coverage": [{"domain": domain, "queries": sum(counts.values()),
                          "exact_domain": counts["exact_domain"], "general_fallback": counts["general_fallback"],
                          "unrouted": counts["unrouted"]} for domain, counts in sorted(stats.items())]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("payloads", type=Path)
    parser.add_argument("--expect-request-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        request, manifest, payloads = (decode(read_bytes(path, MAX_BYTES)) for path in
                                        (args.request, args.catalog, args.payloads))
        result = route(request, manifest, payloads, args.expect_request_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
