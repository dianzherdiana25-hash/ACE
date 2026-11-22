"""Ukur kesehatan situs fixture melalui probe yang terdaftar.

Probe memakai transport loopback dengan timeout dan ukuran terbatas.
Status, latency, tipe media dan kondisi isi ditimbang terpisah.
Kesalahan transport tidak dianggap respons HTTP dan tidak memiliki skor sukses.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from time import perf_counter_ns

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,origin,read,schema,text,web_path
from ._http import fetch


def probe(plan,expected,*,transport=fetch,clock=perf_counter_ns):
    checked(plan,expected)
    schema(plan,"ace.web.health-plan.v1",("source_ref","sites","checks"))
    pointer=text(plan["source_ref"],"Rujukan health check")
    sites={}
    for row in entries(plan["sites"],30,1):
        obj(row,("id","origin","source_ref"))
        label=identifier(row["id"],"Situs")
        if label in sites:
            raise ContractError("Situs ganda.")
        sites[label]=(origin(row["origin"])[0],text(row["source_ref"],"Rujukan situs"))
    checks={}
    for row in entries(plan["checks"],50,1):
        obj(row,("id","site","path","status","media_type","json_equals","timeout_seconds","latency_ms","source_ref"))
        key=identifier(row["id"],"Pemeriksaan")
        site=identifier(row["site"],"Situs pemeriksaan")
        if key in checks or site not in sites:
            raise ContractError("Pemeriksaan ganda atau tanpa situs.")
        assertion=row["json_equals"]
        if assertion is not None:
            obj(assertion,("key","value"))
            identifier(assertion["key"],"Kunci bukti")
            if row["media_type"]!="application/json":
                raise ContractError("Assertion JSON membutuhkan media aplikasi JSON.")
        checks[key]=(site,web_path(row["path"]),integer(row["status"],"Status harapan",100,599),
                     text(row["media_type"],"Media",80),assertion,integer(row["timeout_seconds"],"Timeout",1,6),
                     integer(row["latency_ms"],"Ambang latency",1,6000),text(row["source_ref"],"Sumber probe"))
    if sum(row[5] for row in checks.values())>120:
        raise ContractError("Budget waktu probe melebihi batas.")
    observations=[]
    for key,(site,path,status,media,assertion,timeout,latency,source) in sorted(checks.items()):
        base,ref=sites[site]
        begin=clock()
        response=transport(base,path,cap=150_000,timeout=timeout)
        elapsed=clock()-begin
        if elapsed<0:
            raise ContractError("Clock tidak monoton.")
        reasons=[]
        if response.error:
            reasons.append(response.error)
        else:
            if response.status!=status:
                reasons.append("unexpected_status")
            if response.media_type!=media:
                reasons.append("unexpected_media_type")
            if assertion is not None and response.media_type==media:
                try:
                    actual=decode(response.body)
                    name=assertion["key"]
                    if not isinstance(actual,dict) or name not in actual or identity(actual[name])!=identity(assertion["value"]):
                        reasons.append("body_assertion_failed")
                except (ValueError,RecursionError):
                    reasons.append("invalid_json")
        if elapsed>latency*1_000_000:
            reasons.append("slow")
        observations.append({"id":key,"site":site,"path":path,"site_ref":ref,"source_ref":source,
                             "http_status":response.status,"elapsed_ns":elapsed,"state":"healthy" if not reasons else (
                                 "degraded" if reasons==["slow"] else "unhealthy"),"reasons":reasons,
                             "body_sha256":sha256(response.body).hexdigest() if response.error is None else None})
    return {"schema":"ace.web.health-receipt.v1","plan_sha256":expected,"source_ref":pointer,
            "checks":observations,"status":"healthy" if all(row["state"]=="healthy" for row in observations) else
                "unhealthy" if any(row["state"]=="unhealthy" for row in observations) else "degraded"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=probe(decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="healthy")


if __name__=="__main__":
    raise SystemExit(main())
