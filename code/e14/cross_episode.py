"""ACE E1.4c: transfer a query-selection policy between disjoint rule episodes.

Pure local public-development experiment. The candidate only accesses demo
labels and unlabeled question pools, never test labels or hidden rule IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from e13.contract import canonical_json
from e14.query_bank import oracle
from .cross_episode_candidate import POLICIES, choose, fit, predict
from .cross_episode_bank import FAMILIES, REGIMES, bank, digest

SEED = 141702
SHAM_SHIFT = 3


def score(family, guessed, probes):
    return sum(predict(family, guessed, p["input"]) == p["output"] for p in probes)


def refit_one(task, index):
    """One target query, evaluator reveals label only for selected slot."""
    if type(index) is not int or not 0 <= index < 8:
        raise ValueError("invalid one-label index")
    v = task.pool[index]
    example = {"input":v,"output":oracle(task.family,task.word,v)}
    candidates,_=fit(task.family,(*task.demos,example))
    return {"question":index,"correct":score(task.family,candidates[0],task.probes),
            "labels":1,"candidate_count":len(candidates),"chosen":candidates[0]}


def evaluate_source(task):
    """Training-only: exhaustive labeled query interventions for the source."""
    candidates,_=fit(task.family,task.demos)
    arms=[refit_one(task,i) for i in range(8)]
    policy_rows={}
    for policy in POLICIES:
        idx,reason=choose(policy,task.family,candidates,task.pool,seed=SEED+task.pair_id)
        policy_rows[policy]={"index":idx,"reason":reason,"correct":arms[idx]["correct"]}
    return {"task_id":task.task_id,"pair_id":task.pair_id,"family":task.family,
            "regime":task.regime,"word":list(task.word),"candidate_count":len(candidates),
            "source_training_labels":8,"arms":arms,"policies":policy_rows}


def select_inherited(source_rows):
    """Learn one policy per family using ONLY the source intervention scores."""
    selected={}
    for family in FAMILIES:
        rows=[row for row in source_rows if row["family"]==family]
        if len(rows)!=6:
            raise ValueError("six source episodes required per family")
        utilities={p:sum(row["policies"][p]["correct"] for row in rows) for p in POLICIES}
        best=max(POLICIES,key=lambda p:(utilities[p],-POLICIES.index(p)))
        # Sham: permute the utility-to-policy association without target information.
        sham=max(POLICIES,key=lambda p:(utilities[POLICIES[(POLICIES.index(p)+SHAM_SHIFT)
                                                 %len(POLICIES)]],-POLICIES.index(p)))
        selected[family]={"policy":best,"sham_policy":sham,"source_utility":utilities,
                          "source_episodes":len(rows),"source_training_labels":8*len(rows)}
    return selected


def evaluate_target(task,selection):
    candidates,_=fit(task.family,task.demos)
    arms=[refit_one(task,i) for i in range(8)]
    outputs={}
    for alias,policy in (("inherited",selection["policy"]),
                         ("sham",selection["sham_policy"]),
                         ("task_local", "max_partition"),
                         ("local_random_disagreement","seeded_disagreement")):
        idx,reason=choose(policy,task.family,candidates,task.pool,seed=SEED+task.pair_id)
        outputs[alias]={"policy":policy,"index":idx,"reason":reason,
                        "correct":arms[idx]["correct"],"labels":1}
    no_label=score(task.family,candidates[0],task.probes)
    return {"task_id":task.task_id,"pair_id":task.pair_id,"family":task.family,
            "regime":task.regime,"word":list(task.word),"target_candidate_count":len(candidates),
            "target_oracle_counterfactual_labels":8,"no_label":no_label,
            "uniform_expected_numerator":sum(arm["correct"] for arm in arms),
            "uniform_expected_denominator":8,
            "best_possible_one_label":max(a["correct"] for a in arms),
            "policies":outputs,"arms":arms}


def summary(rows):
    summaries=[]
    for family in FAMILIES:
        for regime in REGIMES:
            subset=[r for r in rows if r["family"]==family and r["regime"]==regime]
            if len(subset)!=3:
                raise ValueError("expected three independent targets per stratum")
            x={"family":family,"regime":regime,"episodes":len(subset),
               "total":len(subset)*8,"no_label":sum(r["no_label"] for r in subset),
               "uniform_expected":sum(r["uniform_expected_numerator"] for r in subset)/8,
               "one_label_hindsight_ceiling":sum(r["best_possible_one_label"] for r in subset)}
            for name in ("inherited","sham","task_local","local_random_disagreement"):
                x[name]=sum(r["policies"][name]["correct"] for r in subset)
            summaries.append(x)
    return summaries


def decide(summaries, caps):
    if caps:
        return "HOLD_RESOURCE_INTEGRITY"
    if all(s["inherited"]>max(s["task_local"],s["sham"],s["uniform_expected"],s["no_label"])
           for s in summaries):
        return "GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY"
    return "HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS"


def run(source_commit):
    if not isinstance(source_commit,str) or not re.fullmatch(r"[0-9a-f]{40}",source_commit):
        raise ValueError("prescoring source commit required")
    tasks=bank()
    # All source training is completed and the policy is frozen BEFORE target scoring.
    source_rows=[evaluate_source(source) for source,_ in tasks]
    trained=select_inherited(source_rows)
    targets=[evaluate_target(target,trained[target.family]) for _,target in tasks]
    groups=summary(targets)
    caps=0 # bounded finite enumeration; process wall-time is enforced externally
    report={"mode":"E1.4c_public_development","freeze_version":1,
            "seed":SEED,"bank_seed":141701,"source_commit":source_commit,
            "bank_sha256":digest(tasks),"source_episodes":len(source_rows),
            "target_episodes":len(targets),"total_training_labels":8*len(source_rows),
            "one_label_target_budget_per_policy":1,
            "target_counterfactual_oracle_calls":8*len(targets),
            "learned_policies":trained,"sources":source_rows,"targets":targets,
            "summary":groups,"caps":caps,"decision":decide(groups,caps),
            "limitations":["Finite known 4-event hypothesis grammar, not autonomous new architectures.",
              "Source training consumes 8 labels per episode; per-target parity omits amortization.",
              "Target uniform is exhaustive counterfactual expectation, not a randomized live trial.",
              "Candidate/evaluator are separate Python modules in one process, not isolated workers.",
              "Twelve targets and six sources per family are too small for confirmatory inference."]}
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify",type=Path)
    p.add_argument("--source-commit",required=True)
    args=p.parse_args()
    result=run(args.source_commit)
    if args.verify:
        saved=json.loads(args.verify.read_text())
        if canonical_json(saved)!=canonical_json(result):
            raise ValueError("deterministic E1.4c replication mismatch")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
