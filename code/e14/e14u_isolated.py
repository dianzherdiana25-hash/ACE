"""E1.4u worker-only actual-namespace development run (NOT Bwrap certification).

A trusted evaluator constructs public worlds and keeps truth/probes exclusively
outside the worker. Each decision is a fresh chrooted unshare worker process.
A different author and approved sandbox are required for scientific acceptance.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from time import perf_counter_ns

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_routes, purchase
from .e14_shared_budget import BudgetContractError
from .e14t_sandbox import isolation_canary, sandbox_call
from .e14u_dev import MODES, SEED, TRIPLE_WORDS, make_world
from .e14u_primitive import PAIR_SPACE, PAIR_WORDS, diagnose, fit, guarded_predict, program, select_query

WORKER = Path(__file__).with_name("e14u_worker.py")


def decision(world, mode, database):
    journal = DurableGraphBudget(database, world["id"]+":"+mode)
    known = list(world["demonstrations"])
    triggers=[]; measures=[]
    for turn in range(5):
        snap = journal.snapshot()
        packet = {"mode":mode,"seed":SEED+turn+len(known)+len(world["id"]),
                  "demos":known,"purchased":[r["query"] for r in snap["receipts"]]}
        # Hidden truth, oracle, and probes are NOT in packet or worker mount.
        start = perf_counter_ns()
        reply = sandbox_call(packet, worker=WORKER)
        measures.append({"wall_us":(perf_counter_ns()-start)//1000,
                         "worker_cpu_us":reply.pop("cpu_us"),
                         "worker_rss_kib":reply.pop("rss_kib")})
        if set(reply) != {"trigger","survivors","action"} or type(reply["trigger"]) is not bool:
            raise BudgetContractError("invalid worker result shape")
        reference=diagnose(known)
        expand=reference["trigger"] and mode!="base-only"
        candidates=(reference["extended"] if expand else reference["base"])["candidates"]
        if reply["trigger"]!=reference["trigger"] or reply["survivors"]!=len(candidates):
            raise BudgetContractError("candidate worker disagrees with evaluator")
        action=reply["action"]
        if type(action) is not dict or action.get("action") not in ("query","accept","abstain"):
            raise BudgetContractError("invalid worker action")
        triggers.append(action["action"])
        if action["action"]=="query":
            if set(action)!={"action","graph"} or len(candidates)<=1 or turn>=4:
                raise BudgetContractError("invalid purchased query")
            expected=select_query(candidates,[r["query"] for r in snap["receipts"]],
                mode="fixed" if mode=="base-only" else mode,seed=packet["seed"])
            if action["graph"]!=expected:
                raise BudgetContractError("worker proposed off-policy graph")
            graph_routes(action["graph"])
            rid,y=purchase(journal,"diagnosis" if turn==0 else "qualification",
                           action["graph"],world["oracle"])
            known.append({"input":action["graph"],"output":y})
            if turn==0:
                journal.reuse(rid,"repair")
            continue
        if action["action"]=="accept":
            if set(action)!={"action","candidate"} or len(candidates)!=1:
                raise BudgetContractError("unsafe worker acceptance")
            value=action["candidate"]
            if type(value) is not dict or set(value)!={"kind","words"}:
                raise BudgetContractError("invalid worker candidate encoding")
            selected=program(value["kind"],value["words"])
            if selected!=candidates[0]:
                raise BudgetContractError("worker claimed unsupported program")
            break
        if set(action)!={"action"} or len(candidates)==1:
            raise BudgetContractError("worker abstained despite unique candidate")
        selected=None
        break
    else:
        raise BudgetContractError("worker action limit exhausted")
    snapshot=journal.snapshot()
    journal.assert_complete()
    replay=audit_journal(snapshot,world["oracle"])
    cover=[guarded_predict(candidates,g) for g in world["probes"]]
    gold=[world["oracle"](g) for g in world["probes"]]
    errors=sum(int(r["prediction"]!=y) for r,y in zip(cover,gold) if r["covered"])
    return {"world":world["id"],"kind":world["kind"],"arm":mode,
            "purchased":snapshot["purchased"],"audit_calls":replay["auditor_oracle_calls"],
            "accepted":int(selected is not None),
            "exact":int(selected is not None and selected==world["truth"]),
            "wrong_accepted":int(selected is not None and selected!=world["truth"]),
            "covered":sum(int(x["covered"]) for x in cover),"probe_errors":errors,
            "worker_calls":len(measures),"worker_wall_us":sum(x["wall_us"] for x in measures),
            "worker_cpu_us":sum(x["worker_cpu_us"] for x in measures),
            "max_rss_kib":max(x["worker_rss_kib"] for x in measures),
            "query_cost":snapshot["query_cost_totals"],"trace":triggers,
            "source_demonstration_labels":len(world["demonstrations"]),
            "heldout_probe_labels":len(world["probes"])}


def run(*, subset=None):
    canary=isolation_canary()
    worlds=([make_world("pair",i) for i in range(len(PAIR_SPACE))]
            +[make_world("single",i) for i in range(len(PAIR_WORDS))]
            +[make_world("triple",i) for i in range(len(TRIPLE_WORDS))])
    if subset is not None:
        worlds=worlds[:subset]
    rows=[]
    with tempfile.TemporaryDirectory(prefix="ace-e14u-isolated-") as home:
        for world in worlds:
            for mode in MODES:
                rows.append(decision(world,mode,Path(home)/"worker-ledger.sqlite"))
    summary={}
    for kind in ("pair","single","triple"):
        summary[kind]={}
        for mode in MODES:
            chosen=[r for r in rows if r["kind"]==kind and r["arm"]==mode]
            summary[kind][mode]={k:sum(row[k] for row in chosen) for k in
               ("purchased","audit_calls","accepted","exact","wrong_accepted",
                "covered","probe_errors","worker_calls","worker_wall_us","worker_cpu_us")}
            summary[kind][mode]["worlds"]=len(chosen)
    deterministic=[{k:v for k,v in r.items() if k not in
                   ("worker_wall_us","worker_cpu_us","max_rss_kib")} for r in rows]
    digest=hashlib.sha256(json.dumps(deterministic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {"status":"PUBLIC_DEV_ACTUAL_NAMESPACE_WORKER_NOT_SCIENTIFIC_ACCEPTANCE",
            "worlds":len(worlds),"arms":len(rows),"preflight":canary,
            "worker_source_sha256":hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "deterministic_sha256":digest,"summary":summary,"rows":rows,
            "warning":"chroot/unshare canary is not independently certified Bubblewrap equivalence"}


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--subset",type=int)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    r=run(subset=args.subset)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:r[k] for k in ("status","worlds","arms","deterministic_sha256","summary")},sort_keys=True))

if __name__=="__main__":main()
