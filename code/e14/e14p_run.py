"""Run cold successor inheritance on a different weighted graph task."""

import argparse
import gzip
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import oracle, sha
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14n_run import deterministic, invoke as invoke_source, stage as source_stage, validate_classes
from .e14o_run import frozen as prior_frozen
from .e14p_bank import SEEDS, build
from .e14p_graph import minimum, paths

BANK = "evidence/e14/e14p_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14P_LOCK_v1.json"
WORKER = "code/e14/e14p_worker.py"
SOURCE = "code/e14/e14p_bank.py"
FILES = (BANK, WORKER, SOURCE, "code/e14/e14p_graph.py", "code/e14/e14p_run.py", "code/e14/e14p_audit.py",
         "code/e14/test_e14p.py", "design/e1.4/E14P_PROTOCOL_v1.md", "design/e1.4/E14O_LOCK_v1.json",
         "tools/ace_sprint_runner.py")
MODES = ("cold", "inherited", "sham")


def manifest():
    return {"version":1,"sha256":{p:sha((REPO/p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO/LOCK).read_bytes())
    verify(lock == manifest(),"E1.4p freeze manifest mismatch")
    raw = gzip.decompress((REPO/BANK).read_bytes())
    return json.loads(raw),sha(raw),lock


def schedule(bank):
    arms = {Arm("G","unrelated",f'lineage:{b["slot"]}',str(len(b["source_word"])),0,"inheritance"):b
            for b in bank["blocks"]}
    verify(len(arms)==12,"lineage count mismatch")
    return arms


@contextmanager
def stage():
    with source_stage() as root:
        shutil.copyfile(REPO/WORKER,root/"e14/e14p_worker.py")
        yield root


def target_call(root, packet):
    cmd = ("import sys; sys.path.insert(0,'/solver'); from e14.e14p_worker import main; "
           f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw,wall = _sandbox_python(["-c",cmd],canonical_json(packet),solver=root)
    record = read_json(raw,24_576)
    require_fields(record,"selected","artifact_used","candidate_fits","cpu_us","rss_kib")
    meter = {"cpu_us":integer(record.pop("cpu_us"),0,1_000_000),
             "rss_kib":integer(record.pop("rss_kib"),1,131_072),"wall_us":integer(wall,0,3_000_000)}
    return record,meter


def source_packet(block):
    target = tuple(block["source_word"])
    return {"family":"S","demos":[{"input":x,"output":oracle("S",target,x)}
                                  for x in block["source_demos"]+block["source_observations"]]}


def encode(learned, packet):
    parent = sha(canonical_json({"source":packet,"learned":learned}))
    mapped = [1 if e==0 else 2 for e in learned]
    return {"kind":"edge-relative-word-v1","word":mapped,"source_sha256":parent}


def sham_for(artifact):
    word = artifact["word"].copy()
    word[0] = 3-word[0]
    return {**artifact,"word":word}


def regimes(block):
    word = tuple(1 if x==0 else 2 for x in block["source_word"])
    shift = tuple(3-x for x in word)
    values = {"aligned":(word,block["calibration"]),"shift_visible":(shift,block["calibration"])}
    if block["neutral"] is not None:
        values["shift_hidden"] = shift,block["neutral"]
    return values


def prediction_metrics(selected, routes, gold):
    covered = errors = fp = 0
    for r,y in zip(routes,gold,strict=True):
        options = {minimum(r,tuple(w)) for w in selected}
        if len(options)==1:
            pred = next(iter(options))
            covered += 1
            errors += pred != y
            fp += pred is not None and y is None
    return {"covered":covered,"errors":errors,"false_positive":fp}


def evaluate(root, block):
    packet = source_packet(block)
    source,source_meter = invoke_source(root,packet)
    verified = source["expansions"].get("directed",{}).get("classes",[[],[],[]])
    validate_classes("S",verified,(7,8,9))
    learned = [w for group in verified for w in group]
    artifact = encode(learned[0],packet) if len(learned)==1 and set(learned[0]) <= {0,2} else None
    candidates = {"cold":None,"inherited":artifact,"sham":None if artifact is None else sham_for(artifact)}
    target_routes = [paths(x) for x in block["probes"]]
    worlds,meters = {},[source_meter]
    for name,(truth,calibration) in regimes(block).items():
        demos = [{"input":x,"output":minimum(paths(x),truth)} for x in block["target_demos"]]
        label = {"input":calibration,"output":minimum(paths(calibration),truth)}
        gold = [minimum(r,truth) for r in target_routes]
        scores = {}
        for budget in (0,1):
            seen = demos+[label] if budget else demos
            arms = {}
            for mode,a in candidates.items():
                result,meter = target_call(root,{"demos":seen,"artifact":a})
                selected = result.pop("selected")
                verify(len(selected)<=896 and all(len(w) in (7,8,9) and all(type(x) is int and x in (1,2)
                       for x in w) for w in selected),"invalid successor version space")
                arms[mode] = {**result,**prediction_metrics(selected,target_routes,gold),
                              "selected_sha256":sha(canonical_json(selected))}
                meters.append(meter)
            scores[str(budget)] = arms
        worlds[name] = {"calibration_label":label["output"],"scores":scores}
    end = worlds["aligned"]["scores"]["1"]["inherited"]
    return {"status":"scored","total":8,"correct":end["covered"]-end["errors"],"source_anchor":source["anchor"],
            "source_classes_sha256":sha(canonical_json(verified)),"source_labels":len(packet["demos"]),
            "artifact":artifact,"artifact_sha256":None if artifact is None else sha(canonical_json(artifact)),
            "worlds":worlds,"resources":meters}


def summary(rows):
    cells = {}
    for condition in ("aligned","shift_visible","shift_hidden"):
        cases = [r["worlds"][condition] for r in rows if condition in r["worlds"]]
        arms = {}
        for budget in ("0","1"):
            arms[budget] = {}
            for mode in MODES:
                runs = [c["scores"][budget][mode] for c in cases]
                arms[budget][mode] = {k:sum(r[k] for r in runs) for k in
                                      ("artifact_used","candidate_fits","covered","errors","false_positive")}
                arms[budget][mode]["full"] = sum(r["covered"]==8 and r["errors"]==0 for r in runs)
        cells[condition] = {"worlds":len(cases),"arms":arms}
    aligned = cells["aligned"]["arms"]["1"]
    visible = cells["shift_visible"]["arms"]["1"]
    passing = (all(r["artifact"] is not None for r in rows) and aligned["inherited"]["full"]>=10
               and aligned["inherited"]["full"]>=aligned["cold"]["full"]+6
               and aligned["inherited"]["full"]>aligned["sham"]["full"]
               and not visible["inherited"]["artifact_used"]
               and all(r["worlds"]["shift_visible"]["scores"]["1"]["inherited"]["selected_sha256"] ==
                       r["worlds"]["shift_visible"]["scores"]["1"]["cold"]["selected_sha256"] for r in rows))
    return {"aligned_transfer":"GO" if passing else "HOLD","natural_decision":"NATURAL_HOLD",
            "lineages":len(rows),"target_worlds":sum(c["worlds"] for c in cells.values()),"cells":cells,
            "source_observation_labels":sum(r["source_labels"]-32 for r in rows),
            "worker_calls":sum(len(r["resources"]) for r in rows)}


def run(ledger, output):
    bank,digest,lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER],digest,lock["sha256"][SOURCE],sha(canonical_json(lock)),
                   SEEDS[3],8,tuple(arms))
    with stage() as root:
        raw,_ = _sandbox_python(["-c","import importlib.util,sys; sys.path.insert(0,'/solver'); "
                                 "print(all(importlib.util.find_spec(x) is None for x in "
                                 "('e14.e14p_graph','e14.e14p_bank','e14.e14p_run')))"],solver=root)
        verify(raw.strip()==b"True","successor can see evaluator")
        boundary["checks"]["successor_stage_without_evaluator"] = True
        rows = run_arms(ledger,plan,lambda arm:evaluate(root,arms[arm]))
    report = {"status":"completed","version":1,"bank_sha256":digest,"plan_sha256":plan.sha256,
              "boundary":boundary,"rows":rows,"summary":summary(rows)}
    temp = output.with_name(output.name+".tmp")
    temp.write_bytes(gzip.compress(canonical_json(report),mtime=0))
    os.replace(temp,output)
    print(json.dumps(report["summary"],sort_keys=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="mode",required=True)
    subs.add_parser("freeze")
    runner = subs.add_parser("run")
    runner.add_argument("ledger",type=Path)
    runner.add_argument("output",type=Path)
    args = p.parse_args()
    if args.mode=="freeze":
        (REPO/BANK).write_bytes(gzip.compress(canonical_json(build()),mtime=0))
        (REPO/LOCK).write_text(json.dumps(manifest(),indent=2,sort_keys=True)+"\n")
    else:
        run(args.ledger,args.output)


if __name__=="__main__":
    main()
