"""Bandingkan snapshot halaman berkala yang dapat ditautkan kembali.

Perbedaan byte dipisahkan dari perubahan teks yang terlihat di blok
terdaftar. Ignorasi hanya memakai daftar ID yang didokumentasikan.
Hasil menyimpan hash blok serta lokasi sumber, tanpa status rekaan.
"""
import argparse
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text
from .page_extractor import Snapshot,MAX_HTML


STAMP=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
TAGS={"article","div","section","li","tr","p","h1","h2","h3"}


def _snap(raw,payload,suppressed):
    obj(raw,("at","artifact_ref","sha256"))
    moment=text(raw["at"],"Waktu capture",20)
    if not STAMP.fullmatch(moment):
        raise ContractError("Capture perlu waktu UTC kanonis.")
    datetime.fromisoformat(moment.replace("Z","+00:00"))
    pointer=text(raw["artifact_ref"],"Rujukan snapshot",230)
    anchor=digest(raw["sha256"])
    if not isinstance(payload,bytes) or len(payload)>MAX_HTML or sha256(payload).hexdigest()!=anchor:
        raise ContractError("Byte snapshot berbeda dari manifest atau terlalu besar.")
    dom=Snapshot(payload)
    blocks={}
    for node in dom.elements:
        key=node.attrs.get("data-watch")
        if key is None:
            continue
        key=identifier(key,"ID blok")
        if key in suppressed:
            continue
        if node.tag not in TAGS or key in blocks:
            raise ContractError("Blok watcher ganda atau tag tidak didukung.")
        nested=node.parent
        while nested is not None:
            if nested.attrs.get("data-watch") is not None:
                raise ContractError("Blok watcher tidak boleh bertumpuk.")
            nested=nested.parent
        normalized=node.text()
        blocks[key]={"sha256":sha256(normalized.encode()).hexdigest(),"chars":len(normalized),
                     "line":node.line,"artifact_ref":pointer}
    return {"at":moment,"artifact_ref":pointer,"sha256":anchor,"blocks":blocks}


def compare(plan,expected,before,after):
    checked(plan,expected)
    schema(plan,"ace.web.page-watch-plan.v1",("source_ref","site","ignore_blocks","before","after"))
    source=text(plan["source_ref"],"Aturan pemantauan")
    site=identifier(plan["site"],"ID halaman")
    ignored=[identifier(key,"ID blok diabaikan") for key in entries(plan["ignore_blocks"],100)]
    if len(set(ignored))!=len(ignored):
        raise ContractError("Daftar blok diabaikan ganda.")
    old=_snap(plan["before"],before,set(ignored))
    new=_snap(plan["after"],after,set(ignored))
    if old["at"]>=new["at"]:
        raise ContractError("Waktu snapshot tidak berurutan.")
    first,second=old.pop("blocks"),new.pop("blocks")
    rows=[]
    for key in sorted(first.keys()|second.keys()):
        a,b=first.get(key),second.get(key)
        if a is None:
            state="added"
        elif b is None:
            state="removed"
        elif a["sha256"]!=b["sha256"]:
            state="changed"
        else:
            continue
        rows.append({"id":key,"change":state,"before":a,"after":b})
    bytes_changed=old["sha256"]!=new["sha256"]
    if not first and not second:
        status="no_tracked_blocks"
    elif rows:
        status="changed"
    else:
        status="only_untracked_bytes_changed" if bytes_changed else "unchanged"
    return {"schema":"ace.web.page-watch-receipt.v1","plan_sha256":expected,"source_ref":source,
            "site":site,"before":old,"after":new,"bytes_changed":bytes_changed,"changes":rows,
            "known_blocks_before":len(first),"known_blocks_after":len(second),"ignored":sorted(ignored),"status":status}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","before","after"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=compare(decode(read(args.plan)),args.expect_sha256,read(args.before,MAX_HTML),read(args.after,MAX_HTML))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
