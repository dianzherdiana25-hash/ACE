"""Susun jalur belajar dari prasyarat, skill terdaftar, dan anggaran waktu.

Topologi serta tie-breaking ditetapkan dalam kode. Skill dengan
status ACQUIRED berfungsi sebagai prasyarat yang sudah terpenuhi.
Node hilang atau siklus tidak memicu rencana belajar rekaan.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError,canonical,checked,decode,entries,identifier,integer,obj,read,schema,text
from .skill_registry import _current


def build(plan,expected,registry):
    checked(plan,expected)
    schema(plan,"ace.web.skill-path-plan.v1",("source_ref","registry_sha256","targets","minutes","skills"))
    checked(registry,plan["registry_sha256"])
    _,previous=_current(registry)
    source=text(plan["source_ref"],"Sumber jalur")
    maximum=integer(plan["minutes"],"Anggaran menit",1,100_000)
    targets=[identifier(key,"Target skill") for key in entries(plan["targets"],120,1)]
    if len(set(targets))!=len(targets):
        raise ContractError("Target skill ganda.")
    graph={}
    for row in entries(plan["skills"],800):
        obj(row,("id","prerequisites","minutes","priority","source_ref"))
        key=identifier(row["id"],"Skill terjadwal")
        refs=[identifier(value,"Prasyarat") for value in entries(row["prerequisites"],80)]
        if key in graph or len(set(refs))!=len(refs):
            raise ContractError("Skill atau prasyarat ganda.")
        graph[key]=(set(refs),integer(row["minutes"],"Menit terencana",1,6000),
                    integer(row["priority"],"Prioritas",0,100),text(row["source_ref"],"Sumber prasyarat"))
    acquired={key for key,row in previous.items() if row["status"]=="ACQUIRED"}
    closure=set()
    missing=set()
    pending=list(targets)
    while pending:
        key=pending.pop()
        if key in closure or key in acquired or key in missing:
            continue
        if key not in graph:
            missing.add(key)
        else:
            closure.add(key)
            pending.extend(graph[key][0])
    ready=set(acquired)
    leftover=set(closure)
    steps=[]
    used=0
    budget_limited=set()
    while leftover:
        runnable=sorted((key for key in leftover if graph[key][0]<=ready),
                        key=lambda key:(-graph[key][2],graph[key][1],key))
        if not runnable:
            break
        key=runnable[0]
        requires,cost,priority,pointer=graph[key]
        leftover.remove(key)
        if used+cost>maximum:
            budget_limited.add(key)
            continue
        ready.add(key)
        used+=cost
        steps.append({"skill":key,"requires":sorted(requires),"minutes":cost,
                      "priority":priority,"source_ref":pointer,"cumulative_minutes":used})
    blocked=[{"skill":key,"source_ref":graph[key][3],"undeclared_prerequisites":sorted(graph[key][0]&missing),
              "remaining_prerequisites":sorted(graph[key][0]-ready)} for key in sorted(leftover)]
    status="complete_path" if set(targets)<=ready else "partial_path"
    return {"schema":"ace.web.skill-path-report.v1","plan_sha256":expected,"source_ref":source,
            "registry_sha256":plan["registry_sha256"],"targets":sorted(targets),"status":status,"steps":steps,
            "planned_minutes":used,"budget_minutes":maximum,"missing_skills":sorted(missing),
            "budget_limited":sorted(budget_limited),"blocked":blocked,
            "target_outstanding":sorted(set(targets)-ready)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("registry",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        report=build(decode(read(args.plan)),args.expect_sha256,decode(read(args.registry)))
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(report["status"]!="complete_path")


if __name__=="__main__":
    raise SystemExit(main())
