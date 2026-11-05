"""Public one-label graph-interface test with paired counterfactual truths."""

import argparse
import gzip
import json
import os
import random
import shutil
from contextlib import contextmanager
from itertools import product
from pathlib import Path

from e13.contract import canonical_json, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import sha
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14p_bank import inventory as p_inventory, render_graph
from .e14p_graph import minimum, paths
from .e14p_run import frozen as prior_frozen, prediction_metrics, stage as prior_stage
from .e14q_worker import MODES

BANK = "evidence/e14/e14q_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14Q_LOCK_v1.json"
WORKER = "code/e14/e14q_worker.py"
PROTOCOL = "design/e1.4/E14Q_PROTOCOL_v1.md"
SOURCE = "code/e14/e14q_run.py"
FILES = (BANK,LOCK.replace("E14Q","E14P"),WORKER,PROTOCOL,SOURCE,
         "code/e14/e14q_audit.py","code/e14/test_e14q.py","tools/ace_sprint_runner.py")
SEEDS = (143301,143302,143303,143304)


def inventory():
    used = p_inventory()
    bank,_,_ = prior_frozen()
    for b in bank["blocks"]:
        raw = b["target_demos"]+b["probes"]+[b["calibration"]]+([b["neutral"]] if b["neutral"] is not None else [])
        used["G"].update(sha(canonical_json(x)) for x in raw)
    return used["G"]


def build():
    used = inventory()
    motif,rng,seeds = map(random.Random,SEEDS[:3])
    blocks = []
    prefixes = list(product((1,2),repeat=3))
    suffixes = list(product((1,2),repeat=4))
    for condition in ("shared","mixed"):
        for slot in range(6):
            heads = [motif.choice(prefixes)]*4 if condition=="shared" else motif.sample(prefixes,4)
            words = [(*a,*b) for a,b in zip(heads,motif.sample(suffixes,4),strict=True)]
            probes = [render_graph(rng,used,hit=w,exclude=tuple(x for x in words if x!=w)) for w in words for _ in range(2)]
            rng.shuffle(probes)
            blocks.append({"condition":condition,"slot":slot,"words":words,"probes":probes,"seed":seeds.randrange(2**32)})
    return {"version":1,"seeds":SEEDS,"blocks":blocks}


