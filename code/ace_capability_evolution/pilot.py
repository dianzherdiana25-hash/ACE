"""ACE bounded multi-generation public capability acquisition pilot.

Actual research implementations imported from pinned R1 and S2 heads.
All outputs STAGED_ONLY; no arbitrary candidate source execution or production promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random

R1_HEAD = "8952c8ac55613e61b362841f4722c66a5aa990b3"
S2_HEAD = "08da5702828285e0bd4d0f4dd8876f331ac89fe2"
PROTOCOL = "4f6f8b5cfa7b3728d21d723696111652d4d85969"


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def binary_words(start, stop):
    return ["".join(chars) for n in range(start, stop+1)
            for chars in itertools.product("ab", repeat=n)]


def sequence_truth(task, word):
    a = word.count("a") % 4 == 0
    if task == "a_mod4":
        return a
    if task == "b_mod4":
        return word.count("b") % 4 == 0
    if task == "late_rule_inversion":
        return a if len(word) <= 7 else not a
    raise ValueError("unknown sequence task")


def arithmetic_truth(task, x, y):
    if task == "x_minus_y":
        return x-y
    if task == "product_plus_two":
        return x*y+2
    raise ValueError("unknown arithmetic task")


def sequence_bank(task, index):
    train = binary_words(0, 5)
    validation = binary_words(6, 7)
    terminal = random.Random(900000+index).sample(binary_words(8, 12), 256)
    if (len(set(train+validation+terminal)) != 511 or
            set(train) & set(validation) or set(terminal) & (set(train)|set(validation))):
        raise RuntimeError("HALT_SPLIT_OVERLAP")
    return {
        "train": [(word, sequence_truth(task, word)) for word in train],
        "validation": [(word, sequence_truth(task, word)) for word in validation],
        "terminal": [(word, sequence_truth(task, word)) for word in terminal],
    }


def arithmetic_bank(task, index, model):
    # Test coordinates are known to the external evaluator, not the candidate search.
    coordinates = list(itertools.product(range(-7,8), repeat=2))
    selected = random.Random(910000+index).sample(coordinates, 26)
    if len(set(selected)) != 26:
        raise RuntimeError("HALT_SPLIT_OVERLAP")
    train, val, terminal = selected[:6], selected[6:10], selected[10:]
    def make(part):
        return tuple(model.Observation(x, y, arithmetic_truth(task,x,y)) for x,y in part)
    return {"train":make(train), "validation":make(val), "terminal":make(terminal)}


def seq_score(predict, rows):
    return sum(type(predict(word)) is bool and predict(word) == y for word,y in rows)


def expr_score(expr, rows, model, search):
    result = search.evaluate(expr, rows, model.Meter(100000))
    return result


def validate_source(r1, search_mod, model):
    if binary_words(0,5) != r1.training_words():
        raise RuntimeError("HALT_R1_TRAIN_API_DRIFT")
    if not hasattr(r1,"infer") or not hasattr(search_mod,"Search"):
        raise RuntimeError("HALT_SOURCE_API_MISSING")
    if len(search_mod.fixed_candidates()) != 5:
        raise RuntimeError("HALT_S2_FIXED_LIBRARY_DRIFT")
    for x in (model.Grammar, model.Limits, model.Observation, model.Expr):
        if not callable(x):
            raise RuntimeError("HALT_TYPED_CONTRACT_DRIFT")


def fit_sequence(task, index, r1):
    bank = sequence_bank(task,index)
    train,val=bank["train"],bank["validation"]
    candidate,merge_attempts=r1.infer(train)
    if any(candidate.run(word)!=expected for word,expected in train):
        raise RuntimeError("HALT_TRAIN_INCONSISTENT")
    baseline_name,baseline=min(r1.fixed_predicates(),
        key=lambda pair:sum(pair[1](word)!=answer for word,answer in train))
    candidate_val=seq_score(candidate.run,val)
    baseline_val=seq_score(baseline,val)
    accepted=(candidate_val >= 173 and candidate_val - baseline_val >= 10)
    model_data=candidate.signature()
    trial={"domain":"sequence","task":task,"index":index,
           "baseline_predicate":baseline_name,
           "train_sha256":digest(train),"validation_sha256":digest(val),
           "terminal_inputs_sha256":digest([word for word,_ in bank["terminal"]]),
           "candidate_source":"R1_PR38_DFA_INFER",
           "model_fingerprint":digest(model_data),
           "model_state_count":candidate.reachable(),"merges":merge_attempts,
           "training_correct":seq_score(candidate.run,train),"training_total":len(train),
           "validation_candidate_correct":candidate_val,
           "validation_baseline_correct":baseline_val,"validation_total":len(val),
           "staged":accepted,"stage_reason":"validation_gain" if accepted else "validation_gate_not_met",
           "_model":candidate,"_baseline":baseline,"_bank":bank}
    return trial


def fit_arithmetic(task,index,source,model):
    bank=arithmetic_bank(task,index,model)
    train,val=bank["train"],bank["validation"]
    grammar=model.Grammar(constants=(0,1,2,3),operations=("add","sub","mul"))
    limits=model.Limits(max_depth=3,max_operations=3,max_candidates=800,
                        max_work=100000,beam_width=20,shortlist=8)
    factory=source.Search(grammar,limits,train,mode="beam")
    digest_stream=[]
    search_stop=None
    for kind,event in factory.events():
        if kind=="trial":
            digest_stream.append(event["id"])
        if kind=="search_stop":
            search_stop=event
    if search_stop is None or len(digest_stream)>800:
        raise RuntimeError("HALT_SEARCH_MISSING_STOP")
    baseline_candidates=source.fixed_candidates()
    baseline=min(baseline_candidates,
        key=lambda e:(expr_score(e,train,model,source)["absolute_error"],e.key))
    baseline_val=expr_score(baseline,val,model,source)
    contenders=[]
    for expr,training_result in factory.shortlist():
        if training_result["status"]!="ok":
            continue
        validation_result=expr_score(expr,val,model,source)
        if validation_result["status"]=="ok":
            contenders.append((validation_result["absolute_error"],
                               training_result["absolute_error"],
                               expr.operations,expr.depth,expr.key,expr))
    winner=min(contenders,key=lambda row:row[:5])[-1] if contenders else None
    winner_val=expr_score(winner,val,model,source) if winner is not None else None
    accepted=bool(winner_val and winner_val["status"]=="ok"
                  and winner_val["absolute_error"]==0
                  and winner_val["absolute_error"]<baseline_val["absolute_error"])
    trial={"domain":"arithmetic","task":task,"index":index,
           "candidate_source":"S2_PR36_TYPED_BEAM",
           "train_sha256":digest([[z.x,z.y,z.target] for z in train]),
           "validation_sha256":digest([[z.x,z.y,z.target] for z in val]),
           "terminal_inputs_sha256":digest([[z.x,z.y] for z in bank["terminal"]]),
           "candidate_fingerprints_sha256":digest(digest_stream),
           "searched_candidates":len(digest_stream),
           "search_stop":search_stop["reason"],"search_work":search_stop["search_work"],
           "baseline_ast":baseline.data(),
           "model_ast":winner.data() if winner is not None else None,
           "model_fingerprint":winner.identity if winner is not None else None,
           "training_candidate_abs_error":contenders[0][1] if winner is not None else None,
           "validation_candidate_abs_error":winner_val["absolute_error"] if winner_val else None,
           "validation_baseline_abs_error":baseline_val["absolute_error"],
           "validation_total":len(val),
           "staged":accepted,"stage_reason":"validation_gain" if accepted else "validation_gate_not_met",
           "_model":winner,"_baseline":baseline,"_bank":bank}
    return trial


def score_terminal(trial, r1, search_mod, model):
    rows=trial["_bank"]["terminal"]
    if trial["domain"]=="sequence":
        candidate=seq_score(trial["_model"].run,rows)
        baseline=seq_score(trial["_baseline"],rows)
    else:
        candidate=expr_score(trial["_model"],rows,model,search_mod)["correct"] if trial["_model"] else 0
        baseline=expr_score(trial["_baseline"],rows,model,search_mod)["correct"]
    return {"candidate_correct":candidate,"baseline_correct":baseline,
            "total":len(rows),"candidate_accuracy":round(candidate/len(rows),6),
            "baseline_accuracy":round(baseline/len(rows),6)}


def public(trial):
    return {key:value for key,value in trial.items() if not key.startswith("_")}


def review_retention(trials, r1, search_mod, model):
    # These are task-specific frozen artifacts; do NOT interpret as neural continual learning.
    for record in trials:
        if not record["staged"]:
            continue
        if record["domain"]=="sequence":
            if digest(record["_model"].signature()) != record["model_fingerprint"]:
                raise RuntimeError("HALT_CAPABILITY_MUTATED")
            new_score=seq_score(record["_model"].run,record["_bank"]["validation"])
            if new_score!=record["validation_candidate_correct"]:
                raise RuntimeError("HALT_RETENTION_REGRESSION")
        else:
            if record["_model"].identity!=record["model_fingerprint"]:
                raise RuntimeError("HALT_CAPABILITY_MUTATED")
            new=expr_score(record["_model"],record["_bank"]["validation"],model,search_mod)
            if new["absolute_error"]!=record["validation_candidate_abs_error"]:
                raise RuntimeError("HALT_RETENTION_REGRESSION")
    return {"checked":sum(t["staged"] for t in trials),
            "immutable_task_artifacts":True,
            "validation_retested_without_refit":True,
            "not_lifelong_learning_proof":True}


def run_pilot(r1, s2search, s2model):
    validate_source(r1,s2search,s2model)
    records=[];generations=[]
    generations.append({"generation":0,"stage":"BASELINE_ONLY",
                        "task_specific_capabilities":0,"no_algorithm_search":True})
    for generation,specs in (
        (1,(("sequence","a_mod4",0),("arithmetic","x_minus_y",0))),
        (2,(("sequence","b_mod4",1),("arithmetic","product_plus_two",1))),
    ):
        added=[]
        for domain,name,index in specs:
            record=(fit_sequence(name,index,r1) if domain=="sequence"
                    else fit_arithmetic(name,index,s2search,s2model))
            records.append(record)
            added.append({"task":name,"staged":record["staged"],
                          "fingerprint":record["model_fingerprint"]})
        retention=review_retention(records,r1,s2search,s2model)
        generations.append({"generation":generation,"stage":"TASK_SPECIFIC_STAGING_ONLY",
              "new_candidates":added,"cumulative_staged":sum(x["staged"] for x in records),
              "retention":retention})
    # The adversarial task has identical observable labels to the original a_mod4
    # but inverses all terminal truth; no algorithm may infer this from identical observations.
    drift=fit_sequence("late_rule_inversion",0,r1)
    a4=next(x for x in records if x["task"]=="a_mod4")
    if drift["train_sha256"]!=a4["train_sha256"] or drift["validation_sha256"]!=a4["validation_sha256"]:
        raise RuntimeError("HALT_DRIFT_CONTROL_NOT_INDISTINGUISHABLE")
    for record in records:
        record["terminal"]=score_terminal(record,r1,s2search,s2model)
    drift["terminal"]=score_terminal(drift,r1,s2search,s2model)
    final_good=sum(record["staged"] and (
                (record["terminal"]["candidate_accuracy"]>=.9) if record["domain"]=="sequence"
                else (record["terminal"]["candidate_correct"]==record["terminal"]["total"]))
                for record in records)
    staged=sum(x["staged"] for x in records)
    gate={"G1_first_generation_staged":any(x["staged"] for x in records[:2]),
          "G2_both_modalities_staged_and_frozen":
             (all(any(x["staged"] and x["domain"]==d for x in records) for d in ("sequence","arithmetic"))
              and generations[-1]["retention"]["immutable_task_artifacts"]),
          "G3_terminal_success_on_at_least_3_of_4":final_good>=3,
          "G4_indistinguishable_drift_safely_detected":False,
          "G5_deterministic_evidence_and_provenance":True}
    return {"schema":"ace.capability_evolution.public_pilot.v0.1",
      "protocol_commit":PROTOCOL,
      "pinned_sources":{"R1":R1_HEAD,"S2":S2_HEAD},
      "generations":generations,
      "tasks":[public(x) for x in records],
      "negative_controls":[{"kind":"INDISTINGUISHABLE_LATE_DRIFT",
           **public(drift),"feature_stage_not_equal_semantic_safety":True,
           "forced_prediction_without_ood_detector":True}],
      "staged_task_capabilities":staged,
      "nominal_terminal_gate_successes":final_good,
      "gates":gate,
      "scientific_status":"NOT_ASSESSED",
      "release_decision":"BLOCK_RELEASE",
      "candidate_deployed":False,
      "aoie_not_established":True,
      "interpretation":"Fixed authored algorithms reused on new task-specific instances; no general self-created algorithm or architecture."}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    from ace_research_primitives import primitive_discovery as r1
    from ace_candidate_search import search as s2search
    from ace_candidate_search import model as s2model
    report=run_pilot(r1,s2search,s2model)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    data=canonical(report)
    args.output.write_bytes(data)
    print(json.dumps({"sha256":hashlib.sha256(data).hexdigest(),
                      "gates":report["gates"],
                      "staged":report["staged_task_capabilities"],
                      "terminal_good":report["nominal_terminal_gate_successes"],
                      "negative_control":report["negative_controls"][0]["terminal"],
                      "release_decision":report["release_decision"]},sort_keys=True))


if __name__=="__main__":
    main()
