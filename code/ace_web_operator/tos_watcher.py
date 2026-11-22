"""Bandingkan klausul syarat layanan dari snapshot yang di-anchor.

Label penting berasal dari dokumen yang diberi penanda oleh operator.
Laporan membuat delta kata, perubahan label, dan pointer klausul lama
serta baru untuk telaah. Tool tidak mengubah aturan situs.
"""
import argparse
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,identifier,obj,read,schema,text
from .page_extractor import MAX_HTML,Snapshot
from .web_scheduler import time_value


CLASSES={"general","data_use","payment_terms","account_controls","publication","dispute","retention"}


def _clauses(row,html):
    obj(row,("sha256","at","ref"))
    at=time_value(row["at"])
    ref=text(row["ref"],"Rujukan snapshot",250)
    anchor=digest(row["sha256"])
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("Byte syarat layanan tidak cocok.")
    result={}
    for element in Snapshot(html).elements:
        if "data-term-id" not in element.attrs:
            continue
        key=identifier(element.attrs["data-term-id"],"ID klausul")
        category=element.attrs.get("data-term-class")
        value=text(element.text(),"Klausul",2500)
        if key in result or category not in CLASSES or len(result)>=250:
            raise ContractError("Klausul ganda, tanpa kategori, atau melampaui batas.")
        result[key]={"class":category,"line":element.line,"source_ref":ref,
                     "text_sha256":sha256(value.encode()).hexdigest(),"content":value}
    return at,result


def _diff(before,after):
    old=before["content"].split()
    new=after["content"].split()
    added=removed=0
    for state,i,j,k,l in SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
        if state!="equal":
            removed+=j-i
            added+=l-k
    return {"added_words":added,"removed_words":removed}


def _reference(row):
    return None if row is None else {key:value for key,value in row.items() if key!="content"}


def compare(plan,expected,before,after):
    checked(plan,expected)
    schema(plan,"ace.web.tos-watch-plan.v1",("site","source_ref","before","after"))
    site=identifier(plan["site"],"Situs")
    pointer=text(plan["source_ref"],"Aturan baca")
    first,a=_clauses(plan["before"],before)
    last,b=_clauses(plan["after"],after)
    if first>=last:
        raise ContractError("Tanggal revisi tidak berurutan.")
    changes=[]
    for key in sorted(a.keys()|b.keys()):
        old,new=a.get(key),b.get(key)
        if old is None:
            status="added"
        elif new is None:
            status="removed"
        elif old["text_sha256"]!=new["text_sha256"]:
            status="text_changed"
        elif old["class"]!=new["class"]:
            status="classification_changed"
        else:
            continue
        changes.append({"id":key,"status":status,"before":_reference(old),"after":_reference(new),
                        "word_delta":_diff(old,new) if old and new else None,
                        "review_required":any(row is not None and row["class"]!="general" for row in (old,new))})
    return {"schema":"ace.web.tos-delta.v1","plan_sha256":expected,"source_ref":pointer,"site":site,
            "before":plan["before"],"after":plan["after"],"changes":changes,
            "status":"no_annotated_clauses" if not a and not b else "review_required" if changes else "unchanged_in_scope"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for path in ("plan","before","after"):
        parser.add_argument(path,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=compare(decode(read(args.plan)),args.expect_sha256,read(args.before,MAX_HTML),read(args.after,MAX_HTML))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
