"""Graph-family OOD transfer of unchanged ACE Runtime and compositional string learner.

New graph solvers are explicitly researcher-supplied controls, NOT ACE-invented
algorithms. Deterministic public synthetic study; no arbitrary source execution.
"""
from __future__ import annotations

from collections import deque
import argparse
import hashlib
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory

from ace_capability_evolution import compositional as c
from ace_runtime.engine import Runtime, validate_task

SOURCE_SHA = "80104ce50ecbcea21080bed8c0eabce88d47ccb5"
PRESCORE_SHA = "aa1bbdafc0cd1c6240e4138bd8b9eec470714a01"
FAMILIES = ("undirected_st_connectivity","undirected_bipartite")
SEEDS = (20261121,20261122)
ARMS = ("dfa","counter","composition","fixed_product")
NATIVE = ("bfs_reachability","bfs_bipartite")
MAX_ATTEMPTS = 100000


def canonical(o):
    return (json.dumps(o,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()


def digest(o):
    return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":"),
                                     allow_nan=False).encode()).hexdigest()


def edge_count(n):
    return n*(n-1)//2


def size_for(word):
    if type(word) is not str or len(word)>100 or set(word)-{"a","b"}:
        raise ValueError("not a bounded simple graph encoding")
    for n in (4,5,7):
        if edge_count(n)==len(word):
            return n
    raise ValueError("unsupported graph size in serialization")


def decode(word):
    n=size_for(word)
    m=[[False]*n for _ in range(n)]
    k=0
    for i in range(n):
        for j in range(i):
            m[i][j]=m[j][i]=(word[k]=="a")
            k+=1
    return m


def encode(matrix):
    n=len(matrix)
    if n not in (4,5,7) or any(len(row)!=n for row in matrix):
        raise ValueError("invalid graph shape")
    if any(type(matrix[i][i]) is not bool or matrix[i][i] for i in range(n)):
        raise ValueError("self-loop forbidden")
    for i in range(n):
        for j in range(i):
            if type(matrix[i][j]) is not bool or matrix[i][j] != matrix[j][i]:
                raise ValueError("expected undirected strict-bool adjacency")
    return "".join("a" if matrix[i][j] else "b" for i in range(n) for j in range(i))


def native_model(kind, word):
    """One of two supplied domain algorithms; counts actual node/edge operations."""
    graph=decode(word)
    n=len(graph)
    scans=0
    visited=0
    if kind=="bfs_reachability":
        queue=deque([0])
        seen={0}
        while queue:
            v=queue.popleft()
            visited+=1
            if v==n-1:
                return True,{"node_visits":visited,"edge_checks":scans}
            for u in range(n):
                scans+=1
                if graph[v][u] and u not in seen:
                    seen.add(u)
                    queue.append(u)
        return False,{"node_visits":visited,"edge_checks":scans}
    if kind=="bfs_bipartite":
        color={}
        for root in range(n):
            if root in color:
                continue
            color[root]=0
            queue=deque([root])
            while queue:
                v=queue.popleft()
                visited+=1
                for u in range(n):
                    scans+=1
                    if not graph[v][u]:
                        continue
                    if u not in color:
                        color[u]=1-color[v]
                        queue.append(u)
                    elif color[u]==color[v]:
                        return False,{"node_visits":visited,"edge_checks":scans}
        return True,{"node_visits":visited,"edge_checks":scans}
    raise ValueError("unknown graph candidate")


def truth(family,word):
    """Separate independent oracle algorithms: union-find and exhaustive coloring."""
    graph=decode(word)
    n=len(graph)
    if family=="undirected_st_connectivity":
        # Union-find, deliberately not the candidate BFS path.
        parent=list(range(n))
        def find(x):
            while parent[x]!=x:
                x=parent[x]
            return x
        for i in range(n):
            for j in range(i):
                if graph[i][j]:
                    parent[find(i)]=find(j)
        return find(0)==find(n-1)
    if family=="undirected_bipartite":
        # Exhaustive 2-color oracle bounded at n=7, unlike the candidate BFS.
        for bits in range(1<<n):
            if all(not graph[i][j] or ((bits>>i)&1)!=((bits>>j)&1)
                   for i in range(n) for j in range(i)):
                return True
        return False
    raise ValueError("unknown graph family")


def matrix_from_word(word):
    return decode(word)


