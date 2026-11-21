"""Uji konektor deklaratif terhadap exchange fixture tanpa jaringan.

Setiap operasi menjalani expected response dan expected failure dari
snapshot. Transport fixture memeriksa origin, rute dan batas byte.
Kasus keliru atau operasi tanpa cakupan tercatat eksplisit.
"""
import argparse
from pathlib import Path
import sys

from . import api_connector_builder
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,integer,obj,read,schema,text,web_path
from ._http import Observation


def run(connector,suite,expected):
    checked(suite,expected)
    schema(suite,"ace.web.connector-sandbox.v1",("connector_sha256","source_ref","cases"))
    checked(connector,suite["connector_sha256"])
    source=text(suite["source_ref"],"Sumber sandbox")
    ids=set()
    covered=set()
    observations=[]
    for raw in entries(suite["cases"],100,1):
        obj(raw,("id","operation","parameters","exchange","expected","source_ref"))
        key=identifier(raw["id"],"ID kasus")
        operation=identifier(raw["operation"],"Operasi")
        ref=text(raw["source_ref"],"Rujukan fixture")
        if key in ids:
            raise ContractError("ID fixture ganda.")
        ids.add(key)
        exchange=obj(raw["exchange"],("path","status","media_type","body"))
        path=web_path(exchange["path"])
        status=integer(exchange["status"],"HTTP status",100,599)
        mime=text(exchange["media_type"],"Jenis media",80)
        body=canonical(exchange["body"])
        outcome=obj(raw["expected"],("status","reason","body"))
        calls=[]
        def local(base,address,*,cap):
            calls.append(address)
            if base!=connector["origin"] or address!=path:
                return Observation(None,None,b"","fixture_route_mismatch")
            if len(body)>cap:
                return Observation(status,None,b"","body_limit")
            return Observation(status,mime,body,None)
        actual,record=api_connector_builder.invoke(connector,suite["connector_sha256"],operation,
                                                     raw["parameters"],transport=local)
        matches=(record["status"]==outcome["status"] and record["reason"]==outcome["reason"]
                 and identity(actual)==identity(outcome["body"]) and calls==[path])
        covered.add(operation)
        observations.append({"id":key,"operation":operation,"source_ref":ref,"requested_paths":calls,
                             "matched":matches,"receipt":record})
    untested=sorted(connector["operations"].keys()-covered)
    failing=sorted(row["id"] for row in observations if not row["matched"])
    return {"schema":"ace.web.connector-sandbox-report.v1","suite_sha256":expected,
            "connector_sha256":suite["connector_sha256"],"source_ref":source,"status":"verified" if not untested and not failing else "held",
            "untested_operations":untested,"failed_cases":failing,"cases":observations}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("connector",type=Path)
    parser.add_argument("suite",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=run(decode(read(args.connector)),decode(read(args.suite)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="verified")


if __name__=="__main__":
    raise SystemExit(main())
