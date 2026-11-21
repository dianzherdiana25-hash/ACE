"""Terapkan feedback produk pada field deklaratif dengan preimage jelas.

Perubahan hanya masuk bila report menunjuk byte kontrak lama, evidence,
dan nilai sebelumnya. Builder produk dijalankan ulang sehingga perbaikan
kontrak yang tidak dapat dibangun menahan seluruh paket.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

from . import cli_builder, mobile_builder
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, identity, obj, read, schema, text
from .repo_scaffolder import materialize


EDITABLE={
    "ace.factory-cli-plan.v1": (cli_builder.build, {"description","max_input_bytes"}, "commands", {"help"}),
    "ace.factory-mobile-plan.v1": (mobile_builder.build, {"summary","max_records"}, "tabs", {"title","input"}),
}


def _locate(contract, item, field, globals_allowed, group, local_allowed):
    if item is None:
        if field not in globals_allowed:
            raise ContractError("Field tidak termasuk perbaikan yang didukung.")
        return contract
    key=identifier(item,"ID item")
    if field not in local_allowed:
        raise ContractError("Field item tidak termasuk perbaikan yang didukung.")
    matches=[row for row in contract[group] if row.get("id")==key]
    if len(matches)!=1:
        raise ContractError("ID item tidak menunjuk tepat satu konfigurasi.")
    return matches[0]


def fix(current, campaign, expected):
    checked(campaign,expected)
    schema(campaign,"ace.factory-feedback-campaign.v1",("product_sha256","source_ref","issues"))
    checked(current,campaign["product_sha256"])
    pointer=text(campaign["source_ref"],"Sumber triase")
    flavor=current.get("schema")
    if not isinstance(flavor,str) or flavor not in EDITABLE:
        raise ContractError("Jenis kontrak produk belum bisa diperbaiki.")
    builder,globals_allowed,group,local_allowed=EDITABLE[flavor]
    builder(current,campaign["product_sha256"])
    candidate=deepcopy(current)
    touched=set()
    cases={}
    for issue in entries(campaign["issues"],40,minimum=1):
        obj(issue,("id","source_ref","evidence_sha256","change"))
        key=identifier(issue["id"],"ID feedback")
        source=text(issue["source_ref"],"Rujukan feedback",220)
        checked_evidence=digest(issue["evidence_sha256"])
        change=obj(issue["change"],("item","field","before","after"))
        item=change["item"]
        if item is not None:
            identifier(item,"ID item")
        field=identifier(change["field"],"Field perbaikan")
        location=(item,field)
        if key in cases or location in touched:
            raise ContractError("Feedback ganda atau dua usulan menyentuh field yang sama.")
        touched.add(location)
        settings=_locate(candidate,item,field,globals_allowed,group,local_allowed)
        if identity(settings[field])!=identity(change["before"]) or identity(change["before"])==identity(change["after"]):
            raise ContractError("Preimage field berbeda atau perubahan kosong.")
        settings[field]=change["after"]
        cases[key]={"id":key,"source_ref":source,"evidence_sha256":checked_evidence,"item":item,"field":field,
                    "before_sha256":identity(change["before"]),"after_sha256":identity(change["after"])}
    updated=identity(candidate)
    files,receipt=builder(candidate,updated)
    report={"schema":"ace.factory-feedback-receipt.v1","campaign_sha256":expected,"source_ref":pointer,
            "before_sha256":campaign["product_sha256"],"after_sha256":updated,
            "changes":[cases[key] for key in sorted(cases)],"build_receipt_sha256":identity(receipt),
            "status":"rebuilt"}
    result={f"product/{path}":data for path,data in files.items()}
    result.update({"updated_product.json":canonical(candidate)+b"\n",
                   "prior_product.json":canonical(current)+b"\n",
                   "feedback_receipt.json":canonical(report)+b"\n"})
    return result,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("current","campaign","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=fix(decode(read(args.current)),decode(read(args.campaign)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
