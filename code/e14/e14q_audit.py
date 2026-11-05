"""Independently audit weighted query partitions, updates, and held-out labels."""

import argparse
import json
from collections import Counter
from pathlib import Path

from e13.contract import canonical_json, input_value
from e13.evaluator.run_ledger import Arm

from .e14g_audit import verify
from .e14g_bank import sha
from .e14h_route import read
from .e14p_graph import minimum, paths
from .e14p_run import deterministic
from .e14q_run import build, frozen, schedule, summary
from .e14q_worker import CAP, MODES, propose


def audit(bank, report):
    pending = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family","regime","block","episode","seed_slot","policy")))
        block = pending.pop(arm)
        words = list(map(tuple,block["words"]))
        probes = [paths(raw) for raw in block["probes"]]
        verify(set(row["modes"]) == set(MODES),"missing query strategy")
        for mode,meter in zip(MODES,row["resources"],strict=True):
            verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
                   and 0 <= meter["wall_us"] <= 3_000_000,"worker resource cap exceeded")
            record = row["modes"][mode]
            expected = propose(mode,words,block["seed"])
            verify([o["graph"] for o in record["offers"]] == expected and 0 < len(expected) <= CAP,
                   "offer cap or reconstruction mismatch")
            partitions = []
            for graph,offer in zip(expected,record["offers"],strict=True):
                input_value("G",graph)
                routes = paths(graph)
                verify(all(len(events)==7 for events,_ in routes) and 1 <= len(routes) <= 3,
                       "query route shape mismatch")
                outputs = [minimum(routes,w) for w in words]
                verify(offer["predicted"] == outputs,"incorrect query labels")
                partitions.append(outputs)
            ranking = []
            for i,outputs in enumerate(partitions):
                counts = Counter(outputs)
                ranking.append((-sum(n==1 for n in counts.values()),sum(n*n for n in counts.values()),i))
            best = min(ranking)[-1]
            choice = best if len(set(partitions[best]))>1 else None
            verify(record["choice"]==choice and len(record["outcomes"])==4,"query selection mismatch")
            for i,w in enumerate(words):
                actual = None if choice is None else minimum(paths(expected[choice]),w)
                candidates = words if choice is None else [q for q,y in zip(words,partitions[choice],strict=True) if y==actual]
                support = [{minimum(routes,q) for q in candidates} for routes in probes]
                released = [(next(iter(s)),minimum(routes,w)) for s,routes in zip(support,probes,strict=True) if len(s)==1]
                expected_outcome = {"target_index":i,"bought":int(choice is not None),"oracle_label":actual,
                                    "surviving":len(candidates),"covered":len(released),
                                    "errors":sum(p!=y for p,y in released),
                                    "false_positive":sum(p is not None and y is None for p,y in released)}
                verify(record["outcomes"][i]==expected_outcome,"target or probe score mismatch")
        first = row["modes"]["packed"]["outcomes"][0]
        verify(row["correct"]==first["covered"]-first["errors"] and row["total"]==8 and row["status"]=="scored",
               "ledger score mismatch")
    verify(not pending and report["summary"]==summary(report["rows"]) and report["status"]=="completed",
           "incomplete report or aggregate mismatch")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score",type=Path)
    parser.add_argument("replay",type=Path)
    args=parser.parse_args()
    bank,digest,_=frozen()
    score,replay=read(args.score),read(args.replay)
    verify(canonical_json(bank)==canonical_json(build()),"bank regeneration mismatch")
    verify(score["bank_sha256"]==digest and deterministic(score)==deterministic(replay),"replay mismatch")
    audit(bank,score)
    print(json.dumps({"status":"COMPLETE","blocks":len(score["rows"]),"replay_match":True,
                      "deterministic_sha256":sha(canonical_json(deterministic(score)))},sort_keys=True))


if __name__=="__main__":
    main()
