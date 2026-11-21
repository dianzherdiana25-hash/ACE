"""Periksa dasar aksesibilitas halaman produk secara statis berbasis HTML.

Audit mencatat posisi dan hash asal. Ia memeriksa struktur, label,
deskripsi gambar, urutan heading, dan beberapa pola keyboard. Pemeriksaan
visual, pembaca layar dan DOM setelah JavaScript memerlukan bukti terpisah.
"""
import argparse
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

from ._artifact_io import read_relative
from ._contracts import ContractError,canonical,checked,decode,digest,entries,obj,read,schema,text


VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
HEADING={f"h{count}":count for count in range(1,7)}
CONTROL={"input","select","textarea"}
LANG=re.compile(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*")


class Node:
    def __init__(self,tag,attributes,parent,line,column):
        self.tag=tag
        self.attrs=dict(attributes)
        self.parent=parent
        self.line=line
        self.column=column+1
        self.children=[]

    def content(self):
        pieces=[]
        pending=list(reversed(self.children))
        while pending:
            child=pending.pop()
            if isinstance(child,str):
                pieces.append(child)
            elif child.tag not in ("script","style") and "hidden" not in child.attrs:
                if child.tag=="img" and child.attrs.get("alt"):
                    pieces.append(child.attrs["alt"])
                pending.extend(reversed(child.children))
        return " ".join(" ".join(pieces).split())


class Document(HTMLParser):
    def __init__(self,payload):
        super().__init__(convert_charrefs=True)
        self.records=[]
        self.open=[]
        self.feed(payload.decode("utf-8"))
        self.close()

    def handle_starttag(self,tag,attrs):
        parent=self.open[-1] if self.open else None
        row=Node(tag,attrs,parent,*self.getpos())
        self.records.append(row)
        if len(self.records)>8000 or len(self.open)>240:
            raise ContractError("Halaman melampaui batas analyzer.")
        if parent:
            parent.children.append(row)
        if tag not in VOID:
            self.open.append(row)

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self,tag):
        for index in range(len(self.open)-1,-1,-1):
            if self.open[index].tag==tag:
                del self.open[index:]
                break

    def handle_data(self,data):
        if self.open:
            self.open[-1].children.append(data)


def _attr(row,key):
    return (row.attrs.get(key) or "").strip()


def _label(row,ids,labels):
    explicit=_attr(row,"aria-label")
    if explicit:
        return explicit
    linked=_attr(row,"aria-labelledby").split()
    if linked and all(key in ids and len(ids[key])==1 for key in linked):
        return " ".join(ids[key][0].content() for key in linked).strip()
    local=_attr(row,"id")
    if local in labels and any(label.content() for label in labels[local]):
        return " ".join(label.content() for label in labels[local]).strip()
    parent=row.parent
    while parent:
        if parent.tag=="label" and not _attr(parent,"for") and parent.content():
            return parent.content()
        parent=parent.parent
    return ""


def _checks(nodes):
    ids=defaultdict(list)
    labels=defaultdict(list)
    findings=[]
    def add(row,code):
        findings.append({"rule":code,"tag":row.tag if row else None,"line":row.line if row else 1,
                         "column":row.column if row else 1})
    for node in nodes:
        key=_attr(node,"id")
        if key:
            ids[key].append(node)
        if node.tag=="label":
            target=_attr(node,"for")
            if target:
                labels[target].append(node)
    for occurrences in ids.values():
        for node in occurrences[1:]:
            add(node,"duplicate_id")
    for target,items in labels.items():
        if target not in ids or len(ids[target])!=1 or ids[target][0].tag not in CONTROL|{"button","meter","output","progress"}:
            for item in items:
                add(item,"label_target_missing")
    root=next((node for node in nodes if node.tag=="html"),None)
    if not root or not LANG.fullmatch(_attr(root,"lang")):
        add(root,"document_language_missing")
    if not any(node.tag=="title" and node.content() for node in nodes):
        add(root,"title_missing")
    mains=[node for node in nodes if node.tag=="main" or _attr(node,"role")=="main"]
    if len(mains)!=1:
        add(mains[-1] if mains else root,"main_landmark_count")
    previous=0
    for node in nodes:
        tag=node.tag
        if tag in HEADING:
            depth=HEADING[tag]
            if depth>previous+1:
                add(node,"heading_jump")
            if not node.content() and not _label(node,ids,labels):
                add(node,"empty_heading")
            previous=depth
        if tag=="img" and "alt" not in node.attrs:
            add(node,"image_alt_missing")
        if tag in CONTROL and _attr(node,"type").lower() not in ("hidden","submit","reset","button","image") and (
                not _label(node,ids,labels)):
            add(node,"control_label_missing")
        if (tag=="button" or tag=="a" and "href" in node.attrs) and not node.content() and not _label(node,ids,labels):
            add(node,"interactive_name_missing")
        tab=_attr(node,"tabindex")
        if tab.isascii() and tab.lstrip("+").isdigit() and len(tab)<8 and int(tab)>0:
            add(node,"positive_tabindex")
        if "onclick" in node.attrs and tag not in (CONTROL|{"button","a","summary"}):
            add(node,"nonsemantic_click_target")
        references=_attr(node,"aria-labelledby").split()
        if references and any(len(ids.get(ref,()))!=1 for ref in references):
            add(node,"aria_reference_missing")
    return sorted(findings,key=lambda row:(row["line"],row["column"],row["rule"]))


def inspect(root,manifest,expected):
    checked(manifest,expected)
    schema(manifest,"ace.factory-a11y-plan.v1",("source_ref","pages"))
    pointer=text(manifest["source_ref"],"Asal audit")
    pages={}
    for row in entries(manifest["pages"],50,minimum=1):
        obj(row,("path","sha256"))
        path=text(row["path"],"Path HTML",250)
        if not path.endswith(".html") or path in pages:
            raise ContractError("Path halaman ganda atau bukan HTML.")
        anchor=digest(row["sha256"])
        payload=read_relative(root,path,400_000,anchor)
        pages[path]={"path":path,"sha256":anchor,"findings":_checks(Document(payload).records)}
    result=[pages[name] for name in sorted(pages)]
    hits=sum(len(page["findings"]) for page in result)
    return {"schema":"ace.factory-a11y-report.v1","manifest_sha256":expected,"source_ref":pointer,
            "scope":"static_html","pages":result,"findings":hits,"status":"review_required" if hits else "no_rule_matches"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("manifest",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=inspect(args.root,decode(read(args.manifest)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="no_rule_matches")


if __name__=="__main__":
    raise SystemExit(main())
