"""Rakit kemampuan majemuk dengan kompatibilitas dan asal-usul eksplisit.

Setiap langkah mengutip entry registry dan artefak verifier komponen.
Port terhubung secara bertipe dari input atau langkah lain. Keluaran
siap dinilai pada suite khusus komposisi bila seluruh komponen sah.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,digest,entries,identifier,obj,read,schema,text
from .skill_registry import _current


PORT_TYPES={"text","integer","boolean","list","object"}


def _ports(raw):
    if not isinstance(raw,dict) or len(raw)>24:
        raise ContractError("Bentuk port tidak sah.")
    parsed={}
    for key,kind in sorted(raw.items()):
        name=identifier(key,"Port")
        if not isinstance(kind,str) or kind not in PORT_TYPES:
            raise ContractError("Tipe port tidak didukung.")
        parsed[name]=kind
    return parsed


def build(plan,expected,registry):
    checked(plan,expected)
    schema(plan,"ace.web.skill-composition-plan.v1",("id","source_ref","registry_sha256","heldout_sha256",
                                                       "inputs","steps","outputs"))
    checked(registry,plan["registry_sha256"])
    _,known=_current(registry)
    key=identifier(plan["id"],"Komposisi")
    source=text(plan["source_ref"],"Sumber alur")
    heldout=digest(plan["heldout_sha256"])
    inputs=_ports(plan["inputs"])
    builds={}
    for row in entries(plan["steps"],80,1):
        obj(row,("id","skill","package_sha256","takes","produces","bindings","source_ref"))
        name=identifier(row["id"],"Langkah")
        skill=identifier(row["skill"],"Komponen")
        if name=="input" or name in builds or skill==key:
            raise ContractError("Langkah ganda atau komposisi merujuk dirinya.")
        takes,produces=_ports(row["takes"]),_ports(row["produces"])
        if not produces:
            raise ContractError("Langkah harus mendeklarasikan hasil.")
        bindings=obj(row["bindings"],takes)
        builds[name]={"id":name,"skill":skill,"package_sha256":digest(row["package_sha256"]),"input":takes,
                     "output":produces,"bindings":bindings,"source_ref":text(row["source_ref"],"Rujukan langkah")}
    signature={"input":inputs,**{name:row["output"] for name,row in builds.items()}}

    def port(value,required=None):
        if not isinstance(value,str) or value.count(".")!=1:
            raise ContractError("Sambungan perlu komponen.port.")
        owner,field=value.split(".")
        if owner not in signature or field not in signature[owner]:
            raise ContractError("Port sumber tidak terdaftar.")
        kind=signature[owner][field]
        if required is not None and required!=kind:
            raise ContractError("Tipe port tidak kompatibel.")
        return owner,kind

    deps={name:{port(value,item["input"][field])[0] for field,value in item["bindings"].items()}-{"input"}
          for name,item in builds.items()}
    if not isinstance(plan["outputs"],dict) or not 1<=len(plan["outputs"])<=24:
        raise ContractError("Komposisi perlu keluaran bernama.")
    results={}
    for name,path in sorted(plan["outputs"].items()):
        identifier(name,"Port hasil")
        owner,kind=port(path)
        if owner=="input":
            raise ContractError("Komposisi harus memiliki hasil dari langkah.")
        results[name]={"from":path,"type":kind}
    waiting=set(builds)
    ordered=[]
    visited=set()
    while waiting:
        ready=sorted(name for name in waiting if deps[name]<=visited)
        if not ready:
            raise ContractError("Sambungan skill membentuk siklus.")
        name=ready[0]
        waiting.remove(name)
        visited.add(name)
        ordered.append(name)
    pending=[]
    steps=[]
    for name in ordered:
        step=builds[name]
        entry=known.get(step["skill"])
        status="missing_component" if entry is None else "component_not_acquired" if entry["status"]!="ACQUIRED" else (
            "version_mismatch" if step["package_sha256"]!=entry["package_sha256"] else
            "suite_not_independent" if heldout==entry["suite_sha256"] else None)
        if status:
            pending.append({"step":name,"skill":step["skill"],"reason":status,"source_ref":step["source_ref"]})
        steps.append({**step,"requires":sorted(deps[name]),"verification_sha256":entry["verification_sha256"] if not status else None})
    return {"schema":"ace.web.skill-composition-receipt.v1","plan_sha256":expected,"composition":key,"source_ref":source,
            "registry_sha256":plan["registry_sha256"],"heldout_sha256":heldout,"inputs":inputs,"outputs":results,
            "steps":steps,"gaps":pending,"status":"ready_for_heldout" if not pending else "held"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("registry",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=build(decode(read(args.plan)),args.expect_sha256,decode(read(args.registry)))
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]=="held")


if __name__=="__main__":
    raise SystemExit(main())
