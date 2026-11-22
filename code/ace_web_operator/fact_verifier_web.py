"""Periksa satu fakta terstruktur dengan observasi dua penerbit independen.

Kebijakan penerbit mengikat host, grup kontrol editorial, dan referensi
registrasi. Salinan hash yang sama tidak memberi suara tambahan.
Bukti bertentangan dipertahankan dalam hasil.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,obj,read,schema,text
from .search_reader import address


def _source_index(registry):
    schema(registry,"ace.web.publisher-registry.v1",("source_ref","publishers"))
    text(registry["source_ref"],"Sumber daftar penerbit")
    mapped={}
    for row in entries(registry["publishers"],150,1):
        obj(row,("host","owner_group","source_ref"))
        _,host=address("https://"+text(row["host"],"Host terdaftar",250)+"/")
        if host!=row["host"] or host in mapped:
            raise ContractError("Host penerbit perlu kanonis dan unik.")
        mapped[host]=(identifier(row["owner_group"],"Grup penerbit"),text(row["source_ref"],"Rujukan penerbit"))
    return mapped


def verify(plan,expected,registry,evidence):
    checked(plan,expected)
    schema(plan,"ace.web.fact-plan.v1",("id","source_ref","registry_sha256","evidence_sha256","claim"))
    checked(registry,plan["registry_sha256"])
    checked(evidence,plan["evidence_sha256"])
    subject=obj(plan["claim"],("subject","predicate","value","unit","scope"))
    matches={key:text(subject[key],key,150) for key in ("subject","predicate","unit","scope")}
    wanted=identity(subject["value"])
    key=identifier(plan["id"],"ID klaim")
    source=text(plan["source_ref"],"Sumber klaim")
    publishers=_source_index(registry)
    schema(evidence,"ace.web.fact-observations.v1",("observations",))
    proof=[]
    excluded=[]
    seen=set()
    groups=set()
    bytes_seen=set()
    for row in entries(evidence["observations"],300):
        obj(row,("id","address","html_sha256","artifact_ref","observation"))
        evidence_id=identifier(row["id"],"ID observasi")
        if evidence_id in seen:
            raise ContractError("Observasi ganda.")
        seen.add(evidence_id)
        url,host=address(row["address"])
        anchor=digest(row["html_sha256"])
        pointer=text(row["artifact_ref"],"Rujukan bukti",230)
        values=obj(row["observation"],("subject","predicate","value","unit","scope"))
        reason=None
        if host not in publishers:
            reason="unregistered_publisher"
        elif any(values[field]!=content for field,content in matches.items()):
            reason="different_scope_or_subject"
        elif anchor in bytes_seen:
            reason="shared_document_bytes"
        if reason:
            excluded.append({"id":evidence_id,"reason":reason,"source_ref":pointer})
            continue
        bytes_seen.add(anchor)
        owner,registry_ref=publishers[host]
        observed=identity(values["value"])
        stance="support" if observed==wanted else "contradiction"
        if stance=="support":
            groups.add(owner)
        proof.append({"id":evidence_id,"address":url,"artifact_ref":pointer,"html_sha256":anchor,"registry_ref":registry_ref,
                      "ownership_group":owner,"value_sha256":observed,"verdict":stance})
    proof.sort(key=lambda row:row["id"])
    if any(row["verdict"]=="contradiction" for row in proof):
        result="disputed"
    elif len(groups)>=2:
        result="verified_fixture_scopes"
    else:
        result="insufficient_independent_sources"
    return {"schema":"ace.web.fact-report.v1","plan_sha256":expected,"claim_id":key,"source_ref":source,
            "claim_value_sha256":wanted,"status":result,"support_groups":sorted(groups),
            "evidence":proof,"excluded":sorted(excluded,key=lambda row:row["id"])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","registry","evidence"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=verify(decode(read(args.plan)),args.expect_sha256,decode(read(args.registry)),decode(read(args.evidence)))
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(output["status"]!="verified_fixture_scopes")


if __name__=="__main__":
    raise SystemExit(main())
