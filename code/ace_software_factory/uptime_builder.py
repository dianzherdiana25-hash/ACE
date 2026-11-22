"""Bangun monitor produk lokal dari probe kesehatan dan jadwal yang tercatat.

Setiap slot punya status up, down, atau unknown. Satu hitungan mencakup
hanya sampel teramati, dan batas bawah menghukum slot tanpa bukti.
Probe sekali jalan menghasilkan catatan yang dapat disimpan penjadwal.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text
from .load_test_builder import ROUTE, request


STAMP=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
MAX_SLOTS=12_000


def _time(value):
    if not isinstance(value,str) or not STAMP.fullmatch(value):
        raise ContractError("Timestamp monitor perlu UTC detik penuh.")
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())


def _format(time):
    return datetime.fromtimestamp(time,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _config(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-uptime-plan.v1",("source_ref","from","until","cadence_seconds","max_delay_seconds","components"))
    source=text(plan["source_ref"],"Sumber monitor")
    begin,end=_time(plan["from"]),_time(plan["until"])
    cadence=integer(plan["cadence_seconds"],"Interval probe",10,86_400)
    tolerance=integer(plan["max_delay_seconds"],"Toleransi waktu probe",0,cadence-1)
    if not 0<end-begin<=cadence*MAX_SLOTS or (end-begin)%cadence:
        raise ContractError("Rentang harus mencakup slot penuh dalam batas.")
    components={}
    for raw in entries(plan["components"],12,minimum=1):
        obj(raw,("id","port","path","ok_status","source_ref"))
        key=identifier(raw["id"],"ID komponen")
        path=text(raw["path"],"Endpoint health",150)
        if key in components or not ROUTE.fullmatch(path):
            raise ContractError("Komponen ganda atau path health tidak sah.")
        components[key]={"port":integer(raw["port"],"Port loopback",1024,65535),"path":path,
                         "ok":integer(raw["ok_status"],"HTTP status sukses",200,299),
                         "source_ref":text(raw["source_ref"],"Sumber komponen")}
    return source,begin,end,cadence,tolerance,components


def probe(plan,expected,at,*,client=request):
    _,begin,end,cadence,tolerance,components=_config(plan,expected)
    observed=_time(at)
    if not begin<=observed<end or (observed-begin)%cadence>tolerance:
        raise ContractError("Waktu penjadwal di luar slot probe.")
    rows=[]
    for key,rule in sorted(components.items()):
        result=client(rule["port"],rule["path"],3)
        status=result["status"]
        healthy=result["error"] is None and status==rule["ok"]
        rows.append({"component":key,"at":at,"state":"up" if healthy else "down",
                     "source_ref":f"{rule['source_ref']}#{at}"})
    return {"schema":"ace.factory-uptime-observations.v1","plan_sha256":expected,"rows":rows}


def evaluate(plan,expected,observations):
    source,begin,end,cadence,tolerance,components=_config(plan,expected)
    schema(observations,"ace.factory-uptime-observations.v1",("plan_sha256","rows"))
    if observations["plan_sha256"]!=expected:
        raise ContractError("Snapshot observasi merujuk rencana lain.")
    by_slot={}
    slot_count=(end-begin)//cadence
    for row in entries(observations["rows"],MAX_SLOTS*len(components)):
        obj(row,("component","at","state","source_ref"))
        key=identifier(row["component"],"ID komponen")
        moment=_time(row["at"])
        slot,delay=divmod(moment-begin,cadence)
        if key not in components or not 0<=slot<slot_count or delay>tolerance or (key,slot) in by_slot:
            raise ContractError("Observasi ganda, terlambat atau komponen tidak dikenal.")
        if row["state"] not in ("up","down"):
            raise ContractError("Observasi perlu up atau down.")
        by_slot[(key,slot)]=(row["state"],text(row["source_ref"],"Rujukan probe",200))
    recorded=[]
    for key,rule in sorted(components.items()):
        sequence=[by_slot.get((key,slot),("unknown",None)) for slot in range(slot_count)]
        counts=Counter(state for state,_ in sequence)
        observed=counts["up"]+counts["down"]
        transitions=[]
        last=None
        for i,(state,ref) in enumerate(sequence):
            if state!=last:
                transitions.append({"from":last,"to":state,"at":_format(begin+i*cadence),"source_ref":ref})
                last=state
        recorded.append({"component":key,"source_ref":rule["source_ref"],"up":counts["up"],"down":counts["down"],
                         "unknown":counts["unknown"],"uptime_observed":{"numerator":counts["up"],"denominator":observed}
                         if observed else None,
                         "uptime_lower_bound":{"numerator":counts["up"],"denominator":slot_count},
                         "recent_state":last,"transitions":transitions})
    return {"schema":"ace.factory-uptime-report.v1","plan_sha256":expected,"observations_sha256":identity(observations),
            "source_ref":source,"slots_per_component":slot_count,"cadence_seconds":cadence,"components":recorded}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe-at")
    mode.add_argument("--observations",type=Path)
    args=parser.parse_args(argv)
    try:
        plan=decode(read(args.plan))
        report=probe(plan,args.expect_sha256,args.probe_at) if args.probe_at else (
            evaluate(plan,args.expect_sha256,decode(read(args.observations))))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
