"""Catat sebutan nama terdaftar dari snapshot web yang telah dipilih.

Pencocokan memakai token Unicode dan longest match pada tiap posisi.
Hash sumber mencegah salinan byte menggandakan hitungan. Laporan
mencatat rentang waktu, lokasi, dan sebutan tanpa menyalin halaman.
"""
import argparse
from collections import Counter
from pathlib import Path
import re
import sys
from unicodedata import normalize

from ._artifact import read_relative
from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,relative_path,schema,text
from .page_extractor import MAX_HTML,Snapshot
from .web_scheduler import time_value


WORD=re.compile(r"[^\W_]+",re.UNICODE)
TAGS={"p","h1","h2","h3","li","article","blockquote","figcaption"}


def words(value):
    return WORD.findall(normalize("NFKC",value).casefold())


def _aliases(raw):
    groups={}
    for row in entries(raw,100,1):
        obj(row,("id","aliases","source_ref"))
        name=identifier(row["id"],"Nama terdaftar")
        source=text(row["source_ref"],"Rujukan nama")
        if name in groups:
            raise ContractError("Nama ganda.")
        options={}
        for value in entries(row["aliases"],25,1):
            name_variant=text(value,"Alias pencarian",90)
            tokens=tuple(words(name_variant))
            if not 1<=len(tokens)<=10 or tokens in options:
                raise ContractError("Alias kosong atau ganda setelah normalisasi.")
            options[tokens]=name_variant
        groups[name]=(source,sorted(options.items(),key=lambda pair:(-len(pair[0]),pair[1])))
    return groups


def _blocks(payload):
    for row in Snapshot(payload).elements:
        if row.tag not in TAGS or "hidden" in row.attrs:
            continue
        if any(child.tag in TAGS for child in row.contents if not isinstance(child,str)):
            continue
        pointer=row.parent
        while pointer is not None and "hidden" not in pointer.attrs and pointer.tag not in ("script","style","template"):
            pointer=pointer.parent
        if pointer is None:
            yield row.line,words(row.text())


def _scan(block,aliases):
    references=[]
    position=0
    while position<len(block):
        match=next(((tokens,name) for tokens,name in aliases
                    if block[position:position+len(tokens)]==tokens),None)
        if match is None:
            position+=1
        else:
            tokens,name=match
            references.append((position,name))
            position+=len(tokens)
    return references


def scan(root,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.mention-plan.v1",("source_ref","from","until","tracked","documents"))
    source=text(plan["source_ref"],"Sumber pemantauan")
    start,end=(time_value(plan[name]) for name in ("from","until"))
    if end<=start:
        raise ContractError("Rentang pemantauan terbalik.")
    aliases=_aliases(plan["tracked"])
    pages={}
    for row in entries(plan["documents"],90):
        obj(row,("path","sha256","at","site","source_ref"))
        rel=relative_path(row["path"])
        if rel in pages:
            raise ContractError("Path snapshot ganda.")
        pages[rel]=(time_value(row["at"]),identifier(row["site"],"Situs"),
                    digest(row["sha256"]),text(row["source_ref"],"Rujukan snapshot"))
    counts=Counter()
    prior={}
    emitted=[]
    outside=0
    for path,(when,site,anchor,pointer) in sorted(pages.items(),key=lambda item:(item[1][0],item[0])):
        if not start<=when<end:
            outside+=1
            continue
        data=read_relative(root,path,MAX_HTML,anchor)
        report={"path":path,"sha256":anchor,"site":site,"source_ref":pointer,"mentions":[],"duplicate_of":prior.get(anchor)}
        if anchor in prior:
            emitted.append(report)
            continue
        prior[anchor]=path
        for line,tokens in _blocks(data):
            for name,(ref,patterns) in sorted(aliases.items()):
                for offset,alias in _scan(tuple(tokens),patterns):
                    if len(report["mentions"])>=3000:
                        raise ContractError("Temuan sebutan melampaui anggaran per halaman.")
                    counts[name]+=1
                    report["mentions"].append({"name":name,"alias":alias,"line":line,"token_offset":offset,"tracking_ref":ref})
        emitted.append(report)
    return {"schema":"ace.web.mention-report.v1","plan_sha256":expected,"source_ref":source,
            "documents":emitted,"outside_window":outside,"counts":{key:counts[key] for key in sorted(aliases)}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=scan(args.root,decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
