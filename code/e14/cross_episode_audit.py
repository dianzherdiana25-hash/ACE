"""Post-score standard-library-only arithmetic auditor for E1.4c report.

This does not validate oracle semantics, query-pool independence, or candidate
isolation. All checks operate on a saved JSON report without importing solver.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

POLICIES=("first_disagreement","last_disagreement","short_disagreement",
          "long_disagreement","max_partition","min_partition",
          "seeded_disagreement","seeded_uniform")


def ensure(ok,reason):
    if not ok:raise ValueError(reason)


def audit(r):
    ensure(r.get("mode")=="E1.4c_public_development","mode")
    ss,ts=r.get("sources"),r.get("targets")
    ensure(isinstance(ss,list) and isinstance(ts,list) and len(ss)==len(ts)==12,"episode count")
    ensure(len({x["task_id"] for x in ss+ts})==24,"duplicate task")
    ensure(r["source_episodes"]==12 and r["target_episodes"]==12,"reported episodes")
    ensure(r["total_training_labels"]==96 and r["target_counterfactual_oracle_calls"]==96,"label budget")
    known=r["learned_policies"]
    ensure(set(known)=={"S","G"},"families")
    for family in ("S","G"):
        subset=[x for x in ss if x["family"]==family]
        ensure(len(subset)==6,"source family")
        totals={p:0 for p in POLICIES}
        for item in subset:
            ensure(item["source_training_labels"]==8 and len(item["arms"])==8,"source arms")
            for p in POLICIES:
                v=item["policies"][p]
                ensure(type(v["index"]) is int and 0<=v["index"]<8,"source selector")
                ensure(v["correct"]==item["arms"][v["index"]]["correct"],"source score")
                totals[p]+=v["correct"]
        ensure(totals==known[family]["source_utility"],"source utility")
        expected=max(POLICIES,key=lambda p:(totals[p],-POLICIES.index(p)))
        sham=max(POLICIES,key=lambda p:(totals[POLICIES[(POLICIES.index(p)+3)%8]],-POLICIES.index(p)))
        ensure(known[family]["policy"]==expected and known[family]["sham_policy"]==sham,"selected policy")
    computed=[]
    for fam in ("S","G"):
        for regime in ("related","unrelated"):
            group=[x for x in ts if x["family"]==fam and x["regime"]==regime]
            ensure(len(group)==3,"target family/regime")
            row={"family":fam,"regime":regime,"episodes":3,"total":24,
                 "no_label":0,"uniform_expected":0.,"one_label_hindsight_ceiling":0}
            for key in ("inherited","sham","task_local","local_random_disagreement"):
                row[key]=0
            for item in group:
                arms=item["arms"]
                ensure(len(arms)==8 and item["target_oracle_counterfactual_labels"]==8,"target arms")
                ensure(all(type(a["correct"]) is int and 0<=a["correct"]<=8 for a in arms),"score bounds")
                ensure(item["uniform_expected_numerator"]==sum(a["correct"] for a in arms) and
                       item["uniform_expected_denominator"]==8,"uniform numerator")
                ensure(item["best_possible_one_label"]==max(a["correct"] for a in arms),"oracle ceiling")
                ensure(0<=item["no_label"]<=8,"no-label bounds")
                row["no_label"]+=item["no_label"]
                row["uniform_expected"]+=sum(a["correct"] for a in arms)/8
                row["one_label_hindsight_ceiling"]+=max(a["correct"] for a in arms)
                for alias in ("inherited","sham","task_local","local_random_disagreement"):
                    a=item["policies"][alias]
                    index=a["index"]
                    ensure(type(index) is int and 0<=index<8 and a["correct"]==arms[index]["correct"]
                           and a["labels"]==1,"policy arm mismatch")
                    if alias=="inherited":
                        ensure(a["policy"]==known[fam]["policy"],"inherited policy mismatch")
                    if alias=="sham":
                        ensure(a["policy"]==known[fam]["sham_policy"],"sham policy mismatch")
                    row[alias]+=a["correct"]
            computed.append(row)
    ensure(computed==r["summary"],"summary mismatch")
    expected="GO_CROSS_EPISODE_TRANSFER_DEVELOPMENT_ONLY" if all(
        x["inherited"]>max(x["task_local"],x["sham"],x["uniform_expected"],x["no_label"])
        for x in computed) else "HOLD_CROSS_EPISODE_TRANSFER_HYPOTHESIS"
    ensure(r["caps"]==0 and r["decision"]==expected,"decision mismatch")
    return {"status":"INTERNAL_REPORT_ARITHMETIC_PASS","sources":len(ss),"targets":len(ts),
            "source_training_labels":96,"target_counterfactual_oracle_calls":96,
            "decision":expected,"summary":computed,
            "limitations":["Saved JSON consistency only; no oracle-semantic or split leakage check.",
                           "v1 pool RNG draw stream can depend on word-dependent demo filtering.",
                           "No independent worker isolation; development-only study."]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("json_file",type=Path)
    args=ap.parse_args()
    print(json.dumps(audit(json.loads(args.json_file.read_text())),indent=2,sort_keys=True))

if __name__=="__main__":main()
