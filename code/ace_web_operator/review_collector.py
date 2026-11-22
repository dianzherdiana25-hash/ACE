"""Kumpulkan ulasan lintas situs dari snapshot tanpa identitas penulis.

Skala bintang ditambatkan ke definisi situs. Duplikat dari konten dan
produk yang sama diarsipkan sebagai rujukan tambahan. Perbedaan rating
pada salinan yang sama tetap dilaporkan.
"""
import argparse
from decimal import Decimal
from pathlib import Path
import re
import sys
from unicodedata import normalize

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


SCORE=re.compile(r"(?:0|[1-9][0-9]?)(?:\.[0-9]{1,3})?")


def _rating(value,scale):
    if value is None:
        return None
    if not isinstance(value,str) or not SCORE.fullmatch(value):
        raise ContractError("Rating perlu decimal kanonis sesuai skala.")
    number=Decimal(value)
    if number>scale:
        raise ContractError("Rating di atas skala situs.")
    return int(number*10_000/scale)


def collect(plan,expected,source):
    checked(plan,expected)
    schema(plan,"ace.web.review-plan.v1",("source_ref","data_sha256","sites","products"))
    checked(source,plan["data_sha256"])
    schema(source,"ace.web.review-snapshot.v1",("source_ref","rows"))
    pointer=text(plan["source_ref"],"Rujukan aturan ulasan")
    data_ref=text(source["source_ref"],"Rujukan snapshot ulasan")
    scales={}
    for row in entries(plan["sites"],50,1):
        obj(row,("id","scale","source_ref"))
        site=identifier(row["id"],"Situs")
        if site in scales:
            raise ContractError("Situs ganda.")
        scales[site]=(integer(row["scale"],"Skala rating",1,20),text(row["source_ref"],"Sumber skala"))
    ordered=[identifier(key,"Produk") for key in entries(plan["products"],200,1)]
    if len(set(ordered))!=len(ordered):
        raise ContractError("Produk ganda.")
    known=set(ordered)
    seen=set()
    clusters={}
    for row in entries(source["rows"],6000):
        obj(row,("id","site","product","rating","observed_at","review","source_ref","snapshot_sha256"))
        key=identifier(row["id"],"ID ulasan situs")
        site=identifier(row["site"],"Situs ulasan")
        product=identifier(row["product"],"Produk ulasan")
        if (site,key) in seen or site not in scales or product not in known:
            raise ContractError("Ulasan ganda atau rujukan situs/produk tak dikenal.")
        seen.add((site,key))
        snippet=text(row["review"],"Isi ulasan",2000)
        normalized=" ".join(normalize("NFKC",snippet).casefold().split())
        merge=identity([product,normalized])
        time_value(row["observed_at"])
        record={"id":key,"site":site,"observed_at":row["observed_at"],
                "rating_bp":_rating(row["rating"],scales[site][0]),"scale_ref":scales[site][1],
                "source_ref":text(row["source_ref"],"Bukti sumber"),"snapshot_sha256":digest(row["snapshot_sha256"])}
        clusters.setdefault((product,merge),{"sources":[]})["sources"].append({**record,"snippet":snippet})
    reports=[]
    for (product,anchor),cluster in sorted(clusters.items()):
        refs=sorted(cluster["sources"],key=lambda row:(row["site"],row["id"]))
        variants=sorted({row["rating_bp"] for row in refs if row["rating_bp"] is not None})
        copy_excerpt=refs[0]["snippet"][:160]
        reports.append({"product":product,"content_sha256":anchor,"excerpt":copy_excerpt,
                        "sources":[{name:value for name,value in row.items() if name!="snippet"} for row in refs],
                        "rating_bp":variants[0] if len(variants)==1 else None,
                        "rating_status":"conflicting" if len(variants)>1 else "known" if variants else "unknown"})
    census={}
    for key in sorted(known):
        subset=[row for row in reports if row["product"]==key]
        ratings=[row["rating_bp"] for row in subset if row["rating_bp"] is not None]
        census[key]={"unique":len(subset),"rated":len(ratings),"mean_bp":sum(ratings)//len(ratings) if ratings else None,
                     "disputes":sum(row["rating_status"]=="conflicting" for row in subset)}
    return {"schema":"ace.web.review-report.v1","plan_sha256":expected,"data_sha256":plan["data_sha256"],
            "source_ref":pointer,"data_ref":data_ref,"source_rows":len(seen),"unique_reviews":len(reports),
            "by_product":census,"reviews":reports}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("snapshot",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        record=collect(decode(read(args.plan)),args.expect_sha256,decode(read(args.snapshot)))
        sys.stdout.buffer.write(canonical(record)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
