"""Bangun audit log produk berbentuk JSONL berantai hash.

Format memakai event bertipe dan pointer bukti. Snapshot baru hanya
dibuat jika rantai serta tail lama cocok. Tail disimpan pemanggil
secara terpisah untuk mendeteksi pemotongan yang valid secara lokal.
"""
import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text


MAX_ROWS=3000
MAX_BYTES=2_500_000
GENESIS="0"*64
UTC=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
STATUS={"allowed","denied","failed"}


def _policy(raw, expected):
    checked(raw,expected)
    schema(raw,"ace.factory-audit-policy.v1",("id","source_ref","operations"))
    product=identifier(raw["id"],"ID produk audit")
    source=text(raw["source_ref"],"Sumber audit")
    actions={}
    for row in entries(raw["operations"],120,minimum=1):
        obj(row,("id","source_ref"))
        key=identifier(row["id"],"Operasi audit")
        if key in actions:
            raise ContractError("Operasi audit ganda.")
        actions[key]=text(row["source_ref"],"Sumber operasi")
    return product,source,actions


def _normalize(raw, actions):
    obj(raw,("id","at","actor_ref","operation","target_ref","status","evidence_ref"))
    key=identifier(raw["id"],"ID event")
    at=text(raw["at"],"UTC event",20)
    action=identifier(raw["operation"],"Operasi")
    if not UTC.fullmatch(at) or action not in actions or not isinstance(raw["status"],str) or raw["status"] not in STATUS:
        raise ContractError("Timestamp, operasi atau hasil audit tidak sah.")
    datetime.fromisoformat(at.replace("Z","+00:00"))
    return {"id":key,"at":at,"operation":action,"status":raw["status"],"operation_ref":actions[action],
            **{field:identifier(raw[field],"ID referensi") for field in ("actor_ref","target_ref","evidence_ref")}}


def _hash(previous, item):
    return sha256(canonical({"previous_sha256":previous,"event":item})).hexdigest()


def _envelope(row):
    return {key:value for key,value in row.items() if key not in ("previous_sha256","event_sha256")}


def _scan(payload, actions, expected_last):
    if not isinstance(payload,bytes) or len(payload)>MAX_BYTES or (payload and not payload.endswith(b"\n")):
        raise ContractError("Snapshot audit terpotong atau melebihi batas.")
    digest(expected_last)
    rows=payload.splitlines()
    if len(rows)>MAX_ROWS:
        raise ContractError("Log melebihi batas baris.")
    previous=GENESIS
    marker=""
    seen={}
    for count,line in enumerate(rows,1):
        current=decode(line)
        obj(current,("id","at","actor_ref","operation","target_ref","status","evidence_ref","operation_ref",
                     "previous_sha256","event_sha256"))
        projection=_envelope(current)
        normalized=_normalize({key:value for key,value in projection.items() if key!="operation_ref"},actions)
        if (canonical(current)!=line or projection!=normalized or current["id"] in seen or current["at"]<marker
                or current["previous_sha256"]!=previous or current["event_sha256"]!=_hash(previous,projection)):
            raise ContractError(f"Rantai audit gagal pada baris {count}.")
        seen[current["id"]]=normalized
        previous=current["event_sha256"]
        marker=current["at"]
    if previous!=expected_last:
        raise ContractError("Tail log tidak sesuai anchor luar.")
    return seen,marker


def verify(payload, policy, expected, end):
    product,source,actions=_policy(policy,expected)
    index,_=_scan(payload,actions,end)
    by_operation={name:0 for name in sorted(actions)}
    by_result={name:0 for name in sorted(STATUS)}
    for item in index.values():
        by_operation[item["operation"]]+=1
        by_result[item["status"]]+=1
    return {"schema":"ace.factory-audit-report.v1","status":"verified","product_id":product,"source_ref":source,
            "policy_sha256":expected,"events":len(index),"by_operation":by_operation,"by_status":by_result,
            "log_sha256":sha256(payload).hexdigest(),"tail_sha256":end}


def extend(payload, policy, expected, end, additions):
    _,_,actions=_policy(policy,expected)
    seen,earliest=_scan(payload,actions,end)
    result=[payload]
    previous=end
    for item in entries(additions,MAX_ROWS):
        event=_normalize(item,actions)
        key=event["id"]
        if key in seen:
            if seen[key]!=event:
                raise ContractError("ID audit sudah dipakai untuk event berbeda.")
            continue
        if event["at"]<earliest:
            raise ContractError("Waktu event mundur.")
        if len(seen)>=MAX_ROWS:
            raise ContractError("Log melebihi batas baris.")
        hash_value=_hash(previous,event)
        result.append(canonical({**event,"previous_sha256":previous,"event_sha256":hash_value})+b"\n")
        seen[key]=event
        previous=hash_value
        earliest=event["at"]
    snapshot=b"".join(result)
    return snapshot,verify(snapshot,policy,expected,previous)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--expect-tail")
    parser.add_argument("--events",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if (args.source is None)!=(args.expect_tail is None) or (args.events is None)!=(args.output is None):
        parser.error("Snapshot/tail dan events/output harus diberikan berpasangan.")
    try:
        policy=decode(read(args.policy))
        payload=read(args.source,MAX_BYTES) if args.source else b""
        end=args.expect_tail or GENESIS
        if args.events:
            data,report=extend(payload,policy,args.expect_sha256,end,decode(read(args.events)))
            with args.output.open("xb") as target:
                target.write(data)
        else:
            report=verify(payload,policy,args.expect_sha256,end)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