def permute(word, permutation):
    m=decode(word)
    n=len(m)
    if sorted(permutation)!=list(range(n)) or permutation[0]!=0 or permutation[-1]!=n-1:
        raise ValueError("must preserve distinguished endpoint vertices")
    new=[[False]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            new[permutation[i]][permutation[j]]=m[i][j]
    return encode(new)


def all_words(n):
    count=edge_count(n)
    return ["".join("a" if (i>>j)&1 else "b" for j in range(count))
            for i in range(1<<count)]


def balanced_small(family,seed,n,count):
    rng=random.Random(seed)
    grouped={True:[],False:[]}
    for word in all_words(n):
        grouped[truth(family,word)].append(word)
    if any(len(grouped[lab])<count//2 for lab in (True,False)):
        raise RuntimeError("HALT_INSUFFICIENT_BALANCED_GRAPHS")
    chosen=rng.sample(grouped[True],count//2)+rng.sample(grouped[False],count//2)
    rows=sorted(((word,truth(family,word)) for word in chosen),key=lambda x:x[0])
    return rows


def terminal_pairs(family,seed):
    rng=random.Random(seed)
    all_pairs=[]
    used=set()
    tally={True:0,False:0}
    n=7
    for _ in range(MAX_ATTEMPTS):
        if tally[True]==32 and tally[False]==32:
            break
        word="".join("a" if rng.random()<0.35 else "b" for _ in range(edge_count(n)))
        if word in used:
            continue
        lab=truth(family,word)
        if tally[lab]>=32:
            continue
        changed=None
        for _ in range(12):
            inner=list(range(1,n-1))
            rng.shuffle(inner)
            mapping=[0]+inner+[n-1]
            trial=permute(word,mapping)
            if trial!=word and trial not in used:
                changed=trial
                break
        if changed is None:
            continue
        if truth(family,changed)!=lab:
            raise RuntimeError("HALT_PERMUTATION_CHANGES_ORACLE")
        used.update((word,changed))
        tally[lab]+=1
        all_pairs.append(((word,lab),(changed,lab)))
    if len(all_pairs)!=64 or tally != {True:32,False:32}:
        raise RuntimeError("HALT_UNFILLED_TERMINAL_PAIRS")
    rows=[item for pair in all_pairs for item in pair]
    if len({w for w,_ in rows})!=128 or sum(lab for _,lab in rows)!=64:
        raise RuntimeError("HALT_TERMINAL_DUPLICATE_OR_IMBALANCE")
    return rows,[(2*i,2*i+1) for i in range(64)]


def bank(family,seed):
    if family not in FAMILIES or seed not in SEEDS:
        raise ValueError("unknown preregistered trial")
    i=FAMILIES.index(family)
    train=balanced_small(family,910000+seed+i,4,16)
    validation=balanced_small(family,920000+seed+i,5,64)
    terminal,pairs=terminal_pairs(family,930000+seed+i)
    words=[{w for w,_ in part} for part in (train,validation,terminal)]
    if (len(train),len(validation),len(terminal))!=(16,64,128) or any(
        words[i]&words[j] for i,j in ((0,1),(0,2),(1,2))
    ):
        raise RuntimeError("HALT_GRAPH_SPLIT_BUDGET")
    validate_task({"name":"graph_source_test","train":train,"validation":validation})
    for part in (train,validation,terminal):
        if len({w for w,_ in part})!=len(part):
            raise RuntimeError("HALT_GRAPH_DUPLICATES")
        if sum(lab for _,lab in part)*2 != len(part):
            raise RuntimeError("HALT_GRAPH_LABEL_STRATA")
    return {"train":train,"validation":validation,"terminal":terminal,"pairs":pairs}


def permutation_consistency(predictions,pairs):
    return sum(predictions[i]==predictions[j] for i,j in pairs)


def predict_native(kind, rows):
    predictions=[]
    totals={"node_visits":0,"edge_checks":0}
    for word,_ in rows:
        output,work=native_model(kind,word)
        predictions.append(output)
        for key in totals:
            totals[key]+=work[key]
    return predictions,totals


def fit_graph_library(train,validation):
    """No family/task identity or terminal enters the trained graph selector."""
    candidates=[]
    for kind in NATIVE:
        p1,w1=predict_native(kind,train)
        p2,w2=predict_native(kind,validation)
        train_ok=sum(a==b for a,(_,b) in zip(p1,train))
        val_ok=sum(a==b for a,(_,b) in zip(p2,validation))
        scans=w1["edge_checks"]+w2["edge_checks"]
        candidates.append({"kind":kind,"training_correct":train_ok,
                           "validation_correct":val_ok,"edge_scans":scans,
                           "node_visits":w1["node_visits"]+w2["node_visits"],
                           "program_sha256":digest({"name":kind,"class":"fixed_native_graph_library_v1"})})
    selected=min(candidates,key=lambda x:(-x["training_correct"],-x["validation_correct"],
                                          x["edge_scans"],x["kind"]))
    return selected,candidates


def study_world(family,seed):
    data=bank(family,seed)
    train,val,terminal,pairs=(data[key] for key in ("train","validation","terminal","pairs"))
    source_selected,source_info=c.fit(train,val)
    source={}
    for arm in ARMS:
        program=source_selected[arm]
        work=c.Work()
        predictions=[program.predict(w,work) for w,_ in terminal]
        replay=[c.replay(program.data(),w) for w,_ in terminal]
        if predictions!=replay:
            raise RuntimeError("HALT_SOURCE_PROGRAM_REPLAY")
        source[arm]={
            "model_sha256":program.identity,"kind":program.kind,
            "train_correct":source_info["arms"][arm]["train_correct"],
            "validation_correct":source_info["arms"][arm]["validation_correct"],
            "candidates":source_info["arms"][arm]["candidate_count"],
            "terminal_correct":sum(v==y for v,(_,y) in zip(predictions,terminal)),
            "terminal_total":128,
            "permutation_agree_pairs":permutation_consistency(predictions,pairs),
            "terminal_predictions_sha256":digest(predictions),
            "terminal_work":vars(work)}

    selected,inventory=fit_graph_library(train,val)
    graph_predictions,graph_work=predict_native(selected["kind"],terminal)
    oracle_predictions=[truth(family,word) for word,_ in terminal]
    graph_correct=sum(v==lab for v,(_,lab) in zip(graph_predictions,terminal))
    oracle_correct=sum(v==lab for v,(_,lab) in zip(oracle_predictions,terminal))
    if oracle_correct!=128 or any(
        native_model(NATIVE[FAMILIES.index(family)],word)[0]!=lab for word,lab in terminal
    ):
        raise RuntimeError("HALT_NATIVE_ORACLE_DISAGREEMENT")

    with TemporaryDirectory(prefix="ace-graph-research-") as tmp:
        with Runtime(Path(tmp)/"state") as runtime:
            name="graph_transfer_"+str(seed)+"_"+str(FAMILIES.index(family))
            taskid=runtime.enqueue({"name":name,"train":train,"validation":val})
            results=runtime.run(max_tasks=1)
            if len(results)!=1:
                raise RuntimeError("HALT_MISSING_REAL_RUNTIME")
            r=runtime.report(taskid)
            if r!=results[0] or runtime.status()["completed"]!=1:
                raise RuntimeError("HALT_RUNTIME_RECEIPT_MISMATCH")
            evaluation=None
            if r["staged"]:
                evaluation=runtime.evaluate(taskid,terminal)
                predictions=[runtime.predict(taskid,w) for w,_ in terminal]
                if evaluation["correct"]!=sum(v==lab for v,(_,lab) in zip(predictions,terminal)):
                    raise RuntimeError("HALT_TERMINAL_RECEIPT_MISMATCH")
                if evaluation["predictions_sha256"]!=digest(predictions):
                    raise RuntimeError("HALT_EVAL_PREDICTIONS_DIVERGE")
                evaluation={**evaluation,"permutation_agree_pairs":permutation_consistency(predictions,pairs)}
            runtime_row={"staged":r["staged"],"phase":r["phase"],
                         "candidate_identity":r["candidate_identity"],
                         "model_id":r["model_id"],
                         "selection":r["selection"],
                         "terminal":evaluation,
                         "open_world_safe":r["open_world_safe"],
                         "implementation":r["implementation"]}

    opposite=FAMILIES[1-FAMILIES.index(family)]
    altered=sum(truth(opposite,w)!=y for w,y in terminal)
    return {"family":family,"seed":seed,
            "data":{"train_sha256":digest(train),"validation_sha256":digest(val),
                    "terminal_inputs_sha256":digest([w for w,_ in terminal]),
                    "terminal_truth_sha256":digest([y for _,y in terminal]),
                    "train_size":len(train),"validation_size":len(val),
                    "terminal_size":len(terminal),"terminal_permutation_pairs":len(pairs),
                    "terminal_positive":sum(y for _,y in terminal),
                    "opposite_family_disagree_count":altered},
            "source":source,
            "source_fit_costs":{
                "base_merge_attempts":source_info["base_merge_attempts"],
                "residual_merge_attempts":source_info["residual_merge_attempts"],
                "proposal_work":source_info["proposal_work"]},
            "runtime":runtime_row,
            "graph_selector":{"selected":selected,"candidate_inventory":inventory,
                              "terminal_correct":graph_correct,
                              "terminal_total":128,
                              "permutation_agree_pairs":permutation_consistency(graph_predictions,pairs),
                              "predictions_sha256":digest(graph_predictions),
                              "terminal_work":graph_work},
            "native_oracle":{"correct":oracle_correct,"total":128,
                             "permutation_agree_pairs":permutation_consistency(oracle_predictions,pairs)},
            "always_negative_correct":sum(not y for _,y in terminal)}


def experiment():
    trials=[study_world(family,seed) for seed in SEEDS for family in FAMILIES]
    summed={arm:sum(t["source"][arm]["terminal_correct"] for t in trials) for arm in ARMS}
    native_total=sum(t["graph_selector"]["terminal_correct"] for t in trials)
    runtime_staged=[t for t in trials if t["runtime"]["staged"]]
    staged_correct=sum(t["runtime"]["terminal"]["correct"] for t in runtime_staged)
    pairs_consistent=sum(t["graph_selector"]["permutation_agree_pairs"] for t in trials)
    strongest=max(summed["composition"],summed["fixed_product"])
    g2=(len(runtime_staged)>=3 and all(
        t["runtime"]["terminal"]["correct"]>=116 and
        t["runtime"]["terminal"]["permutation_agree_pairs"]>=61 for t in runtime_staged))
    # For true cross-family generalization, require success on *both* families.
    g2=g2 and all(any(t["runtime"]["staged"] and t["family"]==family for t in runtime_staged)
                  for family in FAMILIES)
    g3=native_total>=487 and native_total-strongest>=32
    return {"schema":"ace.graph_family_transfer.public.v1",
            "preregistered_protocol_commit":PRESCORE_SHA,
            "source_main_sha":SOURCE_SHA,
            "seed_ids":list(SEEDS),"families":list(FAMILIES),
            "label_budget":{"worlds":4,"train_per_world":16,"validation_per_world":64,
                            "terminal_per_world":128,"independent_terminal_base_per_world":64,
                            "total_presentations":832,"terminal_not_used_to_fit":512},
            "trials":trials,
            "totals":{"source_terminal_correct":summed,
                      "terminal_total":512,
                      "graph_library_correct":native_total,
                      "stronger_source_comparator_correct":strongest,
                      "graph_library_minus_stronger_source":native_total-strongest,
                      "native_oracle_correct":sum(t["native_oracle"]["correct"] for t in trials),
                      "majority_correct":sum(t["always_negative_correct"] for t in trials),
                      "graph_permutation_agreements":pairs_consistent,
                      "graph_permutation_pairs":256,
                      "runtime_admitted_worlds":len(runtime_staged),
                      "runtime_staged_correct":staged_correct,
                      "runtime_staged_total":len(runtime_staged)*128,
                      "runtime_prediction_coverage":round(len(runtime_staged)/4,6),
                      "task_identity_swap_disagreements":sum(
                          t["data"]["opposite_family_disagree_count"] for t in trials)},
            "gates":{"T1_source_integrity_and_isomorphic_splits":True,
                     "T2_existing_ACE_cross_graph_family_competence":g2,
                     "T3_supplied_native_library_selection_vs_source":g3,
                     "T4_ACE_invented_graph_method":False,
                     "T5_safe_cross_task_reuse_without_validation":False,
                     "T6_exact_replay_and_tamper_contracts":True},
            "native_programs_are_researcher_supplied":True,
            "compute_matched":False,
            "independent_evaluator_sealed":False,
            "graph_task_native_interface_in_core_ACE":False,
            "candidate_deployed":False,
            "scientific_status":"NOT_ASSESSED",
            "release_decision":"BLOCK_RELEASE",
            "oaie_established":False,
            "interpretation":"Graph-native method selection is authored by researchers; current ACE source learner sees lossless adjacency bits but has no graph primitives."}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    report=experiment()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(report)
    args.output.write_bytes(raw)
    print(json.dumps({"report_sha256":hashlib.sha256(raw).hexdigest(),
                      "totals":report["totals"],"gates":report["gates"],
                      "scientific_status":report["scientific_status"],
                      "release_decision":report["release_decision"]},sort_keys=True))


if __name__=="__main__":
    main()
