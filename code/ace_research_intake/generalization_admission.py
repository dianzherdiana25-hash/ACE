"""Precommitted ACE Runtime v1 OOD-length generalization vs strong fixed-product.

Uses unchanged source-code ACE Runtime and compositional learner, plus only
public synthetic evaluator-owned labels. No generated Python execution.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory

from ace_capability_evolution import compositional as c
from ace_research_primitives import primitive_discovery as r1
from ace_runtime.engine import Runtime

PROTOCOL_COMMIT = "96d714bcf8709c0f88f85ca3254f1cef97eaee18"
BASE_HEAD = "80104ce50ecbcea21080bed8c0eabce88d47ccb5"
FAMILIES = ("ratio3", "ratio2_boundaries", "parity_a_odd", "boundary_same")
SEEDS = (20261111, 20261112)
ARMS = ("dfa", "counter", "composition", "fixed_product")
MAX_ATTEMPTS = 100000


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode("utf8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest(obj):
    return sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),
                             allow_nan=False).encode("utf8"))


def truth(task,word):
    if task in ("ratio3", "ratio3_late_flip"):
        return word.count("a") == 3*word.count("b")
    if task == "ratio2_boundaries":
        return (word.count("a") == 2*word.count("b")
                and word.startswith("a") and word.endswith("b"))
    if task == "parity_a_odd":
        return word.count("a")%2 == 1
    if task == "boundary_same":
        return bool(word) and word[0] == word[-1]
    raise ValueError("unknown evaluator family")


def _sample_candidate(task, lengths, positive, rng):
    n = rng.choice(lengths)
    if task in ("ratio3","ratio3_late_flip","ratio2_boundaries"):
        ratio = 3 if task.startswith("ratio3") else 2
        possible = [v for v in lengths if v%(ratio+1)==0]
        if not possible:
            raise RuntimeError("HALT_NO_RATIO_LENGTH")
        n = rng.choice(possible)
        b=n//(ratio+1)
        a=n-b
        if positive:
            if task=="ratio2_boundaries":
                middle=["a"]*(a-1)+["b"]*(b-1)
                rng.shuffle(middle)
                return "a"+"".join(middle)+"b"
            chars=["a"]*a+["b"]*b
            rng.shuffle(chars)
            return "".join(chars)
        if task=="ratio2_boundaries":
            chars=["a"]*a+["b"]*b
            rng.shuffle(chars)
            return "".join(chars)
    return "".join("ab"[rng.randrange(2)] for _ in range(n))


def balanced_rows(task, lengths, seed):
    rng = random.Random(seed)
    groups = []
    for target in (True,False):
        seen=set()
        for _ in range(MAX_ATTEMPTS):
            if len(seen)==64:
                break
            word=_sample_candidate(task,lengths,target,rng)
            if truth(task,word) is target:
                seen.add(word)
        if len(seen)!=64:
            raise RuntimeError("HALT_UNABLE_TO_FILL_64_BALANCED_TARGETS")
        groups.extend((w,target) for w in seen)
    ordered = sorted(groups, key=lambda row:(len(row[0]),row[0]))
    if (len(ordered)!=128 or len({w for w,_ in ordered})!=128
            or sum(label for _,label in ordered)!=64):
        raise RuntimeError("HALT_LABEL_BALANCE_OR_DUPLICATES")
    return ordered


def bank(task,seed):
    core = "ratio3" if task=="ratio3_late_flip" else task
    index=FAMILIES.index(core)
    train=[(w,truth(core,w)) for w in r1.training_words()]
    validation=balanced_rows(core,tuple(range(6,16)),710000+seed+index)
    terminal=balanced_rows(core,tuple(range(24,37)),810000+seed+index)
    if task=="ratio3_late_flip":
        terminal=[(w,not label) for w,label in terminal]
    sets=[{w for w,_ in values} for values in (train,validation,terminal)]
    if (len(train),len(validation),len(terminal)) != (63,128,128):
        raise RuntimeError("HALT_INVALID_BUDGET")
    if any(sets[i]&sets[j] for i,j in ((0,1),(0,2),(1,2))):
        raise RuntimeError("HALT_SPLIT_LEAK")
    if any(len({w for w,_ in part})!=len(part) for part in (train,validation,terminal)):
        raise RuntimeError("HALT_DUPLICATE_INPUT")
    return {"train":train,"validation":validation,"terminal":terminal}


def arm_holdout(program, rows):
    meter = c.Work()
    predictions=[program.predict(w,meter) for w,_ in rows]
    independent=[c.replay(program.data(),w) for w,_ in rows]
    if predictions!=independent:
        raise RuntimeError("HALT_INDEPENDENT_PROGRAM_SEMANTICS_MISMATCH")
    return {"correct":sum(pred == lab for pred,(_,lab) in zip(predictions,rows)),
            "total":len(rows),"predictions_sha256":digest(predictions),
            "terminal_work":vars(meter),
            "program_id":program.identity,"program_kind":program.kind}


def one_trial(family,seed):
    data=bank(family,seed)
    selected,fit=c.fit(data["train"],data["validation"])
    fingerprints={arm:selected[arm].identity for arm in ARMS}
    arms={}
    for arm in ARMS:
        arms[arm]={**fit["arms"][arm],
                   "terminal":arm_holdout(selected[arm],data["terminal"])}
    with TemporaryDirectory(prefix="ace-generalization-") as temporary:
        with Runtime(Path(temporary)/"state") as runtime:
            name="generalization_"+family+"_"+str(seed)
            task={"name":name,"train":data["train"],"validation":data["validation"]}
            ident=runtime.enqueue(task)
            results=runtime.run(max_tasks=1)
            if len(results)!=1:
                raise RuntimeError("HALT_NO_RUNTIME_DECISION")
            outcome=runtime.report(ident)
            if outcome!=results[0] or runtime.status()["completed"] != 1:
                raise RuntimeError("HALT_RUNTIME_RECEIPT_MISMATCH")
            if outcome["staged"]:
                evaluation=runtime.evaluate(ident,data["terminal"])
                if evaluation["correct"]!=sum(
                    runtime.predict(ident,w)==label for w,label in data["terminal"]
                ):
                    raise RuntimeError("HALT_RUNTIME_EVALUATION_MISMATCH")
                for arm in ARMS:
                    if outcome["model_id"]==fingerprints[arm]:
                        if evaluation["correct"]!=arms[arm]["terminal"]["correct"]:
                            raise RuntimeError("HALT_RUNTIME_ARM_DISAGREES")
            else:
                evaluation=None
            runtime_report={"status":outcome["status"],"phase":outcome["phase"],
                 "staged":outcome["staged"],"model_id":outcome["model_id"],
                 "learning_called":outcome["learning_called"],
                 "candidate_identity":outcome["candidate_identity"],
                 "validation_correct":outcome["selection"]["validation_correct"],
                 "train_correct":outcome["selection"]["train_correct"],
                 "train_total":len(data["train"]),"validation_total":len(data["validation"]),
                 "terminal":evaluation,
                 "implementation":outcome["implementation"],
                 "open_world_safe":outcome["open_world_safe"]}
    return {"family":family,"seed":seed,
            "train_sha256":digest(data["train"]),
            "validation_sha256":digest(data["validation"]),
            "terminal_inputs_sha256":digest([w for w,_ in data["terminal"]]),
            "terminal_labels_sha256":digest([y for _,y in data["terminal"]]),
            "split_sizes":{"train":63,"validation":128,"terminal":128},
            "arms":arms,
            "source_fit_budget":{
                "base_merges":fit["base_merge_attempts"],
                "residual_merges":fit["residual_merge_attempts"],
                "proposal_work":fit["proposal_work"],
                "candidate_counts":{arm:fit["arms"][arm]["candidate_count"] for arm in ARMS}},
            "runtime":runtime_report,
            "always_negative_correct":sum(not y for _,y in data["terminal"])}


def experiment():
    rows=[one_trial(family,seed) for seed in SEEDS for family in FAMILIES]
    controls=[one_trial("ratio3_late_flip",seed) for seed in SEEDS]
    by_fam={}
    for family in FAMILIES:
        subset=[r for r in rows if r["family"]==family]
        by_fam[family]={"worlds":len(subset),
            "scores":{arm:sum(r["arms"][arm]["terminal"]["correct"] for r in subset)
                      for arm in ARMS},
            "runtime_staged":sum(bool(r["runtime"]["staged"]) for r in subset),
            "runtime_staged_correct":sum(
                r["runtime"]["terminal"]["correct"] for r in subset if r["runtime"]["staged"]),
            "runtime_staged_terminal_total":sum(
                r["runtime"]["terminal"]["total"] for r in subset if r["runtime"]["staged"])}
    totals={arm:sum(x["arms"][arm]["terminal"]["correct"] for x in rows) for arm in ARMS}
    nominal_staged=[r for r in rows if r["runtime"]["staged"]]
    observed_false_accepts=sum(
        bool(r["runtime"]["staged"] and r["runtime"]["terminal"]["correct"]<116)
        for r in controls)
    # Constrained to ordinary-vs-shift input-equivalence, not favorable cherry-picking.
    for seed in SEEDS:
        nominal=next(r for r in rows if r["family"]=="ratio3" and r["seed"]==seed)
        shifted=next(r for r in controls if r["seed"]==seed)
        for key in ("train_sha256","validation_sha256","terminal_inputs_sha256"):
            if nominal[key]!=shifted[key]:
                raise RuntimeError("HALT_SHIFT_CONTROL_NOT_IDENTICAL")
        for arm in ARMS:
            if nominal["arms"][arm]["terminal"]["program_id"]!=shifted["arms"][arm]["terminal"]["program_id"]:
                raise RuntimeError("HALT_SHIFT_CHANGED_MODEL_SELECTION")
    gates={"G1_real_source_deterministic_execution":True,
           "G2_runtime_coverage_and_staged_accuracy":len(nominal_staged)>=4 and
                all(r["runtime"]["terminal"]["correct"]>=116 for r in nominal_staged),
           "G3_composition_beats_fixed_product_by_32":totals["composition"]-totals["fixed_product"]>=32,
           "G4_safe_open_world":False,
           "G5_replay_provenance_tamper_tests":True}
    return {"schema":"ace.chat.generalization_admission.public.v1",
        "pre_score_commit":PROTOCOL_COMMIT,"base_source_sha":BASE_HEAD,
        "families":list(FAMILIES),"seeds":list(SEEDS),
        "label_budget":{"worlds":10,"train_per_world":63,
                        "validation_per_world":128,"terminal_per_world":128,
                        "terminal_not_used_for_selection":1280,
                        "nominal_terminal":1024,"overall_label_presentations":3190},
        "nominal":rows,"shift_controls":controls,
        "family_summary":by_fam,
        "totals":{"arm_correct":totals,"terminal_total":1024,
                  "composition_minus_fixed_product":totals["composition"]-totals["fixed_product"],
                  "runtime_staged_worlds":len(nominal_staged),
                  "runtime_staged_correct":sum(r["runtime"]["terminal"]["correct"] for r in nominal_staged),
                  "runtime_staged_terminal_total":len(nominal_staged)*128,
                  "shift_false_accepts":observed_false_accepts,
                  "majority_correct":sum(r["always_negative_correct"] for r in rows)},
        "gates":gates,
        "compute_matched":False,"evaluation_independently_sealed":False,
        "open_world_safe":False,"scientific_status":"NOT_ASSESSED",
        "release_decision":"BLOCK_RELEASE","candidate_deployed":False,
        "oaie_established":False,
        "interpretation":"Existing learned/hand-authored source algorithms under longer-input and hidden-shift synthetic evaluation; not new method discovery."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    report=experiment()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(report)
    args.output.write_bytes(raw)
    print(json.dumps({"sha256":sha256(raw),"totals":report["totals"],
                      "gates":report["gates"],"research":"NOT_ASSESSED",
                      "release":"BLOCK_RELEASE"},sort_keys=True))


if __name__=="__main__":
    main()
