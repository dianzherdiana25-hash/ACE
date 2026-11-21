"""Susun keranjang di halaman fixture dengan batas anggaran dan stok.

Rencana browser hanya memakai halaman katalog dan kontrol jumlah/tambah.
Receipt menyatakan jumlah item yang teramati setelah simulasi lokal.
Checkout, order, pembayaran, dan permintaan POST tidak tersedia.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text,web_path


def compile_cart(plan,expected,catalog):
    checked(plan,expected)
    schema(plan,"ace.web.cart-plan.v1",("source_ref","catalog_sha256","browser","page","summary_test_id",
                                       "max_minor_units","cart"))
    checked(catalog,plan["catalog_sha256"])
    schema(catalog,"ace.web.fixture-catalog.v1",("source_ref","items"))
    pointer=text(plan["source_ref"],"Sumber permintaan keranjang")
    text(catalog["source_ref"],"Sumber katalog")
    configuration=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    view=web_path(plan["page"])
    if any(segment.casefold() in ("pay","payment","checkout","order","purchase")
           for path in entries(configuration["allow_paths"],70,1) for segment in web_path(path).split("/")):
        raise ContractError("Path checkout dan pembayaran dilarang.")
    summary=identifier(plan["summary_test_id"],"Kontrol ringkasan")
    available={}
    selectors={summary}
    for raw in entries(catalog["items"],500,1):
        obj(raw,("id","stock","unit_minor","amount_test_id","add_test_id","source_ref"))
        key=identifier(raw["id"],"Produk")
        amount=identifier(raw["amount_test_id"],"Kontrol jumlah")
        action=identifier(raw["add_test_id"],"Kontrol tambah")
        if key in available or amount==action or {amount,action}&selectors:
            raise ContractError("Produk atau kontrol katalog ganda.")
        if any("checkout" in value or "payment" in value for value in (amount,action)):
            raise ContractError("Kontrol pembelian tidak boleh didaftarkan.")
        selectors.update((amount,action))
        available[key]=(integer(raw["stock"],"Stok",0,10_000),integer(raw["unit_minor"],"Harga unit fixture",0,10**9),
                        amount,action,text(raw["source_ref"],"Sumber produk"))
    max_spend=integer(plan["max_minor_units"],"Batas unit minor",0,10**12)
    added={}
    operations=[{"id":"open_catalog","op":"navigate","path":view}]
    total=units=0
    for entry in entries(plan["cart"],12,1):
        obj(entry,("item","quantity"))
        key=identifier(entry["item"],"ID pilihan")
        quantity=integer(entry["quantity"],"Jumlah",1,500)
        if key in added or key not in available:
            raise ContractError("Item permintaan ganda atau tidak dikenal.")
        stock,unit_price,amount,action,source_ref=available[key]
        if stock<quantity:
            raise ContractError(f"Stok fixture kurang pada {key}.")
        subtotal=quantity*unit_price
        total+=subtotal
        units+=quantity
        if total>max_spend:
            raise ContractError("Rencana melebihi batas unit minor.")
        added[key]={"id":key,"quantity":quantity,"sub_total_minor":subtotal,"source_ref":source_ref}
        index=len(added)
        operations.extend([{"id":f"quantity_{index}","op":"fill","test_id":amount,"value":str(quantity)},
                           {"id":f"add_{index}","op":"click","test_id":action}])
    operations.append({"id":"verify_summary","op":"expect_text","test_id":summary,"expected":f"{units} item"})
    contract={"schema":"ace.web.browser-plan.v1","source_ref":pointer,**configuration,"steps":operations}
    browser_engine.compile_plan(contract,identity(contract))
    return contract,list(added.values()),total


def prepare(plan,expected,catalog,*,browser=browser_engine.run):
    browser_plan,items,total=compile_cart(plan,expected,catalog)
    anchor=identity(browser_plan)
    record=browser(browser_plan,anchor)
    if record.get("plan_sha256")!=anchor:
        raise ContractError("Receipt browser menunjuk keranjang berbeda.")
    return {"schema":"ace.web.cart-receipt.v1","plan_sha256":expected,"browser_sha256":anchor,
            "source_ref":plan["source_ref"],"items":items,"total_minor_fixture":total,"checkout":False,
            "status":"prepared_locally" if record["status"]=="completed" else "held","reason":record["reason"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("catalog",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=prepare(decode(read(args.plan)),args.expect_sha256,decode(read(args.catalog)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="prepared_locally")


if __name__=="__main__":
    raise SystemExit(main())
