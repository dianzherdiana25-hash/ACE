"""Nonconfirmatory public E1.4u development evaluation.

World generator *knows* truths; worker-side candidate fitter and query selector
never see the truth, probes or oracle. Evaluation uses one SQLite four-label
journal per world and arm, independent oracle replay, matched initial examples.
This process is IN-PROCESS, NOT an isolated scientific or confirmatory score.
"""
from __future__ import annotations

import hashlib
import json
import random
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_routes, purchase
from .e14u_primitive import (PAIR_SPACE, PAIR_WORDS, _matches, diagnose, fit,
                             graph_from_routes, oracle, program, guarded_predict,
                             select_query)

MODES = ("active", "fixed", "random", "base-only")
TRIPLE_WORDS = tuple(combinations(PAIR_WORDS, 3))[:6]
SEED = 2026110507


def triple_oracle(graph, words):
    routes = graph_routes(graph)[0]
    return min((max(ci, cj, ck) for i, (ei, ci) in enumerate(routes)
                for j, (ej, cj) in enumerate(routes)
                for k, (ek, ck) in enumerate(routes)
                if len({i, j, k}) == 3 and _matches(ei, words[0])
                and _matches(ej, words[1]) and _matches(ek, words[2])), default=None)


def make_world(kind, index):
    rng = random.Random(SEED + 991 * index + (0 if kind == "pair" else 999_997))
    if kind == "pair":
        truth = program("branch-pair", PAIR_SPACE[index])
        a, b = truth[1]
        routes = [(rng.choice((1,2)), *a, rng.choice((1,2))),
                  (rng.choice((1,2)), *b, rng.choice((1,2)))]
        calibration = [graph_from_routes(routes, [0,3]),
                       graph_from_routes(routes[:1]), graph_from_routes(routes[1:])]
        evaluate = lambda g: oracle(g, truth)
    elif kind == "single":
        truth = program("single-path", (PAIR_WORDS[index],))
        a = (1, *truth[1][0], 2)
        b = (2, *(tuple(3-x for x in truth[1][0])), 1)
        calibration = [graph_from_routes([a,b],[0,3]),
                       graph_from_routes([a]),graph_from_routes([b])]
        evaluate = lambda g: oracle(g, truth)
    elif kind == "triple":
        truth = ("branch-triple-hidden", TRIPLE_WORDS[index])
        a, b, c = truth[1]
        calibration = [graph_from_routes([a,b,c], [0,2,5]),
                       graph_from_routes([a,b]),graph_from_routes([b,c]),
                       graph_from_routes([a,c])]
        evaluate = lambda g: triple_oracle(g,truth[1])
    else:
        raise ValueError("unknown world kind")
    demonstrations = [{"input": g,"output": evaluate(g)} for g in calibration]
    # Held-out graph tolls differ from the hardcoded 70-query selector pool.
    options = list(PAIR_WORDS)
    probes = []
    for k in range(6):
        subset = rng.sample(options, 4)
        probes.append(graph_from_routes(subset, [1,4,7,10] if k%2 else [10,7,4,1]))
    return {"id": f"{kind}:{index}","kind": kind,"truth": truth,
            "demonstrations": demonstrations,"probes": probes,
            "oracle": evaluate}


def run_arm(world, mode, database):
    if mode not in MODES:
        raise ValueError("unknown evaluation arm")
    journal = DurableGraphBudget(database, f'{world["id"]}:{mode}')
    known = list(world["demonstrations"])
    initial = diagnose(known)
    expand = initial["trigger"] and mode != "base-only"
    candidates = (initial["extended"] if expand else initial["base"])["candidates"]
    stage_trace = []
    for turn in range(4):
        if len(candidates) <= 1:
            break
        graph = select_query(candidates,
                             [row["query"] for row in journal.snapshot()["receipts"]],
                             mode="fixed" if mode == "base-only" else mode,
                             seed=SEED+turn+len(known)+len(world["id"]))
        if graph is None:
            break
        stage = "diagnosis" if turn == 0 else "qualification"
        rid, label = purchase(journal, stage, graph, world["oracle"])
        known.append({"input":graph,"output":label})
        if stage == "diagnosis":
            journal.reuse(rid,"repair")  # no second target-label charge
        candidates = fit(known, extended=expand)["candidates"]
        stage_trace.append({"stage":stage,"receipt":rid,"label":label,
                            "survivors":len(candidates)})
    snapshot = journal.snapshot()
    replay = audit_journal(snapshot, world["oracle"])
    accepted = len(candidates) == 1
    exact = accepted and candidates[0] == world["truth"]
    predictions = [guarded_predict(candidates, g) for g in world["probes"]]
    gold = [world["oracle"](g) for g in world["probes"]]
    covered = sum(int(row["covered"]) for row in predictions)
    errors = sum(int(row["prediction"] != true) for row,true in zip(predictions,gold)
                 if row["covered"])
    return {"arm":mode,"world":world["id"],"kind":world["kind"],
            "demos":len(known)-snapshot["purchased"],
            "trigger":initial["trigger"],"expanded":expand,
            "base_fits":initial["base"]["candidate_fits"],
            "extension_fits":(initial["extended"]["candidate_fits"] if expand else 0),
            "initial_candidates":len((initial["extended"] if expand else initial["base"])["candidates"]),
            "remaining_candidates":len(candidates),"purchased":snapshot["purchased"],
            "audit_calls":replay["auditor_oracle_calls"],
            "query_cost":snapshot["query_cost_totals"],
            "accepted":int(accepted),"exact":int(exact),
            "wrong_accepted":int(accepted and not exact),
            "covered":covered,"probe_errors":errors,
            "trace":stage_trace,"journal":snapshot}


def report():
    worlds = [make_world("pair", i) for i in range(len(PAIR_SPACE))]
    worlds += [make_world("single",i) for i in range(len(PAIR_WORDS))]
    worlds += [make_world("triple",i) for i in range(len(TRIPLE_WORDS))]
    rows = []
    with tempfile.TemporaryDirectory(prefix="ace-e14u-dev-") as home:
        for world in worlds:
            for mode in MODES:
                rows.append(run_arm(world,mode,Path(home)/"labels.sqlite"))
    summary = {}
    for kind in ("pair", "single", "triple"):
        summary[kind] = {}
        for mode in MODES:
            selected = [row for row in rows if row["kind"]==kind and row["arm"]==mode]
            summary[kind][mode] = {k:sum(row[k] for row in selected) for k in
                ("purchased","audit_calls","accepted","exact","wrong_accepted",
                 "covered","probe_errors")}
            summary[kind][mode]["worlds"] = len(selected)
    raw = {"version":1,"scope":"NONCONFIRMATORY_IN_PROCESS_PUBLIC_DEVELOPMENT",
           "seed":SEED,"worlds":len(worlds),"arms":len(rows),
           "candidate_grammar":"single contiguous motif OR unordered distinct two-route conjunction",
           "source_cost":"initial oracle-labelled demonstrations are outside 4-label intervention cap",
           "controls":list(MODES),"summary":summary,"rows":rows}
    digest=hashlib.sha256(json.dumps(raw,allow_nan=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return raw,digest


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    raw,digest=report()
    if a.output:
        a.output.parent.mkdir(exist_ok=True,parents=True)
        a.output.write_text(json.dumps(raw,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":raw["scope"],"worlds":raw["worlds"],"arms":raw["arms"],
                      "sha256":digest,"summary":raw["summary"]},sort_keys=True))

if __name__=="__main__":
    main()
