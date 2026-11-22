"""Jalankan riset harga berkala dari slot UTC dan snapshot yang terdaftar.

Setiap slot due diperiksa terhadap feed dengan anchor sendiri. Komparasi
menyimpan nilai yang memiliki bukti dan melaporkan slot tanpa feed.
Runner bekerja lokal dan tidak memperoleh harga dari jaringan.
"""
import argparse
from pathlib import Path
import sys

from . import cross_site_comparator,web_scheduler
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text


def run(plan,expected,schedule,history,feeds):
    checked(plan,expected)
    schema(plan,"ace.web.price-research-plan.v1",("source_ref","schedule_sha256","history_sha256","feeds_sha256",
                                                  "workflow_sha256","task","comparison"))
    checked(schedule,plan["schedule_sha256"])
    checked(history,plan["history_sha256"])
    checked(feeds,plan["feeds_sha256"])
    pointer=text(plan["source_ref"],"Sumber riset")
    task=identifier(plan["task"],"Nama tugas harga")
    workflow=digest(plan["workflow_sha256"])
    compare_config=obj(plan["comparison"],("source_ref","currency","max_age_seconds","sites","products"))
    summary=web_scheduler.schedule(schedule,plan["schedule_sha256"],history)
    schema(feeds,"ace.web.price-feeds.v1",("source_ref","snapshots"))
    text(feeds["source_ref"],"Sumber kumpulan feed")
    indexed={}
    for row in entries(feeds["snapshots"],100):
        obj(row,("scheduled_at","feed_sha256","feed","source_ref"))
        stamp=row["scheduled_at"]
        web_scheduler.time_value(stamp)
        checked(row["feed"],row["feed_sha256"])
        if stamp in indexed:
            raise ContractError("Dua feed menunjuk slot yang sama.")
        indexed[stamp]=(row["feed_sha256"],row["feed"],text(row["source_ref"],"Rujukan feed"))
    due=[row for row in summary["slots"] if row["task"]==task and row["status"]=="due"]
    if not any(row["id"]==task and row["workflow_sha256"]==workflow for row in schedule["tasks"]) or (
            any(row["workflow_sha256"]!=workflow for row in due)
    ):
        raise ContractError("Jadwal tidak menambatkan tugas dan workflow harga.")
    count=integer(len(due),"Jumlah slot harga",0,100)
    results=[]
    baseline={}
    for slot in due:
        at=slot["at"]
        record={"at":at,"slot_sha256":slot["id"],"schedule_ref":slot["source_ref"],
                "status":"missing_snapshot","feed_ref":None,"comparison":None,"changes":[]}
        if at in indexed:
            anchor,feed,ref=indexed[at]
            comparison={"schema":"ace.web.compare-plan.v1",**compare_config,"feed_sha256":anchor,"as_of":at}
            outcome=cross_site_comparator.compare(comparison,identity(comparison),feed)
            changes=[]
            for product in outcome["products"]:
                usable=[row["total_minor_units"] for row in product["offers"] if row["total_minor_units"] is not None]
                current=min(usable) if len(usable)>=2 else None
                key=product["id"]
                if current is not None and key in baseline:
                    prior=baseline[key]
                    changes.append({"product":key,"from":prior[0],"to":at,"delta_minor_units":current-prior[1],
                                    "before_feed_sha256":prior[2],"after_feed_sha256":anchor})
                if current is not None:
                    baseline[key]=(at,current,anchor)
            record.update(status="compared",feed_ref=ref,comparison=outcome,changes=changes)
        results.append(record)
    missing=sum(item["status"]=="missing_snapshot" for item in results)
    return {"schema":"ace.web.price-research-report.v1","plan_sha256":expected,"source_ref":pointer,
            "scheduler_summary_sha256":identity(summary),"due":count,"missing_feeds":missing,"slots":results,
            "status":"no_due_slots" if not count else "partial" if missing else "complete"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","schedule","history","feeds"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=run(decode(read(args.plan)),args.expect_sha256,
                   *(decode(read(getattr(args,key))) for key in ("schedule","history","feeds")))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="partial")


if __name__=="__main__":
    raise SystemExit(main())
