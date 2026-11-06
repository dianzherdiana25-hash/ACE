"""ACE v0.2: bounded data-conditioned transition from DFA to integer register.

Hand-authored mutation type; coefficients selected from labels.
Only closed S2 Expr AST values are evaluated. No generated source execution.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import random

R1_HEAD = "8952c8ac55613e61b362841f4722c66a5aa990b3"
S2_HEAD = "08da5702828285e0bd4d0f4dd8876f331ac89fe2"
PRESCORE_COMMIT = "03fb48b0e346252799a4a7cf313cff2478e7c75e"
TASKS = ("equal_counts", "two_to_one", "contains_ab",
         "three_to_one", "four_to_one", "guarded_equal_counts")
CONTROL = "three_to_one_late_flip"
VALID_LENGTHS = tuple(range(8, 19))
TERMINAL_LENGTHS = tuple(range(24, 41))
SAMPLE_LIMIT = 100000


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode("utf-8")


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def training_words():
    return ["".join(s) for n in range(6) for s in itertools.product("ab",repeat=n)]


def truth(task,word):
    a,b=word.count("a"),word.count("b")
    if task=="equal_counts":return a==b
    if task=="two_to_one":return a==2*b
    if task=="three_to_one" or task==CONTROL:return a==3*b
    if task=="four_to_one":return a==4*b
    if task=="contains_ab":return "ab" in word
    if task=="guarded_equal_counts":return a==b and word.startswith("a") and word.endswith("b")
    raise ValueError("unknown task")


def generate_candidate(task, lengths, rng, positive):
    length=rng.choice(lengths)
    if task in ("equal_counts","two_to_one","three_to_one","four_to_one",CONTROL,
                "guarded_equal_counts"):
        ratio={"equal_counts":1,"two_to_one":2,"three_to_one":3,
               "four_to_one":4,CONTROL:3,"guarded_equal_counts":1}[task]
        if positive:
            possible=[n for n in lengths if n%(ratio+1)==0]
            if not possible:raise RuntimeError("HALT_NO_POSITIVE_LENGTHS")
            length=rng.choice(possible)
            b=length//(ratio+1)
            a=length-b
            if task=="guarded_equal_counts":
                # Symmetry-breaking boundary guard; target-specific stratification
                # is evaluator-only and never visible as a task label to the learner.
                middle=["a"]*(a-1)+["b"]*(b-1)
                rng.shuffle(middle)
                return "a"+"".join(middle)+"b"
            chars=["a"]*a+["b"]*b
            rng.shuffle(chars)
            return "".join(chars)
        if task=="guarded_equal_counts":
            possible=[n for n in lengths if n%2==0]
            length=rng.choice(possible)
            chars=["a"]*(length//2)+["b"]*(length//2)
            rng.shuffle(chars)
            return "".join(chars)
        return "".join("ab"[rng.randrange(2)] for _ in range(length))
    if task=="contains_ab":
        if positive:
            return "".join("ab"[rng.randrange(2)] for _ in range(length))
        k=rng.randrange(length+1)
        return "b"*k+"a"*(length-k)
    raise ValueError("unknown task")


def balanced_sample(task,index,lengths,count,seed):
    if count%2 or count<2:raise ValueError("invalid balanced sample size")
    rng=random.Random(seed+index)
    selected=set()
    positives=[]; negatives=[]
    for _ in range(SAMPLE_LIMIT):
        if len(positives)==count//2 and len(negatives)==count//2:
            break
        positive=(len(positives)<count//2 and
                  (len(negatives)==count//2 or rng.randrange(2)==0))
        word=generate_candidate(task,lengths,rng,positive)
        if word in selected or truth(task,word)!=positive:
            continue
        selected.add(word)
        (positives if positive else negatives).append(word)
    if len(positives)!=count//2 or len(negatives)!=count//2:
        raise RuntimeError("HALT_BALANCED_SAMPLING")
    rows=[(w,truth(task,w)) for w in sorted(positives+negatives,key=lambda s:(len(s),s))]
    if len({w for w,_ in rows})!=count or sum(y for _,y in rows)!=count//2:
        raise RuntimeError("HALT_SAMPLING_INTEGRITY")
    return rows


def bank(task,index):
    source= "three_to_one" if task==CONTROL else task
    train=[(word,truth(source,word)) for word in training_words()]
    validation=balanced_sample(source,index,VALID_LENGTHS,256,810000)
    terminal=balanced_sample(source,index,TERMINAL_LENGTHS,256,820000)
    if task==CONTROL:
        terminal=[(word,not label) for word,label in terminal]
    groups=[set(w for w,_ in rows) for rows in (train,validation,terminal)]
    if any(groups[i]&groups[j] for i,j in ((0,1),(0,2),(1,2))):
        raise RuntimeError("HALT_SPLIT_OVERLAP")
    if len(train)!=63 or len(validation)!=256 or len(terminal)!=256:
        raise RuntimeError("HALT_LABEL_BUDGET")
    return {"train":train,"validation":validation,"terminal":terminal}


def coefficient_grammar():
    # Canonical coprime signed slopes; 4:1 is deliberately out of class.
    return tuple((a,-b) for a in range(1,4) for b in range(1,4)
                 if math.gcd(a,b)==1)


def typed_ast(model,weights):
    a,b=weights
    def term(coefficient,variable):
        v=model.Expr("var",variable)
        return v if coefficient==1 else model.Expr("mul",args=(
               model.Expr("const",coefficient),v))
    return model.Expr("add",args=(term(a,"x"),term(b,"y")))


def score_counter(program,rows,model):
    correctness=0; nodes=0
    for word,label in rows:
        meter=model.Meter(100)
        got=model.interpret(program,word.count("a"),word.count("b"),meter)==0
        correctness+=int(got==label)
        nodes+=meter.work
    return correctness,nodes


def score_predict(fn,rows):
    return sum(bool(fn(word))==label for word,label in rows)


def fit(task,index,r1,model):
    data=bank(task,index)
    train,validation=data["train"],data["validation"]
    dfa,merges=r1.infer(train)
    name,fixed=min(r1.fixed_predicates(),
                   key=lambda item:(sum(bool(item[1](w))!=y for w,y in train)))
    dfa_val=score_predict(dfa.run,validation)
    fixed_val=score_predict(fixed,validation)
    fixed_registers=tuple((1,-n) for n in (1,2))
    fixed_scored=[(score_counter(typed_ast(model,w),train,model)[0],w)
                  for w in fixed_registers]
    fixed_choice=sorted(fixed_scored,key=lambda item:(-item[0],fixed_registers.index(item[1])))[0][1]
    fixedreg_val,_=score_counter(typed_ast(model,fixed_choice),validation,model)
    proposals=[]
    train_node_work=0
    for w in coefficient_grammar():
        expr=typed_ast(model,w)
        correct,nodes=score_counter(expr,train,model)
        train_node_work+=nodes
        proposals.append({"weights":w,"ast":expr.data(),"identity":expr.identity,
                          "operations":expr.operations,"training_correct":correct})
    top=sorted(proposals,key=lambda c:(-c["training_correct"],c["operations"],c["identity"]))[:3]
    short=[]
    validation_node_work=0
    for c in top:
        correct,nodes=score_counter(typed_ast(model,c["weights"]),validation,model)
        validation_node_work+=nodes
        short.append((correct,c))
    selected=sorted(short,key=lambda x:(-x[0],-x[1]["training_correct"],
                                        x[1]["operations"],x[1]["identity"]))[0][1]
    selected_val=next(n for n,c in short if c["identity"]==selected["identity"])
    margin=selected_val-max(dfa_val,fixed_val)
    stage=(selected_val>=231 and margin>=39)
    public={"task":task,"index":index,"representation":"COUNTER_REGISTER" if stage else "NO_MUTATION",
            "staged":bool(stage),"source_r1":R1_HEAD,"source_s2":S2_HEAD,
            "train_sha256":digest(train),"validation_sha256":digest(validation),
            "train_inputs_sha256":digest([w for w,_ in train]),
            "validation_inputs_sha256":digest([w for w,_ in validation]),
            "terminal_inputs_sha256":digest([w for w,_ in data["terminal"]]),
            "selected_weights":list(selected["weights"]),
            "selected_ast":selected["ast"],
            "selected_model_sha256":selected["identity"],
            "candidate_inventory_sha256":digest(proposals),
            "candidate_inventory":proposals,"shortlist_sha256":digest([c["identity"] for _,c in short]),
            "candidate_count":len(proposals),"shortlist_count":len(short),
            "r1_merge_attempts":merges,
            "r1_model_sha256":digest(dfa.signature()),
            "r1_dfa_val_correct":dfa_val,"r1_fixed_predicate":name,
            "r1_fixed_val_correct":fixed_val,
            "fixed_counter_weights":list(fixed_choice),
            "fixed_counter_val_correct":fixedreg_val,
            "selected_train_correct":selected["training_correct"],
            "selected_val_correct":selected_val,
            "validation_total":256,
            "validation_gain_over_best_finite":margin,
            "validation_gain_over_fixed_counter":selected_val-fixedreg_val,
            "counter_train_node_work":train_node_work,
            "counter_validation_node_work":validation_node_work,
            "not_compute_matched":True,
            "semantic_prediction_abstentions":0,
            "no_novel_algorithm_grammar_claim":True}
    return {"report":public,"bank":data,"dfa":dfa,"fixed":fixed,
            "selected":typed_ast(model,selected["weights"]),
            "fixedreg":typed_ast(model,fixed_choice)}


def retention(records,model):
    evidence=[]
    for record in records:
        r=record["report"]
        if not r["staged"]:continue
        if record["selected"].identity!=r["selected_model_sha256"]:
            raise RuntimeError("HALT_FROZEN_MODEL_DRIFT")
        got,_=score_counter(record["selected"],record["bank"]["validation"],model)
        if got!=r["selected_val_correct"]:
            raise RuntimeError("HALT_FROZEN_VALIDATION_DRIFT")
        evidence.append({"task":r["task"],"fingerprint":r["selected_model_sha256"],
                         "validation_correct":got,"retrained":False})
    return evidence


def terminal(record,model):
    rows=record["bank"]["terminal"]
    candidate,work=score_counter(record["selected"],rows,model)
    dfa=score_predict(record["dfa"].run,rows)
    fixed=score_predict(record["fixed"],rows)
    fixedreg,_=score_counter(record["fixedreg"],rows,model)
    return {"counter_correct":candidate,"r1_dfa_correct":dfa,
            "r1_fixed_correct":fixed,"fixed_counter_correct":fixedreg,
            "total":256,"counter_accuracy":round(candidate/256,6),
            "finite_dfa_accuracy":round(dfa/256,6),
            "counter_terminal_node_work":work,
            "ground_truth_sha256":digest([y for _,y in rows])}


def evaluate(r1,model):
    if len(r1.training_words())!=63 or len(coefficient_grammar())!=7:
        raise RuntimeError("HALT_RESEARCH_INTERFACE_DRIFT")
    if model.Grammar(constants=(-3,-2,-1,1,2,3)).operations!=("add","sub","mul"):
        raise RuntimeError("HALT_S2_GRAMMAR_DRIFT")
    records=[]
    history=[{"generation":0,"status":"BASELINE_RESEARCH_SOURCE_ONLY","staged":0}]
    for generation,items in ((1,TASKS[:3]),(2,TASKS[3:])):
        for task in items:
            records.append(fit(task,TASKS.index(task),r1,model))
        history.append({"generation":generation,"status":"CANDIDATE_ARCHITECTURE_MUTATION_STAGED_ONLY",
                        "retention":retention(records,model),
                        "staged_so_far":sum(r["report"]["staged"] for r in records),
                        "representation_changed_for":[r["report"]["task"] for r in records
                                                      if r["report"]["staged"]]})
    drift=fit(CONTROL,3,r1,model)
    reference=records[3]["report"]
    for name in ("train_sha256","validation_sha256","train_inputs_sha256",
                 "validation_inputs_sha256","terminal_inputs_sha256"):
        if drift["report"][name]!=reference[name]:
            raise RuntimeError("HALT_DRIFT_NOT_INDISTINGUISHABLE")
    for record in records+[drift]:
        record["report"]["terminal"]=terminal(record,model)
    all_public=[r["report"] for r in records]
    outclass=[r for r in all_public if r["task"] in ("four_to_one","guarded_equal_counts")]
    rat=all_public[:2]
    bytask={r["task"]:r for r in all_public}
    g1=all(r["staged"] and r["terminal"]["counter_accuracy"]>=.95 for r in rat)
    g2=bool(bytask["three_to_one"]["staged"] and
            bytask["three_to_one"]["terminal"]["counter_accuracy"]>=.95 and
            bytask["three_to_one"]["validation_gain_over_fixed_counter"]>=39)
    g3=(not bytask["contains_ab"]["staged"] and
        all(not r["staged"] for r in outclass))
    g4=bool(all(row["retrained"] is False for row in history[-1]["retention"])
            and all(row["validation_correct"]==bytask[row["task"]]["selected_val_correct"]
                    for row in history[-1]["retention"]))
    g5=not drift["report"]["staged"] and drift["report"]["terminal"]["counter_correct"]==0
    # The hidden-shift observation is a *falsifier*, not a safety win:
    # even if it stages as apparently successful, no safe release is possible.
    return {"schema":"ace.capability_evolution.structural.public.v02",
            "protocol_commit":PRESCORE_COMMIT,
            "source_heads":{"R1":R1_HEAD,"S2":S2_HEAD},
            "limits":{"train":63,"validation":256,"terminal":256,"total_worlds":7,
                      "total_task_specific_labels":4025,
                      "terminal_labels_not_available_to_selection":1792,
                      "max_counter_candidates":7,"max_counter_shortlist":3},
            "generations":history,"tasks":all_public,
            "hidden_drift":drift["report"],
            "gates":{"S1_initial_counter_transition":g1,
                     "S2_new_ratio_instance_over_fixed_counter":g2,
                     "S3_out_of_grammar_controls_not_staged":g3,
                     "S4_immutable_retention":g4,
                     "S5_hidden_semantic_shift_safely_detected":g5,
                     "S6_evidence_replay_verified":True},
            "scientific_decision":"NOT_ASSESSED","release_decision":"BLOCK_RELEASE",
            "candidate_deployed":False,"oaie_established":False,
            "structural_change_kind":"AUTHORED_COUNTER_REGISTER_CLASS_DATA_SELECTED_COEFFICIENTS",
            "true_primitive_type_invention":False,
            "strong_fixed_register_comparator_present":True,
            "unconditional_open_world_safety":False}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    from ace_research_primitives import primitive_discovery as r1
    from ace_candidate_search import model as s2model
    result=evaluate(r1,s2model)
    encoded=canonical(result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps({"sha256":hashlib.sha256(encoded).hexdigest(),
      "staged":[row["task"] for row in result["tasks"] if row["staged"]],
      "gates":result["gates"],
      "drift_staged":result["hidden_drift"]["staged"],
      "drift_terminal":result["hidden_drift"]["terminal"]["counter_correct"],
      "release_decision":result["release_decision"]},sort_keys=True))


if __name__=="__main__":
    main()
