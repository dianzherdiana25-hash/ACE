"""Bandingkan data katalog lintas situs dari snapshot yang dapat ditelusuri.

Produk dicocokkan melalui peta SKU yang disetujui. Mata uang, tanggal,
stok dan biaya tambahan diperiksa. Data yang tidak dapat dibandingkan
tetap muncul sebagai gap, tanpa konversi atau perkiraan harga.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


MAX_MONEY=10**12


def compare(plan,expected,feed):
    checked(plan,expected)
    schema(plan,"ace.web.compare-plan.v1",("source_ref","feed_sha256","currency","as_of","max_age_seconds","sites","products"))
    source=text(plan["source_ref"],"Sumber peta")
    checked(feed,plan["feed_sha256"])
    schema(feed,"ace.web.comparison-feed.v1",("source_ref","observations"))
    feed_ref=text(feed["source_ref"],"Rujukan feed")
    currency=plan["currency"]
    if not isinstance(currency,str) or len(currency)!=3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise ContractError("Mata uang perlu tiga huruf uppercase.")
    now=time_value(plan["as_of"])
    maximum_age=integer(plan["max_age_seconds"],"Usia data maksimum",60,86400*30)
    sites=[identifier(value,"ID situs") for value in entries(plan["sites"],24,2)]
    if len(set(sites))!=len(sites):
        raise ContractError("ID situs ganda.")
    mapping={}
    keys={}
    for row in entries(plan["products"],500,1):
        obj(row,("id","skus","source_ref"))
        key=identifier(row["id"],"ID produk kanonis")
        if key in keys:
            raise ContractError("Produk kanonis ganda.")
        aliases=obj(row["skus"],sites)
        keys[key]=text(row["source_ref"],"Sumber padanan produk")
        for site,raw in sorted(aliases.items()):
            sku=text(raw,"SKU sumber",120)
            if (site,sku) in mapping:
                raise ContractError("SKU situs menunjuk dua produk.")
            mapping[(site,sku)]=key
    observations={}
    unrelated=[]
    for row in entries(feed["observations"],8000):
        obj(row,("site","sku","at","currency","price","shipping","in_stock","source_ref"))
        key=(identifier(row["site"],"ID situs"),text(row["sku"],"SKU sumber",120))
        if key in observations:
            raise ContractError("Observasi ganda pada satu situs dan SKU.")
        ref=text(row["source_ref"],"Sumber observasi")
        stamp=time_value(row["at"])
        if stamp>now or type(row["in_stock"]) is not bool:
            raise ContractError("Timestamp atau status stok tidak sah.")
        price=integer(row["price"],"Harga per unit minor",0,MAX_MONEY) if row["price"] is not None else None
        freight=integer(row["shipping"],"Biaya per unit minor",0,MAX_MONEY) if row["shipping"] is not None else None
        if key not in mapping:
            unrelated.append({"site":key[0],"sku":key[1],"source_ref":ref})
            continue
        reason=("currency_mismatch" if row["currency"]!=currency else "stale" if now-stamp>maximum_age else
                "out_of_stock" if not row["in_stock"] else "unknown_total" if price is None or freight is None else None)
        observations[key]={"site":key[0],"sku":key[1],"source_ref":ref,"at":row["at"],"reason":reason,
                           "total_minor_units":price+freight if reason is None else None}
    products=[]
    for product,pointer in sorted(keys.items()):
        offers=[]
        for (site,sku),target in sorted(mapping.items()):
            if target==product:
                offers.append(observations.get((site,sku),{"site":site,"sku":sku,"source_ref":None,
                                                           "reason":"missing","total_minor_units":None}))
        valid=[item for item in offers if item["total_minor_units"] is not None]
        ordered=sorted(valid,key=lambda item:(item["total_minor_units"],item["site"]))
        minimum=ordered[0]["total_minor_units"] if len(ordered)>=2 else None
        products.append({"id":product,"source_ref":pointer,"offers":offers,"comparable_count":len(ordered),
                         "lowest_sites":[item["site"] for item in ordered if item["total_minor_units"]==minimum],
                         "spread_minor_units":ordered[-1]["total_minor_units"]-minimum if minimum is not None else None})
    return {"schema":"ace.web.comparison-report.v1","plan_sha256":expected,"feed_sha256":identity(feed),
            "source_ref":source,"feed_ref":feed_ref,"currency":currency,"as_of":plan["as_of"],"products":products,
            "unmapped":[item for item in sorted(unrelated,key=lambda row:(row["site"],row["sku"]))]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("feed",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=compare(decode(read(args.plan)),args.expect_sha256,decode(read(args.feed)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
