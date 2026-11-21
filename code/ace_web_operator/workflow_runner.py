"""Jalankan tahapan web lokal dalam satu sesi browser yang terurut.

Graf prasyarat diturunkan menjadi urutan deterministik. Kegagalan
menahan sisa tahap secara berurutan. Receipt mempertahankan penunjuk
alur, rencana browser dan hasil pada tingkat tahap.
"""
import argparse
from pathlib import Path
import sys

from . import browser_engine
from ._contracts import ContractError,canonical,checked,decode,entries,identifier,identity,obj,read,schema,text


def compile_workflow(plan, expected):
    checked(plan,expected)
    schema(plan,"ace.web.workflow-plan.v1",("source_ref","browser","stages"))
    source=text(plan["source_ref"],"Rujukan workflow")
    settings=obj(plan["browser"],("origin","allow_paths","timeout_ms","request_limit"))
    stage_map={}
    for raw in entries(plan["stages"],16,1):
        obj(raw,("id","requires","steps","source_ref"))
        key=identifier(raw["id"],"ID tahap")
        requirements=[identifier(value,"Prasyarat") for value in entries(raw["requires"],16)]
        if key in stage_map or key in requirements or len(set(requirements))!=len(requirements):
            raise ContractError("Tahap ganda atau prasyarat berulang dan menunjuk diri sendiri.")
        steps=entries(raw["steps"],browser_engine.MAX_OPERATIONS,1)
        stage_map[key]={"requires":sorted(requirements),"steps":steps,
                        "source_ref":text(raw["source_ref"],"Sumber tahap")}
    if any(set(row["requires"])-stage_map.keys() for row in stage_map.values()):
        raise ContractError("Prasyarat tahap tidak ada.")
    waiting=set(stage_map)
    position=[]
    while waiting:
        ready=sorted(key for key in waiting if not set(stage_map[key]["requires"]) & waiting)
        if not ready:
            raise ContractError("Graf workflow mengandung siklus.")
        key=ready[0]
        position.append(key)
        waiting.remove(key)
    flattened=[]
    stages=[]
    for key in position:
        config=stage_map[key]
        identifiers=[]
        for step in config["steps"]:
            if not isinstance(step,dict):
                raise ContractError("Instruksi browser perlu objek.")
            identifiers.append(identifier(step.get("id"),"ID langkah"))
            flattened.append(step)
        stages.append({"id":key,"source_ref":config["source_ref"],"requires":config["requires"],
                       "steps":identifiers})
    browser={"schema":"ace.web.browser-plan.v1","source_ref":source,**settings,"steps":flattened}
    browser_engine.compile_plan(browser,identity(browser))
    return browser,stages


def execute(plan, expected, *, browser=browser_engine.run):
    config,compiled=compile_workflow(plan,expected)
    anchor=identity(config)
    record=browser(config,anchor)
    if record.get("plan_sha256")!=anchor:
        raise ContractError("Receipt browser merujuk rencana berbeda.")
    stages=[]
    read_steps={row["id"]:row for row in record["steps"]}
    boundary=False
    for stage in compiled:
        steps=[read_steps[key] for key in stage["steps"] if key in read_steps]
        if boundary or not steps:
            state="not_started"
            boundary=True
        elif len(steps)==len(stage["steps"]) and all(row["status"]=="ok" for row in steps):
            state="completed"
        else:
            state="failed"
            boundary=True
        stages.append({**stage,"status":state,"observations":steps})
    status="completed" if record["status"]=="completed" and all(row["status"]=="completed" for row in stages) else "held"
    return {"schema":"ace.web.workflow-receipt.v1","workflow_sha256":expected,"browser_sha256":anchor,
            "source_ref":plan["source_ref"],"status":status,"reason":record["reason"],
            "requests":record["requests"],"rejected_requests":record["blocked"],"stages":stages}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        result=execute(decode(read(args.plan)),args.expect_sha256)
        sys.stdout.buffer.write(canonical(result)+b"\n")
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(result["status"]!="completed")


if __name__=="__main__":
    raise SystemExit(main())
