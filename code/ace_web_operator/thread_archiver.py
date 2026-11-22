"""Arsipkan utas yang diizinkan dengan reply chain dan redaksi eksplisit.

Snapshot dibaca dari kontrak. Pseudonim thread-scoped menggantikan
alias peserta dan pola sensitif dari kebijakan diringkas menjadi
penanda. Hash isi, urutan dan parent diperiksa ulang sebelum ekspor.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,identity,obj,read,schema,text
from .web_scheduler import time_value


REDACT="[tersunting]"


def _policy(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.thread-archive-plan.v1",("source_ref","thread","snapshot_sha256","permission_ref",
                                                   "consent","redact_terms"))
    key=identifier(plan["thread"],"ID utas")
    pointer=text(plan["source_ref"],"Asal pengarsipan")
    permission=text(plan["permission_ref"],"Izin arsip")
    if plan["consent"]!="archive_redacted":
        raise ContractError("Izin tidak mencakup pengarsipan redacted.")
    terms=[text(value,"Pola redaksi",200) for value in entries(plan["redact_terms"],70)]
    if len({value.casefold() for value in terms})!=len(terms):
        raise ContractError("Pola redaksi ganda.")
    return key,pointer,permission,terms


def _content(raw, patterns):
    if not isinstance(raw,str) or not raw.strip() or len(raw)>4000 or any(not (c.isprintable() or c in "\n\t") for c in raw):
        raise ContractError("Isi pesan di luar batas arsip.")
    count=0
    for pattern in patterns:
        raw,matches=pattern.subn(REDACT,raw)
        count+=matches
    return raw,count


def archive(snapshot,plan,expected):
    key,pointer,permission,terms=_policy(plan,expected)
    checked(snapshot,plan["snapshot_sha256"])
    schema(snapshot,"ace.web.thread-snapshot.v1",("id","source_ref","entries"))
    if snapshot["id"]!=key:
        raise ContractError("Snapshot menunjuk utas lain.")
    origin=text(snapshot["source_ref"],"Rujukan snapshot")
    participants=set()
    seen={}
    for row in entries(snapshot["entries"],1200):
        obj(row,("id","parent","actor","at","text","source_ref"))
        entry=identifier(row["id"],"ID pesan")
        actor=identifier(row["actor"],"Alias peserta")
        if entry in seen:
            raise ContractError("ID pesan ganda.")
        time_value(row["at"])
        participants.add(actor)
        seen[entry]=row
    sensitive=sorted(set(terms)|participants,key=lambda item:(-len(item),item))
    patterns=[re.compile(re.escape(value),re.I) for value in sensitive if value.casefold()!=REDACT.casefold()]
    ordered=sorted(seen.values(),key=lambda row:(row["at"],row["id"]))
    archived={}
    redactions=0
    for row in ordered:
        key_parent=row["parent"]
        if key_parent is not None and (identifier(key_parent,"ID parent") not in archived):
            raise ContractError("Reply parent tidak ada atau muncul sesudah pesan.")
        content,count=_content(row["text"],patterns)
        redactions+=count
        actor_hash=identity([key,row["actor"]])
        previous=archived[key_parent]["sha256"] if key_parent else None
        item={"id":row["id"],"parent":key_parent,"parent_sha256":previous,"actor_ref":"participant_"+actor_hash[:16],
              "at":row["at"],"body":content,"source_ref":text(row["source_ref"],"Rujukan pesan")}
        archived[item["id"]]={**item,"sha256":identity(item)}
    raw={"schema":"ace.web.thread-archive.v1","thread":key,"plan_sha256":expected,"snapshot_sha256":plan["snapshot_sha256"],
         "snapshot_ref":origin,"source_ref":pointer,"permission_ref":permission,"entries":list(archived.values())}
    blob=canonical(raw)+b"\n"
    anchor=sha256(blob).hexdigest()
    report=verify(blob,anchor)
    return blob,{**report,"redactions":redactions,"participants":len(participants)}


def verify(blob,expected):
    if not isinstance(blob,bytes) or len(blob)>9_000_000 or sha256(blob).hexdigest()!=digest(expected):
        raise ContractError("Archive berubah atau melebihi batas.")
    raw=decode(blob)
    schema(raw,"ace.web.thread-archive.v1",("thread","plan_sha256","snapshot_sha256","snapshot_ref","source_ref",
                                            "permission_ref","entries"))
    known={}
    last=None
    for row in entries(raw["entries"],1200):
        obj(row,("id","parent","parent_sha256","actor_ref","at","body","source_ref","sha256"))
        key=identifier(row["id"],"ID pesan")
        moment=(time_value(row["at"]),key)
        parent=row["parent"]
        payload={name:value for name,value in row.items() if name!="sha256"}
        if key in known or last is not None and moment<=last or row["sha256"]!=identity(payload) or (
                (parent is not None and parent not in known) or known.get(parent)!=row["parent_sha256"]
        ):
            raise ContractError("Kustodi reply chain tidak valid.")
        known[key]=row["sha256"]
        last=moment
    return {"schema":"ace.web.thread-archive-receipt.v1","archive_sha256":expected,"status":"verified",
            "thread":raw["thread"],"entries":len(known),"snapshot_ref":raw["snapshot_ref"],
            "plan_sha256":raw["plan_sha256"]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest="mode",required=True)
    draft=actions.add_parser("archive")
    for key in ("snapshot","plan","output"):
        draft.add_argument(key,type=Path)
    draft.add_argument("--expect-sha256",required=True)
    audit=actions.add_parser("verify")
    audit.add_argument("archive",type=Path)
    audit.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        if args.mode=="archive":
            blob,result=archive(decode(read(args.snapshot)),decode(read(args.plan)),args.expect_sha256)
            with args.output.open("xb") as stream:
                stream.write(blob)
        else:
            result=verify(read(args.archive,9_000_000),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,TypeError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
