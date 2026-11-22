"""Ekstrak baris HTML yang mempunyai kontrak field dan bukti byte.

Selector memakai tag/kelas dan atribut data-field. Nilai keliru
atau duplikat bertahan sebagai temuan dengan posisi. Ekstraktor tidak
menebak data dari elemen yang tidak terdaftar.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text,web_path


MAX_HTML=800_000
VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
ROW_TAGS={"article","div","li","tr"}
KINDS={"text","integer","boolean","path"}
ATTRS={"text","href","src","value","datetime","data-value"}
INT=re.compile(r"(?:0|-?[1-9][0-9]{0,17})")


class Element:
    def __init__(self,tag,attrs,line,parent):
        self.tag=tag
        self.attrs=dict(attrs)
        self.line=line
        self.parent=parent
        self.contents=[]

    def text(self):
        values=[]
        remaining=list(reversed(self.contents))
        while remaining:
            piece=remaining.pop()
            if isinstance(piece,str):
                values.append(piece)
            elif piece.tag not in ("script","style","template") and "hidden" not in piece.attrs:
                remaining.extend(reversed(piece.contents))
        return " ".join(" ".join(values).split())


class Snapshot(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True)
        self.elements=[]
        self.parents=[]
        self.feed(html.decode("utf-8"))
        self.close()

    def handle_starttag(self,tag,attrs):
        current=self.parents[-1] if self.parents else None
        node=Element(tag,attrs,self.getpos()[0],current)
        self.elements.append(node)
        if len(self.elements)>25_000 or len(self.parents)>180:
            raise ContractError("Snapshot HTML terlalu kompleks.")
        if current is not None:
            current.contents.append(node)
        if tag not in VOID:
            self.parents.append(node)

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self,tag):
        for index in range(len(self.parents)-1,-1,-1):
            if self.parents[index].tag==tag:
                self.parents=self.parents[:index]
                break

    def handle_data(self,data):
        if self.parents:
            self.parents[-1].contents.append(data)


def _typed(raw,kind):
    if raw is None:
        raise ContractError("attribute_missing")
    value=text(raw.strip(),"Isi field",1500)
    if kind=="text":
        return value
    if kind=="path":
        return web_path(value)
    if kind=="integer" and INT.fullmatch(value):
        return int(value)
    if kind=="boolean" and value in ("true","false"):
        return value=="true"
    raise ContractError("invalid_value_type")


def _descendants(root):
    pending=list(reversed(root.contents))
    while pending:
        child=pending.pop()
        if isinstance(child,Element) and child.tag not in ("script","style","template") and "hidden" not in child.attrs:
            yield child
            pending.extend(reversed(child.contents))


def extract(html,plan,expected):
    checked(plan,expected)
    schema(plan,"ace.web.extract-plan.v1",("source_ref","html_ref","html_sha256","row_tag","row_class","primary","fields"))
    source=text(plan["source_ref"],"Rujukan kontrak")
    page_ref=text(plan["html_ref"],"Rujukan HTML")
    anchor=digest(plan["html_sha256"])
    if not isinstance(html,bytes) or len(html)>MAX_HTML or sha256(html).hexdigest()!=anchor:
        raise ContractError("HTML terlalu besar atau tidak cocok dengan anchor.")
    tag=plan["row_tag"]
    match_class=identifier(plan["row_class"],"Kelas record")
    if not isinstance(tag,str) or tag not in ROW_TAGS:
        raise ContractError("Tag record belum didukung.")
    fields={}
    for row in entries(plan["fields"],50,1):
        obj(row,("name","marker","type","from","required","source_ref"))
        key=identifier(row["name"],"Field")
        selector=identifier(row["marker"],"Marker field")
        kind=row["type"]
        slot=row["from"]
        if (key in fields or not isinstance(kind,str) or kind not in KINDS or not isinstance(slot,str) or slot not in ATTRS
                or type(row["required"]) is not bool):
            raise ContractError("Field ganda atau tipe tidak dikenal.")
        fields[key]=(selector,kind,slot,row["required"],text(row["source_ref"],"Rujukan field"))
    primary=identifier(plan["primary"],"Primary")
    if primary not in fields or not fields[primary][3]:
        raise ContractError("Primary tidak ditemukan atau opsional.")
    dom=Snapshot(html)
    matches=[node for node in dom.elements if node.tag==tag and match_class in (node.attrs.get("class") or "").split()]
    if len(matches)>1500:
        raise ContractError("Jumlah record melampaui batas.")
    segments=set(matches)
    rows=[]
    keys={}
    for node in matches:
        markers=defaultdict(list)
        for child in _descendants(node):
            if child in segments:
                raise ContractError("Record ekstraksi bertumpuk.")
            if child.attrs.get("data-field"):
                markers[child.attrs["data-field"]].append(child)
        values={}
        issues=[]
        for key,(selector,kind,slot,required,pointer) in sorted(fields.items()):
            observed=markers[selector]
            if len(observed)>1 or not observed and required:
                code="field_ambiguous" if len(observed)>1 else "field_missing"
                issues.append({"field":key,"code":code,"source_ref":pointer,"line":node.line})
                values[key]=None
            elif not observed:
                values[key]=None
            else:
                element=observed[0]
                try:
                    data=element.text() if slot=="text" else element.attrs.get(slot)
                    values[key]=_typed(data,kind)
                except ValueError:
                    issues.append({"field":key,"code":"invalid_field","source_ref":pointer,"line":element.line})
                    values[key]=None
        key=values[primary]
        if key is not None:
            if key in keys:
                issues.append({"field":primary,"code":"duplicate_primary","line":node.line,"first_line":keys[key]})
            else:
                keys[key]=node.line
        rows.append({"line":node.line,"valid":not issues,"values":values,"findings":issues})
    good=sum(row["valid"] for row in rows)
    return {"schema":"ace.web.extraction-receipt.v1","plan_sha256":expected,"page_sha256":anchor,
            "source_ref":source,"html_ref":page_ref,"records":len(rows),"valid":good,"rows":rows,
            "status":"empty" if not rows else "complete" if good==len(rows) else "partial"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page",type=Path)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        output=extract(read(args.page,MAX_HTML),decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(output)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(output["status"]=="partial")


if __name__=="__main__":
    raise SystemExit(main())
