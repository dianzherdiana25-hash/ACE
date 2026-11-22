"""Rancang reservasi yang bisa dibatalkan pada kalender fixture.

Pilihan slot menegakkan kapasitas, waktu, dan margin pembatalan.
Simulasi apply/undo mengikat versi kalender sehingga plan basi tidak
membuat reservasi. Keluaran hanya mengubah representasi data baru.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,integer,obj,read,schema,text
from .web_scheduler import time_value


def _calendar(snapshot):
    schema(snapshot,"ace.web.booking-fixture.v1",("source_ref","slots","reservations"))
    text(snapshot["source_ref"],"Sumber kalender fixture")
    slots={}
    for raw in entries(snapshot["slots"],200,1):
        obj(raw,("id","start","end","cancel_until","capacity","source_ref"))
        key=identifier(raw["id"],"ID slot daftar")
        start,end,cancel=(time_value(raw[field]) for field in ("start","end","cancel_until"))
        if key in slots or not cancel<=start<end:
            raise ContractError("Slot ganda atau jendela pembatalan tidak sah.")
        slots[key]=(start,end,cancel,integer(raw["capacity"],"Kapasitas fixture",1,500),
                    text(raw["source_ref"],"Sumber slot"))
    occupied={key:0 for key in slots}
    ids=set()
    for row in entries(snapshot["reservations"],2000):
        obj(row,("id","slot","places"))
        key=identifier(row["id"],"ID reservasi")
        place=identifier(row["slot"],"Slot reservasi")
        if key in ids or place not in slots:
            raise ContractError("Reservasi ganda atau slot tidak dikenal.")
        ids.add(key)
        occupied[place]+=integer(row["places"],"Kursi",1,500)
        if occupied[place]>slots[place][3]:
            raise ContractError("Snapshot kalender melebihi kapasitas.")
    return slots,occupied,ids


def propose(plan,expected,snapshot):
    checked(plan,expected)
    schema(plan,"ace.web.booking-plan.v1",("id","source_ref","snapshot_sha256","approval_ref","now","earliest",
                                          "latest","minimum_cancel_seconds","places"))
    checked(snapshot,plan["snapshot_sha256"])
    slots,occupied,ids=_calendar(snapshot)
    key=identifier(plan["id"],"ID reservasi baru")
    refer=text(plan["source_ref"],"Sumber tugas")
    now,earliest,latest=(time_value(plan[field]) for field in ("now","earliest","latest"))
    if key in ids or not now<=earliest<latest:
        raise ContractError("ID reservasi ganda atau interval invalid.")
    buffer=integer(plan["minimum_cancel_seconds"],"Margin pembatalan",60,86400*7)
    places=integer(plan["places"],"Kursi fixture",1,500)
    result={"schema":"ace.web.booking-intent.v1","plan_sha256":expected,"snapshot_sha256":plan["snapshot_sha256"],
            "source_ref":refer,"reservation_id":key,"slot":None,"places":places,"approval_ref":None,
            "status":"held","reason":"approval_missing","simulated_only":True}
    if plan["approval_ref"] is None:
        return result
    approved=text(plan["approval_ref"],"Sumber izin")
    candidates=[]
    for name,(start,end,cancel,cap,pointer) in slots.items():
        if earliest<=start<end<=latest and cancel-now>=buffer and cap-occupied[name]>=places:
            candidates.append((start,name,cancel,pointer))
    if not candidates:
        return {**result,"approval_ref":approved,"reason":"no_cancellable_capacity"}
    start,name,cancel,pointer=min(candidates)
    return {**result,"approval_ref":approved,"status":"planned","reason":None,
            "slot":{"id":name,"source_ref":pointer,"start_unix":start,"cancel_until_unix":cancel}}


def apply_fixture(plan,expected,snapshot):
    intent=propose(plan,expected,snapshot)
    if intent["status"]!="planned":
        return None,intent
    result=deepcopy(snapshot)
    item={"id":intent["reservation_id"],"slot":intent["slot"]["id"],"places":intent["places"]}
    result["reservations"].append(item)
    _calendar(result)
    return result,{**intent,"status":"simulated_reserved","undo":{"item":item,"before_sha256":identity(snapshot),
                   "reserved_sha256":identity(result),"cancel_until_unix":intent["slot"]["cancel_until_unix"]}}


def undo_fixture(current,given,now):
    obj(given,("item","before_sha256","reserved_sha256","cancel_until_unix"))
    checked(current,given["reserved_sha256"])
    _calendar(current)
    if time_value(now)>integer(given["cancel_until_unix"],"Tenggat undo",0,2**40):
        raise ContractError("Jendela pembatalan sudah lewat.")
    result=deepcopy(current)
    if given["item"] not in result["reservations"]:
        raise ContractError("Reservasi fixture untuk undo tidak ditemukan.")
    result["reservations"].remove(given["item"])
    if identity(result)!=digest(given["before_sha256"]):
        raise ContractError("Undo tidak dapat membuktikan state semula.")
    return result,{"schema":"ace.web.booking-undo-receipt.v1","status":"simulated_cancelled",
                   "restored_sha256":identity(result),"reservation_id":given["item"]["id"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("calendar",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--fixture-output",type=Path)
    args=parser.parse_args(argv)
    try:
        plan,snapshot=decode(read(args.plan)),decode(read(args.calendar))
        if args.fixture_output is None:
            report=propose(plan,args.expect_sha256,snapshot)
        else:
            result,report=apply_fixture(plan,args.expect_sha256,snapshot)
            if result is not None:
                with args.fixture_output.open("xb") as stream:
                    stream.write(canonical(result)+b"\n")
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
