"""Susun halaman triase internal dari snapshot dan alur status terdaftar.

Operator dapat menyusun perubahan lokal dan mengekspor usulan dengan
anchor snapshot. Mesin menolak transisi di luar aturan dan menyimpan
catatan sebelum/sesudah untuk pemeriksaan. Halaman tidak mengirim data.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,obj,read,schema,text
from .repo_scaffolder import materialize


JS=r'''"use strict";

function make() { return {snapshot_sha256:APP.anchor, changes: []}; }
function prepare(raw) {
    if(!raw || raw.snapshot_sha256!==APP.anchor || !Array.isArray(raw.changes)||raw.changes.length>500)throw Error("draft_invalid");
    const states=Object.fromEntries(APP.records.map(row=>[row.id,row.state]));
    for(const change of raw.changes){
        if(!change || !Object.hasOwn(states,change.id)||states[change.id]!==change.from ||
           !(APP.graph[change.from]??[]).includes(change.to))throw Error("draft_invalid");
        states[change.id]=change.to;
    }
    return states;
}
function propose(draft,id,to){
    const states=prepare(draft);
    if(!Object.hasOwn(states,id)||!(APP.graph[states[id]]??[]).includes(to)||draft.changes.length>=500)throw Error("transition_invalid");
    return {snapshot_sha256:APP.anchor,changes:[...draft.changes,{id,from:states[id],to}]};
}
function mount(doc,store){
    const key=APP.id+"/"+APP.anchor;
    const status=doc.querySelector("#message");
    let draft;
    try{draft=JSON.parse(store.getItem(key)??"null")??make();prepare(draft);}
    catch(_){status.textContent="Draf lokal tidak sah.";return;}
    const body=doc.querySelector("#records");
    const filter=doc.querySelector("#filter");
    function redraw(){
        const state=prepare(draft);
        body.replaceChildren();
        for(const item of APP.records){
            if(filter.value && filter.value!==state[item.id])continue;
            const row=doc.createElement("tr");
            for(const value of [item.title,state[item.id]]){
                const td=doc.createElement("td");td.textContent=value;row.append(td);
            }
            const select=doc.createElement("select");
            select.setAttribute("aria-label","Usulkan status untuk "+item.title);
            const placeholder=doc.createElement("option");
            placeholder.textContent="Pilih status";placeholder.value="";select.append(placeholder);
            for(const target of APP.graph[state[item.id]]??[]){
                const option=doc.createElement("option");option.textContent=target;option.value=target;select.append(option);
            }
            select.disabled=select.options.length===1;
            select.addEventListener("change",()=>{
                try{
                    if(!select.value)return;
                    const next=propose(draft,item.id,select.value);
                    store.setItem(key,JSON.stringify(next));draft=next;
                    status.textContent="Usulan disimpan lokal.";redraw();
                }catch(_){status.textContent="Usulan gagal disimpan.";}
            });
            const cell=doc.createElement("td");cell.append(select);row.append(cell);body.append(row);
        }
        doc.querySelector("#count").textContent=String(draft.changes.length);
    }
    filter.addEventListener("change",redraw);
    doc.querySelector("#export").addEventListener("click",()=>{
        const file=new Blob([JSON.stringify(draft,null,2)+"\n"],{type:"application/json"});
        const url=URL.createObjectURL(file);
        const link=doc.createElement("a");link.href=url;link.download="draft_transitions.json";link.click();
        setTimeout(()=>URL.revokeObjectURL(url),100);
    });
    redraw();
}
if(typeof module!=="undefined")module.exports={make,prepare,propose};
if(typeof document!=="undefined")mount(document,window.sessionStorage);
'''


def build(plan,snapshot,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-internal-plan.v1",("id","title","source_ref","snapshot_sha256","states","transitions"))
    checked(snapshot,plan["snapshot_sha256"])
    schema(snapshot,"ace.factory-internal-snapshot.v1",("source_ref","records"))
    product=identifier(plan["id"],"ID panel")
    title=text(plan["title"],"Judul panel",100)
    text(snapshot["source_ref"],"Sumber snapshot")
    states=[identifier(name,"Nama status") for name in entries(plan["states"],30,minimum=1)]
    if len(set(states))!=len(states):
        raise ContractError("Status ganda.")
    graph={name:set() for name in states}
    refs=[]
    for edge in entries(plan["transitions"],120):
        obj(edge,("from","to","source_ref"))
        before=identifier(edge["from"],"Status awal")
        after=identifier(edge["to"],"Status tujuan")
        if before not in graph or after not in graph or before==after or after in graph[before]:
            raise ContractError("Transisi ganda, berputar ke diri sendiri atau status tak dikenal.")
        graph[before].add(after)
        refs.append({"from":before,"to":after,"source_ref":text(edge["source_ref"],"Sumber aturan")})
    records={}
    for row in entries(snapshot["records"],300):
        obj(row,("id","title","state","source_ref"))
        key=identifier(row["id"],"ID record")
        state=identifier(row["state"],"Status awal")
        if key in records or state not in graph:
            raise ContractError("Record ganda atau status tak dikenal.")
        records[key]={"id":key,"title":text(row["title"],"Judul record",180),"state":state,
                      "source_ref":text(row["source_ref"],"Sumber record")}
    config={"id":product,"anchor":plan["snapshot_sha256"],"graph":{key:sorted(values) for key,values in sorted(graph.items())},
            "records":[records[key] for key in sorted(records)]}
    options='<option value="">Semua</option>'+''.join(f'<option value="{name}">{name}</option>' for name in states)
    label=escape(title)
    page=f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><title>{label}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><script src="triage.js" defer></script>
<style>body{{margin:2rem auto;max-width:65rem;padding:0 1rem;font:16px system-ui;background:#edf3fa;color:#20344a}}
table{{border-collapse:collapse;width:100%;margin-top:1rem;background:white}}th,td{{padding:.65rem;text-align:left;border-bottom:1px solid #d1dbe7}}
select,button{{font:inherit;padding:.45rem}}button{{margin-left:1rem}}</style></head>
<body><main><h1>{label}</h1><label>Filter status <select id="filter">{options}</select></label>
<button id="export">Ekspor usulan (<span id="count">0</span>)</button><p id="message" role="status"></p>
<table><thead><tr><th scope="col">Judul</th><th scope="col">Status</th><th scope="col">Usulan status</th></tr></thead>
<tbody id="records"></tbody></table></main></body></html>'''.encode()
    program=b"const APP = "+canonical(config)+b";\n"+JS.encode()
    report={"schema":"ace.factory-internal-build.v1","plan_sha256":expected,"snapshot_sha256":plan["snapshot_sha256"],
            "source_ref":text(plan["source_ref"],"Sumber panel"),"data_source_ref":snapshot["source_ref"],
            "records":len(records),"transitions":sorted(refs,key=lambda row:(row["from"],row["to"])),
            "files":{"triage.js":sha256(program).hexdigest(),"index.html":sha256(page).hexdigest()}}
    return {"index.html":page,"triage.js":program,"internal_tool_report.json":canonical(report)+b"\n"},report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("plan","snapshot","output"):
        parser.add_argument(key,type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.plan)),decode(read(args.snapshot)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
