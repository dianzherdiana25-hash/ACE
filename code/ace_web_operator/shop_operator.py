"""Periksa inventaris dashboard toko fixture milik akun yang diberi izin.

Setiap produk dipetakan ke kontrol stok dan rujukan katalog. Browser
memeriksa kepemilikan serta angka per produk sebelum memberi receipt.
Operasi ini hanya memakai panel baca yang terdaftar.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,origin,read,schema,text,web_path


ORDERS={"checkout","order","payment","purchase","publish","delete","update"}


def compile_inspection(plan, expected, roster):
    checked(plan,expected)
    schema(plan,"ace.web.shop-inspection.v1",("source_ref","inventory_sha256","approval_ref","browser",
                                              "shop","path","owner_test_id","owner_label"))
    checked(roster,plan["inventory_sha256"])
    schema(roster,"ace.web.shop-inventory.v1",("source_ref","shop","origin","items"))
    pointer=text(plan["source_ref"],"Sumber inspeksi")
    approval=text(plan["approval_ref"],"Izin baca toko")
    key=identifier(plan["shop"],"ID toko")
    config=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    base,_=origin(config["origin"])
    if key!=roster["shop"] or base!=roster["origin"]:
        raise ContractError("Katalog dan izin tidak menunjuk toko atau origin yang sama.")
    path=web_path(plan["path"])
    if any(ORDERS & set(web_path(value).casefold().split("/")) for value in entries(config["allow_paths"],70,1)):
        raise ContractError("Rute transaksi atau mutasi tidak boleh dipakai.")
    owner_id=identifier(plan["owner_test_id"],"Selector pemilik fixture")
    owner_label=text(plan["owner_label"],"Label pemilik fixture",150)
    steps=[{"id":"open_shop","op":"navigate","path":path},
           {"id":"confirm_shop","op":"expect_text","test_id":owner_id,"expected":owner_label}]
    items={}
    selectors={owner_id}
    for row in entries(roster["items"],30,1):
        obj(row,("sku","stock","stock_test_id","source_ref"))
        sku=identifier(row["sku"],"SKU")
        locator=identifier(row["stock_test_id"],"Selector stok")
        if sku in items or locator in selectors:
            raise ContractError("SKU atau selector stok ganda.")
        selectors.add(locator)
        units=integer(row["stock"],"Stok fixture",0,100_000)
        operation_id=f"audit_{len(items)+1}"
        items[sku]={"sku":sku,"expected_units":units,"source_ref":text(row["source_ref"],"Sumber stok"),
                    "proof_step":operation_id}
        steps.append({"id":operation_id,"op":"expect_text","test_id":locator,"expected":f"{units} unit"})
    manifest={"schema":"ace.web.browser-plan.v1","source_ref":pointer,**config,"steps":steps}
    browser_engine.compile_plan(manifest,identity(manifest))
    return manifest,list(items.values()),approval


def inspect(plan,expected,roster,*,browser=browser_engine.run):
    manifest,items,approval=compile_inspection(plan,expected,roster)
    anchor=identity(manifest)
    observed=browser(manifest,anchor)
    if observed.get("plan_sha256")!=anchor:
        raise ContractError("Receipt menunjuk inspeksi lain.")
    outcomes={row["id"]:row for row in observed["steps"]}
    for product in items:
        result=outcomes.get(product.pop("proof_step"))
        product.update(status=result["status"] if result else "not_started",proof=result["evidence"] if result else None)
    passed=observed["status"]=="completed"
    return {"schema":"ace.web.shop-inspection-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,
            "shop":plan["shop"],"source_ref":plan["source_ref"],"approval_ref":approval,
            "items":items,"status":"inventory_confirmed" if passed else "held","reason":observed["reason"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","roster"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=inspect(decode(read(args.plan)),args.expect_sha256,decode(read(args.roster)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="inventory_confirmed")


if __name__=="__main__":
    raise SystemExit(main())
