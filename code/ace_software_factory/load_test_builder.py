"""Uji beban kecil terhadap produk loopback dengan skrip yang bisa diaudit.

Request GET dijadwalkan dengan laju, paralelisme dan kuota terbatas.
Hasil memisahkan respons, timeout, dan kegagalan transport. Tidak ada
proxy, redirect, pergantian target otomatis, atau request eksternal.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.client import HTTPConnection, HTTPException
from pathlib import Path
import re
import sys
from time import monotonic, perf_counter_ns, sleep

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .perf_profiler import _statistics


ROUTE=re.compile(r"/(?:[a-z0-9_-]+(?:/[a-z0-9_-]+)*)?")


def _ready(plan, expected):
    checked(plan,expected)
    schema(plan,"ace.factory-load-plan.v1",("source_ref","host","port","rate","workers","timeout_seconds","max_p95_ns","cases"))
    text(plan["source_ref"],"Sumber beban")
    if plan["host"]!="127.0.0.1":
        raise ContractError("Uji ini hanya menerima host IPv4 loopback.")
    limits={"port":integer(plan["port"],"Port produk",1024,65535),
            "rate":integer(plan["rate"],"Laju maksimum",1,12),"workers":integer(plan["workers"],"Paralelisme",1,6),
            "timeout":integer(plan["timeout_seconds"],"Timeout",1,5),
            "max_p95":integer(plan["max_p95_ns"],"Ambang p95",1,5_000_000_000)}
    seen=set()
    tasks=[]
    for raw in entries(plan["cases"],20,minimum=1):
        obj(raw,("id","path","count","accept_status","source_ref"))
        key=identifier(raw["id"],"ID skenario")
        address=text(raw["path"],"Rute fixture",120)
        allowed=integer(raw["accept_status"],"HTTP status",100,599)
        if key in seen or not ROUTE.fullmatch(address):
            raise ContractError("Rute GET tidak sah atau skenario ganda.")
        seen.add(key)
        cap=integer(raw["count"],"Jumlah request",1,30)
        source=text(raw["source_ref"],"Sumber skenario")
        tasks.extend((key,address,allowed,source) for _ in range(cap))
    if len(tasks)>60:
        raise ContractError("Rencana melebihi 60 request lokal.")
    return limits,tasks


def request(port, path, timeout):
    started=perf_counter_ns()
    status=None
    received=None
    error=None
    try:
        with closing(HTTPConnection("127.0.0.1",port,timeout=timeout)) as peer:
            peer.request("GET",path,headers={"Accept":"application/json","Connection":"close"})
            output=peer.getresponse()
            received=len(output.read(128_001))
            if received>128_000:
                error="response_limit"
            else:
                status=output.status
    except TimeoutError:
        error="timeout"
    except (OSError,HTTPException):
        error="transport"
    return {"status":status,"error":error,"received_bytes":received,"elapsed_ns":perf_counter_ns()-started}


def run(plan, expected, *, probe=request, clock=monotonic, wait=sleep):
    limits,tasks=_ready(plan,expected)
    scheduled=[]
    with ThreadPoolExecutor(max_workers=limits["workers"]) as pool:
        next_slot=clock()
        for key,path,status,source in tasks:
            delay=next_slot-clock()
            if delay>0:
                wait(delay)
            future=pool.submit(probe,limits["port"],path,limits["timeout"])
            scheduled.append(((key,path,status,source),future))
            next_slot=max(next_slot+1/limits["rate"],clock()+1/limits["rate"])
        results=[]
        for number,((key,path,status,source),future) in enumerate(scheduled,1):
            response=future.result()
            results.append({"index":number,"case":key,"path":path,"source_ref":source,**response,
                            "expected_status":status,"matched":status==response["status"] and response["error"] is None})
    stats=_statistics([row["elapsed_ns"] for row in results if row["matched"]])
    failures=sum(not row["matched"] for row in results)
    too_slow=stats is not None and stats["p95_ns"]>limits["max_p95"]
    return {"schema":"ace.factory-load-report.v1","plan_sha256":expected,"source_ref":plan["source_ref"],
            "requests":len(tasks),"failed":failures,"statistics":stats,"p95_exceeds_limit":too_slow,
            "status":"failed" if failures or too_slow else "passed","measurements":results}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=run(decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="passed")


if __name__=="__main__":
    raise SystemExit(main())
