"""Bangun mesin perilaku dari deskripsi state dan respons milik produk.

Deskripsi hanya menentukan input, state dan output data. Builder memeriksa
konflik transisi dan keterjangkauan state, lalu menyimpan implementasi
mandiri. Tidak ada UI, aset, atau kode asli yang disalin.
"""
import argparse
from collections import deque
from hashlib import sha256
import keyword
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, obj, read, schema, text
from .repo_scaffolder import materialize


RUNTIME=r'''"""Runtime transisi produk dari kontrak perilaku eksplisit."""
import argparse
from hashlib import sha256
import json
import sys


def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate")
        result[key]=value
    return result


def operate(raw):
    if not isinstance(raw,list) or len(raw)>500:
        raise ValueError("input_shape")
    state=SHAPE["initial"]
    report=[]
    for index,item in enumerate(raw,1):
        if not isinstance(item,dict) or set(item)!={"event","input"} or not isinstance(item["event"],str):
            raise ValueError("input_shape")
        event=item["event"]
        if len(event)>64:
            raise ValueError("event_size")
        fingerprint=sha256(encode(item["input"])).hexdigest()
        transition=SHAPE["transitions"].get(state,{}).get(event,{}).get(fingerprint)
        if transition is None:
            report.append({"index":index,"status":"unsupported","state":state,"response":None})
            continue
        state=transition["to"]
        report.append({"index":index,"status":"matched","state":state,"response":transition["response"],
                       "source_ref":transition["source_ref"]})
    return {"steps":report,"state":state,"unmatched":sum(row["status"]!="matched" for row in report)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        encoded=sys.stdin.buffer.read(130_001)
        if len(encoded)>130_000:
            raise ValueError("input_limit")
        result=operate(json.loads(encoded,object_pairs_hook=unique))
        print(encode(result).decode())
        return int(result["unmatched"]>0)
    except (ValueError,UnicodeError,RecursionError):
        return 2


if __name__=="__main__":
    raise SystemExit(main())
'''


def build(plan,expected):
    checked(plan,expected)
    schema(plan,"ace.factory-behavior-plan.v1",("id","initial","states","transitions","source_ref"))
    product=identifier(plan["id"],"ID produk")
    if keyword.iskeyword(product) or product in sys.stdlib_module_names:
        raise ContractError("Nama modul bentrok dengan Python.")
    source=text(plan["source_ref"],"Sumber perilaku")
    states=[identifier(value,"State") for value in entries(plan["states"],48,minimum=1)]
    initial=identifier(plan["initial"],"State mula")
    if len(set(states))!=len(states) or initial not in states:
        raise ContractError("State awal tidak dikenal atau state ganda.")
    table={name:{} for name in states}
    graph={name:set() for name in states}
    for row in entries(plan["transitions"],240,minimum=1):
        obj(row,("from","event","input","to","response","source_ref"))
        before=identifier(row["from"],"State awal")
        next_state=identifier(row["to"],"State tujuan")
        event=identifier(row["event"],"Nama event")
        if before not in table or next_state not in table or len(canonical(row))>3800:
            raise ContractError("Transisi memakai state tak dikenal atau payload terlalu besar.")
        route=table[before].setdefault(event,{})
        value=identity(row["input"])
        if value in route:
            raise ContractError("Dua transisi pada input dan state yang sama.")
        route[value]={"to":next_state,"response":row["response"],"source_ref":text(row["source_ref"],"Sumber contoh")}
        graph[before].add(next_state)
    reached=set()
    pending=deque([initial])
    while pending:
        state=pending.popleft()
        if state not in reached:
            reached.add(state)
            pending.extend(graph[state]-reached)
    if reached!=set(states):
        raise ContractError("Ada state yang tidak bisa dicapai.")
    settings={"initial":initial,"transitions":table}
    program=RUNTIME.replace("import sys\n",f"import sys\n\nSHAPE={settings!r}\n",1).encode()
    path=f"{product}.py"
    report={"schema":"ace.factory-behavior-build.v1","plan_sha256":expected,"product_id":product,"source_ref":source,
            "states":sorted(states),"transitions":sum(len(value) for rules in table.values() for value in rules.values()),
            "runtime":{"path":path,"sha256":sha256(program).hexdigest()}}
    return {path:program,"behavior_manifest.json":canonical(report)+b"\n"},report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.plan)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