def manifest():
    return {"version":1,"sha256":{p:sha((REPO/p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock=json.loads((REPO/LOCK).read_bytes())
    verify(lock==manifest(),"E1.4q freeze manifest mismatch")
    raw=gzip.decompress((REPO/BANK).read_bytes())
    return json.loads(raw),sha(raw),lock


def schedule(bank):
    arms={Arm("G","unrelated",b["condition"],str(b["slot"]),0,"query-design"):b for b in bank["blocks"]}
    verify(len(arms)==12,"incorrect block count")
    return arms


@contextmanager
def stage():
    with prior_stage() as root:
        shutil.copyfile(REPO/WORKER,root/"e14/e14q_worker.py")
        yield root


def invoke(root,packet):
    cmd=("import sys; sys.path.insert(0,'/solver'); from e14.e14q_worker import main; "
         f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw,wall=_sandbox_python(["-c",cmd],canonical_json(packet),solver=root)
    row=read_json(raw,24_576)
    require_fields(row,"offers","choice","cpu_us","rss_kib")
    meter={"cpu_us":integer(row.pop("cpu_us"),0,1_000_000),"rss_kib":integer(row.pop("rss_kib"),1,131_072),
           "wall_us":integer(wall,0,3_000_000)}
    return row,meter


def outcomes(block, record):
    words=list(map(tuple,block["words"]))
    choice=record["choice"]
    selected=None if choice is None else record["offers"][integer(choice,0,len(record["offers"])-1)]
    routes=[paths(x) for x in block["probes"]]
    result=[]
    for i,w in enumerate(words):
        label=None if selected is None else minimum(paths(selected["graph"]),w)
        surviving=words if selected is None else [q for q,y in zip(words,selected["predicted"],strict=True) if y==label]
        gold=[minimum(r,w) for r in routes]
        result.append({"target_index":i,"bought":int(selected is not None),"oracle_label":label,
                       "surviving":len(surviving),**prediction_metrics(surviving,routes,gold)})
    return result


def evaluate(root,block):
    modes,meters={},[]
    for mode in MODES:
        record,meter=invoke(root,{"mode":mode,"words":block["words"],"seed":block["seed"]})
        verify(0<len(record["offers"])<=8,"offer cap mismatch")
        modes[mode]={**record,"outcomes":outcomes(block,record)}
        meters.append(meter)
    first=modes["packed"]["outcomes"][0]
    return {"status":"scored","total":8,"correct":first["covered"]-first["errors"],"modes":modes,"resources":meters}


def summary(rows):
    cells={}
    for condition in ("shared","mixed"):
        blocks=[r for r in rows if r["block"]==condition]
        results={}
        for mode in MODES:
            counts=dict.fromkeys(("full","covered","errors","labels","nodes","edges","offers","all_four_blocks"),0)
            for r in blocks:
                arm=r["modes"][mode]
                chosen=arm["offers"][arm["choice"]]["graph"] if arm["choice"] is not None else None
                counts["offers"]+=len(arm["offers"])
                solved=0
                for v in arm["outcomes"]:
                    solved+=v["covered"]==8 and v["errors"]==0
                    counts["covered"]+=v["covered"]
                    counts["errors"]+=v["errors"]
                    counts["labels"]+=v["bought"]
                    if chosen:
                        counts["nodes"]+=chosen["nodes"]
                        counts["edges"]+=len(chosen["edges"])
                counts["full"]+=solved
                counts["all_four_blocks"]+=solved==4
            results[mode]=counts
        cells[condition]=results
    shared=cells["shared"]
    passing=shared["packed"]["all_four_blocks"]>=5 and shared["packed"]["full"]>max(shared[m]["full"] for m in ("chain","random"))
    return {"packed_query":"GO" if passing else "HOLD","blocks":len(rows),"worlds":4*len(rows),"cells":cells}


def run(ledger,output):
    bank,digest,lock=frozen()
    boundary=validate_boundary()
    arms=schedule(bank)
    plan=RunPlan(lock["sha256"][WORKER],digest,lock["sha256"][SOURCE],sha(canonical_json(lock)),SEEDS[3],8,tuple(arms))
    with stage() as root:
        raw,_=_sandbox_python(["-c","import importlib.util,sys; sys.path.insert(0,'/solver'); "
                                "print(all(importlib.util.find_spec(m) is None for m in "
                                "('e14.e14p_graph','e14.e14q_run','e14.e14q_audit')))"],solver=root)
        verify(raw.strip()==b"True","query worker sees evaluator")
        boundary["checks"]["query_stage_without_evaluator"]=True
        rows=run_arms(ledger,plan,lambda a:evaluate(root,arms[a]))
    report={"status":"completed","version":1,"bank_sha256":digest,"plan_sha256":plan.sha256,"boundary":boundary,
            "rows":rows,"summary":summary(rows)}
    temp=output.with_name(output.name+".tmp")
    temp.write_bytes(gzip.compress(canonical_json(report),mtime=0))
    os.replace(temp,output)
    print(json.dumps(report["summary"],sort_keys=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    sub.add_parser("freeze")
    r=sub.add_parser("run")
    r.add_argument("ledger",type=Path)
    r.add_argument("output",type=Path)
    a=p.parse_args()
    if a.mode=="freeze":
        (REPO/BANK).write_bytes(gzip.compress(canonical_json(build()),mtime=0))
        (REPO/LOCK).write_text(json.dumps(manifest(),indent=2,sort_keys=True)+"\n")
    else:
        run(a.ledger,a.output)


if __name__=="__main__":
    main()
