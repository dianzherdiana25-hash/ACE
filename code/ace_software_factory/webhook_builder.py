"""Bangun amplop webhook lokal dan autentikasi HMAC dua arah.

Sender membentuk byte dan header untuk transport milik host. Receiver
memeriksa raw byte, lead/TTL, topik dan replay sebelum mengembalikan
payload. Modul tidak membuka jaringan atau membaca credential host.
"""
import argparse
from contextlib import closing
from hashlib import sha256
from hmac import compare_digest, digest
from pathlib import Path
import re
import sqlite3
import sys

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,integer,obj,read,schema,text


SIGNATURE=re.compile(r"[0-9a-f]{64}")


def _binary(value, label):
    if not isinstance(value,bytes) or not 32<=len(value)<=128:
        raise ContractError(f"Material {label} tidak tersedia atau di luar batas.")
    return value


def _config(policy,expected):
    checked(policy,expected)
    schema(policy,"ace.factory-webhook-policy.v1",("id","source_ref","topics","ttl_seconds","max_clock_lead","max_bytes"))
    product=identifier(policy["id"],"Issuer")
    text(policy["source_ref"],"Sumber policy")
    ttl=integer(policy["ttl_seconds"],"TTL event",10,900)
    lead=integer(policy["max_clock_lead"],"Toleransi clock",0,30)
    cap=integer(policy["max_bytes"],"Batas body",128,300_000)
    topics={}
    for entry in entries(policy["topics"],50,minimum=1):
        obj(entry,("id","source_ref"))
        topic=identifier(entry["id"],"Topik")
        if topic in topics:
            raise ContractError("Topik ganda.")
        topics[topic]=text(entry["source_ref"],"Rujukan topik")
    return product,ttl,lead,cap,topics


def _event(data, topics):
    obj(data,("id","topic","payload"))
    event=identifier(data["id"],"ID event")
    key=identifier(data["topic"],"Topik")
    if key not in topics or not isinstance(data["payload"],dict):
        raise ContractError("Topik atau body event di luar policy.")
    return event,key


def _mac(secret, product, time, body):
    prefix=f"ace-webhook-v1\n{product}\n{time}\n".encode()
    return digest(secret,prefix+body,"sha256").hex()


def prepare(policy,expected,event,at,key):
    product,_,_,cap,topics=_config(policy,expected)
    material=_binary(key,"signer")
    timestamp=integer(at,"Unix timestamp",0,2**40)
    _event(event,topics)
    body=canonical(event)
    if len(body)>cap:
        raise ContractError("Body melebihi batas.")
    headers={"content-type":"application/json","x-ace-time":str(timestamp),
             "x-ace-signature":_mac(material,product,timestamp,body)}
    return body,headers


def receiver_database(path):
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as connection,connection:
        connection.execute("CREATE TABLE seen(issuer TEXT, event TEXT, seen_at INTEGER, "
                           "fingerprint TEXT, PRIMARY KEY(issuer,event)) STRICT")


def accept(policy,expected,body,headers,now,key,replay_db):
    product,ttl,lead,cap,topics=_config(policy,expected)
    material=_binary(key,"receiver")
    current=integer(now,"Unix timestamp",0,2**40)
    if not isinstance(body,bytes) or len(body)>cap or not isinstance(headers,dict):
        return {"status":"rejected","reason":"body_or_headers"}
    signed=headers.get("x-ace-signature")
    time=headers.get("x-ace-time")
    if (headers.get("content-type")!="application/json" or not isinstance(signed,str) or not SIGNATURE.fullmatch(signed)
            or not isinstance(time,str) or not time.isascii() or not time.isdigit() or len(time)>13):
        return {"status":"rejected","reason":"headers_invalid"}
    start=int(time)
    if str(start)!=time or start>current+lead or current-start>=ttl:
        return {"status":"rejected","reason":"timestamp_outside_window"}
    if not compare_digest(signed,_mac(material,product,start,body)):
        return {"status":"rejected","reason":"signature_mismatch"}
    try:
        data=decode(body)
        event,topic=_event(data,topics)
    except (ValueError,TypeError,RecursionError):
        return {"status":"rejected","reason":"event_invalid"}
    anchor=sha256(body).hexdigest()
    path=Path(replay_db).absolute().as_uri()+"?mode=rw"
    with closing(sqlite3.connect(path,uri=True,isolation_level=None,timeout=3)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        prior=connection.execute("SELECT fingerprint FROM seen WHERE issuer=? AND event=?",(product,event)).fetchone()
        if prior is not None:
            return {"status":"duplicate" if prior[0]==anchor else "rejected",
                    "reason":"replay" if prior[0]==anchor else "event_identity_conflict","id":event}
        if connection.execute("SELECT count(*) FROM seen").fetchone()[0]>=50_000:
            return {"status":"rejected","reason":"replay_ledger_full"}
        connection.execute("INSERT INTO seen VALUES (?,?,?,?)",(product,event,current,anchor))
        connection.commit()
    return {"status":"accepted","id":event,"topic":topic,"topic_ref":topics[topic],"body_sha256":anchor,
            "payload":data["payload"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        product,ttl,lead,cap,topics=_config(decode(read(args.policy)),args.expect_sha256)
        result={"schema":"ace.factory-webhook-contract.v1","source_sha256":args.expect_sha256,"issuer":product,
                "ttl_seconds":ttl,"max_clock_lead":lead,"max_bytes":cap,"topics":topics,
                "signature":"ace-webhook-v1 / HMAC-SHA256","transport":"host_managed"}
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
