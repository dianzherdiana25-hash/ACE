"""Bangun revisi katalog produk dari snapshot dan delta lokal yang disetujui.

Delta memakai hash sebelum perubahan untuk tiap SKU. Retire menandai
produk beserta alasan, dengan bukti sebelum dan sesudah. Snapshot lama
tetap terbaca dan tidak pernah ditimpa.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text


def _entry(raw,categories):
    obj(raw,("sku","name","category","stock","price_minor","source_ref","status","retire_ref"))
    sku=identifier(raw["sku"],"SKU")
    category=identifier(raw["category"],"Kategori")
    state=raw["status"]
    if category not in categories or state not in ("active","retired") or (state=="active")!=(raw["retire_ref"] is None):
        raise ContractError("Status atau kategori produk tidak sah.")
    if raw["retire_ref"] is not None:
        text(raw["retire_ref"],"Rujukan retire")
    return {"sku":sku,"name":text(raw["name"],"Nama produk",120),"category":category,
            "stock":integer(raw["stock"],"Stock",0,10**7),"price_minor":integer(raw["price_minor"],"Harga minor",0,10**12),
            "source_ref":text(raw["source_ref"],"Sumber produk"),"status":state,"retire_ref":raw["retire_ref"]}


def revise(snapshot,delta,expected):
    checked(delta,expected)
    schema(delta,"ace.web.catalog-delta.v1",("source_ref","shop","base_sha256","changes"))
    checked(snapshot,delta["base_sha256"])
    schema(snapshot,"ace.web.catalog-snapshot.v1",("source_ref","shop","currency","categories","revision","items"))
    shop=identifier(snapshot["shop"],"Toko")
    source=text(delta["source_ref"],"Sumber delta")
    text(snapshot["source_ref"],"Sumber katalog")
    currency=text(snapshot["currency"],"Mata uang",3)
    if not (currency.isascii() and currency.isupper() and currency.isalpha() and len(currency)==3) or shop!=delta["shop"]:
        raise ContractError("Toko atau mata uang tidak cocok.")
    before=integer(snapshot["revision"],"Revisi awal",0,2**53-2)
    category_list=[identifier(value,"Kategori") for value in entries(snapshot["categories"],150,1)]
    categories=set(category_list)
    if len(categories)!=len(category_list):
        raise ContractError("Daftar kategori ganda.")
    items={}
    for raw in entries(snapshot["items"],5000):
        value=_entry(raw,categories)
        sku=value["sku"]
        if sku in items:
            raise ContractError("SKU ganda pada snapshot.")
        items[sku]=value
    changes={}
    for row in entries(delta["changes"],1500,1):
        obj(row,("operation","sku","expected_sha256","product","source_ref"))
        sku=identifier(row["sku"],"SKU")
        ref=text(row["source_ref"],"Sumber perubahan")
        op=row["operation"]
        if sku in changes or op not in ("upsert","retire"):
            raise ContractError("Delta memiliki dua aksi pada SKU yang sama atau aksi tak dikenal.")
        old=items.get(sku)
        old_anchor=identity(old) if old is not None else None
        if row["expected_sha256"] is not None:
            digest(row["expected_sha256"])
        if old_anchor!=row["expected_sha256"]:
            raise ContractError(f"Versi produk berbeda untuk {sku}.")
        if op=="retire":
            if old is None or old["status"]!="active" or row["product"] is not None:
                raise ContractError("Hanya produk aktif yang dapat ditandai retired.")
            updated={**old,"status":"retired","retire_ref":ref}
        else:
            updated=_entry(row["product"],categories)
            if updated["sku"]!=sku or updated["status"]!="active" or identity(updated)==old_anchor:
                raise ContractError("Delta produk tidak sah atau tidak mengubah snapshot.")
        items[sku]=updated
        changes[sku]={"sku":sku,"operation":op,"before_sha256":old_anchor,"after_sha256":identity(updated),"source_ref":ref}
    if len(items)>5000:
        raise ContractError("Katalog baru melampaui batas.")
    result={**snapshot,"revision":before+1,"items":[items[key] for key in sorted(items)],"source_ref":source}
    report={"schema":"ace.web.catalog-revision-receipt.v1","delta_sha256":expected,"source_ref":source,"shop":shop,
            "before_sha256":delta["base_sha256"],"after_sha256":identity(result),"revision":before+1,
            "changes":[changes[key] for key in sorted(changes)]}
    return result,report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("snapshot","delta","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output,report=revise(decode(read(args.snapshot)),decode(read(args.delta)),args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(canonical(output)+b"\n")
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
