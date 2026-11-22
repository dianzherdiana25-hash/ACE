"""Isi templat produk berprovenance dengan interpolasi bertipe.

Placeholder memilih encoding eksplisit seperti JSON, Python literal,
HTML atau teks. Path hanya bisa memakai slot identifier. Templat, nilai
awal, dan contoh build dapat direproduksi dari manifest hash eksternal.
"""
import argparse
from hashlib import sha256
from html import escape
import keyword
from pathlib import Path
import re
import sys

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import _relative, materialize


SLOT=re.compile(r"\[\[([a-z][a-z0-9_]{0,63}):([a-z]{2,6})\]\]")
SEGMENT=re.compile(r"[a-zA-Z0-9_-][a-zA-Z0-9_.-]{0,100}")
ENCODING={"id","text","json","python","html"}
MAX_TEMPLATE=250_000
MAX_PRODUCT=2_000_000


def _encoding(name,use,value):
    if use=="id":
        key=identifier(value,name)
        if keyword.iskeyword(key):
            raise ContractError("Identifier bertabrakan dengan keyword Python.")
        return key
    if use=="json":
        return canonical(value).decode()
    if use=="python":
        return repr(value)
    if use=="html":
        return escape(str(value))
    return str(value)


def _expand(template, bindings, *, path=False):
    cursor=0
    parts=[]
    used=set()
    for match in SLOT.finditer(template):
        name,use=match.groups()
        content=template[cursor:match.start()]
        if "[[" in content or "]]" in content or name not in bindings:
            raise ContractError("Placeholder template rusak atau tak dikenal.")
        value,allowed=bindings[name]
        if use not in allowed or path and use!="id":
            raise ContractError("Encoding slot tidak diizinkan.")
        parts.extend((content,_encoding(name,use,value)))
        used.add(name)
        cursor=match.end()
    suffix=template[cursor:]
    if "[[" in suffix or "]]" in suffix:
        raise ContractError("Placeholder belum diisi.")
    parts.append(suffix)
    return "".join(parts),used


def build(root, manifest, settings, expected):
    checked(manifest,expected)
    schema(manifest,"ace.factory-product-template.v1",("id","source_ref","fields","files"))
    name=identifier(manifest["id"],"ID template")
    source=text(manifest["source_ref"],"Sumber template",250)
    definitions={}
    for raw in entries(manifest["fields"],50):
        obj(raw,("id","type","encoding"))
        key=identifier(raw["id"],"Nama field")
        mode=raw["type"]
        allowed=entries(raw["encoding"],len(ENCODING),minimum=1)
        if (key in definitions or mode not in ("text","integer","identifier")
                or any(not isinstance(item,str) or item not in ENCODING for item in allowed)
                or len(set(allowed))!=len(allowed) or ("id" in allowed and mode!="identifier")):
            raise ContractError("Deklarasi slot tidak sah.")
        definitions[key]=(mode,set(allowed))
    schema(settings,"ace.factory-template-bindings.v1",("template_sha256","values","source_ref"))
    if settings["template_sha256"]!=expected:
        raise ContractError("Bindings merujuk template berbeda.")
    values=obj(settings["values"],definitions)
    value_ref=text(settings["source_ref"],"Sumber nilai",250)
    mappings={}
    for key,(kind,allowed) in definitions.items():
        raw=values[key]
        if kind=="identifier":
            raw=identifier(raw,key)
        elif kind=="integer":
            raw=integer(raw,key,-2**31,2**31-1)
        else:
            raw=text(raw,key,500)
        mappings[key]=(raw,allowed)
    files={}
    seen=set()
    used=set()
    report=[]
    size=0
    for row in entries(manifest["files"],100,minimum=1):
        obj(row,("source","sha256","output"))
        rel=text(row["source"],"Path sumber template",240)
        requested=text(row["output"],"Path keluaran template",240)
        if rel in seen:
            raise ContractError("Path sumber template ganda.")
        seen.add(rel)
        anchor=digest(row["sha256"])
        raw=read_relative(root,rel,MAX_TEMPLATE,anchor).decode("utf-8")
        path,path_slots=_expand(requested,mappings,path=True)
        body,text_slots=_expand(raw,mappings)
        if (path in files or path=="product_template_report.json"
                or any(not SEGMENT.fullmatch(part) for part in _relative(path))):
            raise ContractError("Path produk tak sah, ganda, atau dicadangkan.")
        payload=body.encode()
        size+=len(payload)
        if len(payload)>MAX_TEMPLATE or size>MAX_PRODUCT:
            raise ContractError("Produk template terlalu besar.")
        files[path]=payload
        used.update(path_slots|text_slots)
        report.append({"path":path,"sha256":sha256(payload).hexdigest(),"template":rel,"template_sha256":anchor})
    if used!=definitions.keys():
        raise ContractError("Ada binding yang tidak digunakan.")
    for path in files:
        if any("/".join(path.split("/")[:i]) in files for i in range(1,len(path.split("/")))):
            raise ContractError("Path produk menimpa direktori.")
    result={"schema":"ace.factory-template-build.v1","template_id":name,"template_sha256":expected,
            "template_ref":source,"bindings_ref":value_ref,"files":sorted(report,key=lambda row:row["path"])}
    return {**files,"product_template_report.json":canonical(result)+b"\n"},result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("root","manifest","settings","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(args.root,decode(read(args.manifest)),decode(read(args.settings)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
