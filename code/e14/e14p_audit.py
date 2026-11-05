"""Recompute typed lineage and branching-graph outcomes without either worker."""

import argparse
import json
from itertools import product
from pathlib import Path

from e13.contract import canonical_json
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, predictions, verify
from .e14g_bank import sha
from .e14h_route import read
from .e14m_audit import blank
from .e14n_audit import reference
from .e14p_bank import build
from .e14p_graph import minimum, paths
from .e14p_run import MODES, deterministic, frozen, regimes, schedule, summary


def check_lineage(block, row):
    inputs = block["source_demos"]+block["source_observations"]
    labels = predictions("S",inputs,tuple(block["source_word"]))
    verify(all(len(inputs) not in fit_counts("S",l,inputs,labels).values() for l in (5,6)),
           "source had not invalidated the old classes")
    anchor = next(i for i,y in enumerate(labels) if not blank("S",y))
    _,_,accepted,_ = reference("S",inputs,labels,anchor)
    classes = list(accepted.values())
    surviving = [w for group in classes for w in group]
    if len(surviving)==1 and set(surviving[0]) <= {0,2}:
        packet = {"family":"S","demos":[{"input":x,"output":y} for x,y in zip(inputs,labels,strict=True)]}
        artifact = {"kind":"edge-relative-word-v1","word":[1 if v==0 else 2 for v in surviving[0]],
                    "source_sha256":sha(canonical_json({"source":packet,"learned":surviving[0]}))}
    else:
        artifact = None
    verify((row["source_anchor"],row["source_classes_sha256"],row["source_labels"],row["artifact"],row["artifact_sha256"])
           == (anchor,sha(canonical_json(classes)),len(inputs),artifact,
               None if artifact is None else sha(canonical_json(artifact))),"source lineage mismatch")
    return artifact


def check_world(saved, block, truth, calibration, artifact):
    probes = [paths(x) for x in block["probes"]]
    gold = [minimum(r,truth) for r in probes]
    seen = [paths(x) for x in block["target_demos"]]
    cal = paths(calibration)
    verify(saved["calibration_label"] == minimum(cal,truth),"calibration label mismatch")
    lineage = None if artifact is None else tuple(artifact["word"])
    sham = None if lineage is None else (3-lineage[0],*lineage[1:])
    for cap in (0,1):
        routes = seen+[cal] if cap else seen
        expected = [minimum(r,truth) for r in routes]

        def consistent(word):
            return all(minimum(r,word)==y for r,y in zip(routes,expected,strict=True))

        cold = [w for l in (7,8,9) for w in product((1,2),repeat=l) if consistent(w)]
        for mode, inherited in zip(MODES,(None,lineage,sham),strict=True):
            used = inherited is not None and consistent(inherited)
            chosen = [inherited] if used else cold
            possible = [{minimum(r,w) for w in chosen} for r in probes]
            accepted = [(next(iter(x)),y) for x,y in zip(possible,gold,strict=True) if len(x)==1]
            expected_score = {"artifact_used":used,"candidate_fits":1 if used else 896+int(inherited is not None),
                              "selected_sha256":sha(canonical_json(chosen)),"covered":len(accepted),
                              "errors":sum(x!=y for x,y in accepted),
                              "false_positive":sum(x is not None and y is None for x,y in accepted)}
            verify(saved["scores"][str(cap)][mode]==expected_score,"target fit, cost, or prediction mismatch")


def audit(bank,report):
    todo = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family","regime","block","episode","seed_slot","policy")))
        block = todo.pop(arm)
        artifact = check_lineage(block,row)
        expected = regimes(block)
        verify(set(expected)==set(row["worlds"]),"target regime mismatch")
        for label,(truth,calibration) in expected.items():
            check_world(row["worlds"][label],block,truth,calibration,artifact)
        meters = row["resources"]
        verify(len(meters)==1+6*len(expected) and all(0<=m["cpu_us"]<=1_000_000 and
               0<m["rss_kib"]<=131_072 and 0<=m["wall_us"]<=3_000_000 for m in meters),"resource limit mismatch")
        end = row["worlds"]["aligned"]["scores"]["1"]["inherited"]
        verify(row["correct"]==end["covered"]-end["errors"] and row["status"]=="scored" and row["total"]==8,
               "lineage accounting mismatch")
    verify(not todo and report["status"]=="completed" and report["summary"]==summary(report["rows"]),
           "incomplete report or summary mismatch")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("score",type=Path)
    p.add_argument("replay",type=Path)
    args = p.parse_args()
    bank,digest,_ = frozen()
    score,replay = read(args.score),read(args.replay)
    verify(canonical_json(bank)==canonical_json(build()),"bank reconstruction mismatch")
    verify(score["bank_sha256"]==digest and deterministic(score)==deterministic(replay),"replay mismatch")
    audit(bank,score)
    print(json.dumps({"status":"COMPLETE","lineages":len(score["rows"]),"replay_match":True,
                      "deterministic_sha256":sha(canonical_json(deterministic(score)))},sort_keys=True))


if __name__=="__main__":
    main()
