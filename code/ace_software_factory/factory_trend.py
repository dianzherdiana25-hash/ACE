"""Laporkan mutu pabrik lintas produk dari riwayat bench yang tertambat.

Setiap run memuat hash ringkasan dan identitas produk. Laju dilaporkan
bersama denominator, perubahan produk dipisah dari perubahan hasil,
dan permukaan tanpa sampel tidak diberi tingkat keberhasilan.
"""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,integer,obj,read,schema,text


SURFACES=("cli","service","web")
TIMESTAMP=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _time(raw):
    if not isinstance(raw,str) or not TIMESTAMP.fullmatch(raw):
        raise ContractError("Waktu run perlu UTC kanonis.")
    datetime.fromisoformat(raw.replace("Z","+00:00"))
    return raw


def _bench(row):
    schema(row,"ace.factory-bench-report.v1",("plan_sha256","source_ref","product_count","passed","status","products"))
    digest(row["plan_sha256"])
    text(row["source_ref"],"Sumber bench")
    expected=integer(row["product_count"],"Jumlah produk",1,100)
    expected_pass=integer(row["passed"],"Produk lulus",0,expected)
    products={}
    for raw in entries(row["products"],expected,minimum=expected):
        obj(raw,("product_id","surface","artifact_sha256","acceptance","counts","status"))
        key=identifier(raw["product_id"],"ID produk")
        verdict=raw["status"]
        if key in products or raw["surface"] not in SURFACES or verdict not in ("passed","failed","incomplete"):
            raise ContractError("Produk, surface atau verdict bench tidak konsisten.")
        detail=obj(raw["counts"],("passed","failed","missing_rule","missing_observation"))
        for count in detail.values():
            integer(count,"Census acceptance",0,1000)
        if verdict=="passed" and (detail["passed"]==0 or detail["failed"] or detail["missing_rule"] or detail["missing_observation"]):
            raise ContractError("Status bench lulus tanpa seluruh kriteria terpenuhi.")
        if (verdict=="failed")!=(detail["failed"]>0):
            raise ContractError("Kegagalan bench tidak sejalan dengan kriteria.")
        products[key]={"surface":raw["surface"],"verdict":verdict,"artifact_sha256":digest(raw["artifact_sha256"]),
                       "acceptance":text(raw["acceptance"],"Path receipt",300)}
    success=sum(item["verdict"]=="passed" for item in products.values())
    if success!=expected_pass or row["status"]!=("passed" if success==expected else "failed"):
        raise ContractError("Sensus produk berbeda dari header bench.")
    return products


def _rate(counter):
    complete=counter["passed"]+counter["failed"]
    return {"passed":counter["passed"],"failed":counter["failed"],"incomplete":counter["incomplete"],
            "completed":complete,"pass_rate_bp":counter["passed"]*10_000//complete if complete else None}


def summarize(plan, expected):
    checked(plan,expected)
    schema(plan,"ace.factory-trend-history.v1",("source_ref","runs"))
    source=text(plan["source_ref"],"Sumber riwayat")
    seen=set()
    ordered=[]
    for record in entries(plan["runs"],200):
        obj(record,("id","at","ref","bench_sha256","bench"))
        key=identifier(record["id"],"ID run")
        if key in seen:
            raise ContractError("ID run ganda.")
        seen.add(key)
        at=_time(record["at"])
        ref=text(record["ref"],"Pointer bukti",250)
        checked(record["bench"],record["bench_sha256"])
        products=_bench(record["bench"])
        ordered.append((at,key,ref,record["bench_sha256"],products))
    by_surface={surface:Counter() for surface in SURFACES}
    all_products=defaultdict(Counter)
    timeline=[]
    changes=[]
    prior=None
    for at,key,ref,anchor,products in sorted(ordered,key=lambda row:(row[0],row[1])):
        run_stats=Counter()
        for product,result in products.items():
            status=result["verdict"]
            by_surface[result["surface"]][status]+=1
            all_products[product][status]+=1
            run_stats[status]+=1
        timeline.append({"id":key,"at":at,"source_ref":ref,"bench_sha256":anchor,"stats":_rate(run_stats)})
        if prior is not None:
            before_key,before_products=prior
            for product in sorted(before_products.keys()|products.keys()):
                old,new=before_products.get(product),products.get(product)
                reason=None
                if old is None or new is None:
                    reason="product_added" if old is None else "product_removed"
                elif old["surface"]!=new["surface"]:
                    reason="surface_changed"
                elif old["verdict"]!=new["verdict"]:
                    reason="verdict_changed"
                if reason is not None:
                    changes.append({"product_id":product,"reason":reason,"from_run":before_key,"to_run":key,
                                    "before":old,"after":new})
        prior=key,products
    return {"schema":"ace.factory-trend-report.v1","plan_sha256":expected,"source_ref":source,
            "run_count":len(timeline),"timeline":timeline,"by_surface":{key:_rate(by_surface[key]) for key in SURFACES},
            "by_product":{key:_rate(all_products[key]) for key in sorted(all_products)},"changes":changes}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=summarize(decode(read(args.history)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
