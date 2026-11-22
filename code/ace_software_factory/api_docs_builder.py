"""Terbitkan dokumentasi OpenAPI dan penjelajah baca untuk backend produk.

Kontrak yang sama dengan runtime menentukan metode, path, tipe SQLite
yang diekspos, dan batas pagination. Penjelajah hanya mengeksekusi GET
same-origin yang muncul pada kontrak. Tidak ada dependensi CDN.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


CELL={"text":"string","integer":"integer","boolean":"boolean"}
METHODS={"GET","POST","PATCH","DELETE"}
EXPLORER=r'''"use strict";
const feedback=document.querySelector("#feedback");
for(const form of document.querySelectorAll("form[data-route]")){
    form.addEventListener("submit",async event=>{
        event.preventDefault();
        const path=form.dataset.route;
        if(!/^\/[a-z][a-z0-9_]{0,63}$/.test(path))return;
        const field=form.querySelector("[name=id]");
        const key=field.value.trim();
        if(key && !/^[1-9][0-9]{0,18}$/.test(key)){
            feedback.textContent="ID record tidak sah.";
            return;
        }
        const actual=path+(key?"/"+key:"?limit=20");
        const button=form.querySelector("button");
        button.disabled=true;
        feedback.textContent="Menunggu.";
        try{
            const response=await fetch(actual,{method:"GET",credentials:"same-origin",redirect:"error"});
            const body=await response.text();
            feedback.textContent=response.status+"\n"+body.slice(0,8000);
        }catch(_error){
            feedback.textContent="Panggilan lokal gagal.";
        }finally{
            button.disabled=false;
        }
    });
}
'''


def _fields(raw, columns, title):
    names=[identifier(key,title) for key in entries(raw,128)]
    if set(names)-columns.keys() or len(names)!=len(set(names)):
        raise ContractError("Kolom resource tidak dikenal atau berulang.")
    return names


def _properties(names, columns):
    return {name:{"type":[CELL[columns[name]["kind"]],"null"] if columns[name]["nullable"]
                  else CELL[columns[name]["kind"]]} for name in names}


def _operation(resource,method,collection,record):
    operation={"operationId":f"{method.lower()}_{resource['name']}_{'list' if collection else 'record'}",
               "tags":[resource["name"]],"x-source-ref":resource["source_ref"],"responses":{}}
    if not collection:
        operation["parameters"]=[{"name":"id","in":"path","required":True,"schema":{"type":"integer","minimum":1}}]
    status=201 if method=="POST" else 200
    reply=record
    if method=="GET" and collection:
        operation["parameters"]=[
            {"name":name,"in":"query","schema":{"type":"integer","minimum":minimum,"maximum":maximum,"default":default}}
            for name,minimum,maximum,default in (("limit",1,200,50),("offset",0,1_000_000,0))]
        reply={"type":"object","required":["items","limit","offset"],"properties":{
            "items":{"type":"array","items":record},"limit":{"type":"integer"},"offset":{"type":"integer"}}}
    elif method=="DELETE":
        reply={"type":"object","required":["deleted"],"properties":{"deleted":{"type":"integer"}}}
    if method in ("POST","PATCH"):
        writable={"type":"object","properties":_properties(resource["write"],resource["columns"]),
                  "additionalProperties":False}
        if method=="PATCH":
            writable["minProperties"]=1
        operation["requestBody"]={"required":True,"content":{"application/json":{"schema":writable}}}
    operation["responses"][str(status)]={"description":"Respons JSON produk","content":{"application/json":{"schema":reply}}}
    for code,message in (("400","Masukan tidak sah"),("404","Rute atau record tidak ditemukan"),
                         ("409","Constraint konflik"),("413","Body melampaui batas"),("503","Database tidak tersedia")):
        operation["responses"][code]={"description":message}
    return operation


def build(api,expected,title,version):
    checked(api,expected)
    schema(api,"ace.factory-generated-api.v1",("plan_sha256","model_sha256","plan_ref","resources"))
    digest(api["plan_sha256"])
    digest(api["model_sha256"])
    text(api["plan_ref"],"Sumber API")
    title=text(title,"Judul dokumentasi",120)
    version=text(version,"Versi API",40)
    raw=api["resources"]
    if not isinstance(raw,dict) or not 1<=len(raw)<=128:
        raise ContractError("Jumlah resource di luar batas.")
    paths,sections={},[]
    for key,details in sorted(raw.items()):
        key=identifier(key,"Nama resource")
        obj(details,("table","primary","read","write","methods","source_ref","columns"))
        source=text(details["source_ref"],"Sumber resource")
        columns=details["columns"]
        if not isinstance(columns,dict) or not 1<=len(columns)<=128:
            raise ContractError("Kolom API tidak sah.")
        for column,definition in columns.items():
            obj(definition,("name","kind","nullable"))
            if (identifier(column,"Kolom API")!=definition["name"] or not isinstance(definition["kind"],str)
                    or definition["kind"] not in CELL or type(definition["nullable"]) is not bool):
                raise ContractError("Deklarasi kolom API tidak sah.")
        read_keys=_fields(details["read"],columns,"Kolom respons")
        write_keys=_fields(details["write"],columns,"Kolom masukan")
        methods=[text(value,"Metode",8) for value in entries(details["methods"],4,minimum=1)]
        if (details["primary"] not in read_keys or details["primary"] in write_keys
                or set(methods)-METHODS or len(set(methods))!=len(methods)):
            raise ContractError("Key atau metode API tidak konsisten.")
        route="/"+key
        resource={"name":key,"write":write_keys,"columns":columns,"source_ref":source}
        record={"type":"object","additionalProperties":False,"properties":_properties(read_keys,columns),
                "required":read_keys}
        for method in sorted(methods):
            categories=[True,False] if method=="GET" else [method=="POST"]
            for collection in categories:
                lane=route if collection else route+"/{id}"
                paths.setdefault(lane,{})[method.lower()]=_operation(resource,method,collection,record)
        form=(f'<form data-route="{route}"><label>ID opsional <input name="id" inputmode="numeric" maxlength="19"></label>'
              f'<button type="submit">GET {route}</button></form>') if "GET" in methods else ""
        sections.append(f"<section><h2><code>{route}</code></h2><p>{', '.join(sorted(methods))}</p>{form}</section>")
    document={"openapi":"3.1.0","info":{"title":title,"version":version},"servers":[{"url":"/"}],
              "paths":paths,"x-api-sha256":expected}
    safe=escape(title)
    html=f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><title>{safe}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><script src="explorer.js" defer></script>
<style>body{{max-width:62rem;margin:2rem auto;padding:0 1rem;font:16px system-ui;color:#183041}}
section{{border-bottom:1px solid #b2c7d8;padding:.8em 0}}form{{display:flex;gap:1em;flex-wrap:wrap}}
button,input{{font:inherit;padding:.45em}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef4f9;padding:.8rem}}</style>
</head><body><main><h1>{safe}</h1><p><a href="openapi.json">Unduh kontrak OpenAPI</a></p>
{''.join(sections)}<h2>Respons lokal</h2><pre id="feedback" aria-live="polite"></pre></main></body></html>'''.encode()
    files={"openapi.json":canonical(document)+b"\n","index.html":html,"explorer.js":EXPLORER.encode()}
    report={"schema":"ace.factory-api-docs.v1","api_sha256":expected,"paths":len(paths),
            "operations":sum(len(items) for items in paths.values()),"artifacts":[
                {"path":path,"sha256":sha256(data).hexdigest()} for path,data in sorted(files.items())]}
    return {**files,"api_docs_manifest.json":canonical(report)+b"\n"},report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    parser.add_argument("--title",required=True)
    parser.add_argument("--version",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.contract)),args.expect_sha256,args.title,args.version)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
