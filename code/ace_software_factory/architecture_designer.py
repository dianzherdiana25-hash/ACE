"""Rancang arsitektur dari spesifikasi dan kebutuhan data yang disetujui.

Setiap kebutuhan mempunyai rancangan pemanggil dan titik uji.
Keputusan storage bergantung pada retensi yang dinyatakan. Graf
memisahkan entry point, logika domain, dan boundary persistence.
Perubahan di luar keputusan yang disetujui tidak diisi otomatis.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, obj, read, schema, text


ENTRY = {"web": "http_adapter", "cli": "command_adapter", "service": "worker_adapter"}
STORES = {"none": "none", "ephemeral": "memory", "durable": "sqlite"}


def design(spec, decision):
    obj(decision, ("spec_sha256", "data_retention", "storage_ref", "interfaces"))
    checked(spec, decision["spec_sha256"])
    schema(spec, "ace.factory-product-spec.v1", ("brief_sha256", "product_id", "name", "surface", "objective",
                                                "objective_ref", "requirements", "constraints", "non_goals", "pending", "status"))
    surface = spec["surface"]
    if spec["status"] != "ready" or spec["pending"] != [] or surface not in ENTRY:
        raise ContractError("Spesifikasi belum siap dirancang.")
    store_ref = text(decision["storage_ref"], "Rujukan keputusan data", 200)
    retention = decision["data_retention"]
    if not isinstance(retention, str) or retention not in STORES:
        raise ContractError("Retensi data belum diakui.")
    store = STORES[retention]

    requirements = {}
    for row in entries(spec["requirements"], 512, minimum=1):
        obj(row, ("id","statement","source_ref","acceptance"))
        key = identifier(row["id"], "Kebutuhan")
        if key in requirements:
            raise ContractError("ID kebutuhan ganda.")
        checks = []
        for item in entries(row["acceptance"], 128, minimum=1):
            obj(item, ("statement","source_ref"))
            checks.append(text(item["source_ref"], "Rujukan acceptance", 200))
        requirements[key] = (text(row["source_ref"], "Rujukan kebutuhan", 200), checks)

    entry = ENTRY[surface]
    calls = []
    seen = set()
    covered = defaultdict(list)
    uses_store = set()
    for row in entries(decision["interfaces"], 512, minimum=1):
        obj(row, ("id","requirement","input_shape","output_shape","persist","source_ref"))
        key = identifier(row["id"], "ID interaksi")
        need = identifier(row["requirement"], "ID kebutuhan interaksi")
        if key in seen or need not in requirements or type(row["persist"]) is not bool:
            raise ContractError("Interaksi ganda, tanpa kebutuhan, atau retensi ambigu.")
        seen.add(key)
        if row["persist"]:
            if store == "none":
                raise ContractError("Interaksi meminta persistence yang belum disetujui.")
            uses_store.add(need)
        covered[need].append(key)
        calls.append({"id": key, "entry": entry, "use_case": need,
                      "input_shape": text(row["input_shape"], "Bentuk masukan"),
                      "output_shape": text(row["output_shape"], "Bentuk keluaran"),
                      "source_ref": text(row["source_ref"], "Rujukan interaksi", 200),
                      "data_boundary": "repository" if row["persist"] else None})
    missing = sorted(requirements.keys()-covered.keys())
    components = [{"id": entry, "layer": "boundary", "depends_on": ["use_cases"]},
                  {"id": "use_cases", "layer": "domain", "depends_on": ["repository"] if uses_store else []}]
    if uses_store:
        components.extend([{"id": "repository", "layer": "port", "depends_on": []},
                           {"id": f"{store}_repository", "layer": "adapter", "depends_on": ["repository"]}])
    return {"schema":"ace.factory-architecture.v1", "product_id":identifier(spec["product_id"],"Produk"),
            "surface":surface, "spec_sha256":decision["spec_sha256"],"decision_sha256":identity(decision),
            "components":components, "data_policy":{"retention":retention,"implementation":store,"source_ref":store_ref},
            "interfaces":sorted(calls,key=lambda item:item["id"]),
            "trace":[{"requirement":key,"source_ref":value[0],"acceptance_refs":value[1],
                      "interfaces":sorted(covered[key]),"uses_repository":key in uses_store}
                     for key,value in sorted(requirements.items())],
            "unmapped_requirements":missing, "status":"missing_interfaces" if missing else "ready"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec",type=Path)
    parser.add_argument("decisions",type=Path)
    args=parser.parse_args(argv)
    try:
        product=design(decode(read(args.spec)),decode(read(args.decisions)))
        sys.stdout.buffer.write(canonical(product)+b"\n")
    except (OSError,OverflowError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(product["status"]!="ready")


if __name__ == "__main__":
    raise SystemExit(main())
