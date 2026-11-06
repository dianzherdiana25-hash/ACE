"""Source-exact retained ACE Runtime transfer vs fresh per-task runtime."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from ace_runtime.engine import Runtime
from . import generalization_admission as g

PRESCORE="37706b8b86121f2052de08c14e4f09285830901a"
BASE="80104ce50ecbcea21080bed8c0eabce88d47ccb5"
PAIRS=(("ratio3","ratio2_boundaries"),("ratio2_boundaries","ratio3"),
       ("parity_a_odd","boundary_same"),("boundary_same","parity_a_odd"))


def run_sequence(families,seed,shift=False):
    with TemporaryDirectory(prefix="ace-crossfamily-") as d:
        root=Path(d)/"state"
        results=[]
        with Runtime(root) as runtime:
            for index,family in enumerate(families):
                core="ratio3" if family=="ratio3_late_flip" else family
                data=g.bank(family,seed)
                task={"name":f"seq_{index}_{core}_{seed}","train":data["train"],
                      "validation":data["validation"]}
                ident=runtime.enqueue(task)
                completed=runtime.run(max_tasks=1)
                if len(completed)!=1 or completed[0]!=runtime.report(ident):
                    raise RuntimeError("runtime report inconsistent")
                receipt=runtime.report(ident)
                eval_result=runtime.evaluate(ident,data["terminal"]) if receipt["staged"] else None
                results.append({"family":family,"observed_hash":g.digest((data["train"],data["validation"])),
                    "terminal_words_hash":g.digest([w for w,_ in data["terminal"]]),
                    "terminal_labels_hash":g.digest([label for _,label in data["terminal"]]),
                    "phase":receipt["phase"],"staged":receipt["staged"],
                    "model_id":receipt["model_id"],"candidate_identity":receipt["candidate_identity"],
                    "learning_called":receipt["learning_called"],
                    "inherited_candidates":receipt["inherited_candidates"],
                    "fit_report":receipt["fit_report"],
                    "selection":receipt["selection"],
                    "terminal":eval_result})
            before=runtime.status()
        with Runtime(root) as reopened:
            after=reopened.status()
            if before!=after or before["completed"]!=len(families) or before["failed"]!=0:
                raise RuntimeError("durability or chain verification mismatch")
    return {"families":list(families),"seed":seed,"results":results,
            "status":after,"shift":shift}


def run():
    trials=[]
    for seed in g.SEEDS:
        for offset in range(4):
            sequence=g.FAMILIES[offset:]+g.FAMILIES[:offset]
            trials.append(run_sequence(sequence,seed))
        for pair in PAIRS:
            trials.append(run_sequence(pair,seed))
    controls=[run_sequence(("ratio3","ratio3_late_flip"),seed,True) for seed in g.SEEDS]
    targets=[]
    for trial in trials:
        target=trial["results"][-1]
        fresh=run_sequence((trial["families"][-1],),trial["seed"])["results"][0]
        if target["family"]!=fresh["family"] or target["observed_hash"]!=fresh["observed_hash"]:
            raise RuntimeError("target/fresh comparison invalid")
        if target["terminal_words_hash"]!=fresh["terminal_words_hash"] or target["terminal_labels_hash"]!=fresh["terminal_labels_hash"]:
            raise RuntimeError("terminal mismatch")
        targets.append({"family":target["family"],"seed":trial["seed"],
            "predecessors":trial["families"][:-1],"retained":target,"fresh":fresh})
    for ctrl in controls:
        src,target=ctrl["results"]
        if src["observed_hash"]!=target["observed_hash"] or src["terminal_words_hash"]!=target["terminal_words_hash"]:
            raise RuntimeError("hidden control observational mismatch")
        if src["terminal"] and target["terminal"] and src["terminal"]["correct"]+target["terminal"]["correct"]!=128:
            raise RuntimeError("inverted terminal not complementary")
    def terminal_score(t):
        return t["terminal"]["correct"] if t["terminal"] is not None else 0
    def coverage(t):
        return int(t["staged"])
    reuse=sum(t["retained"]["phase"]=="REUSE_VALIDATED" and not t["retained"]["learning_called"] for t in targets)
    losses=[{"index":i,"family":t["family"],"retained":terminal_score(t["retained"]),
             "fresh":terminal_score(t["fresh"])}
            for i,t in enumerate(targets) if (coverage(t["retained"])<coverage(t["fresh"]) or
            (coverage(t["retained"]) and coverage(t["fresh"]) and terminal_score(t["retained"])<terminal_score(t["fresh"]))) ]
    false_accepts=sum(bool(t["results"][-1]["staged"] and
                           t["results"][-1]["terminal"]["correct"]<116) for t in controls)
    summary={"targets":len(targets),"reuse_validated":reuse,
             "retained_staged":sum(coverage(t["retained"]) for t in targets),
             "fresh_staged":sum(coverage(t["fresh"]) for t in targets),
             "retained_correct_on_all_targets":sum(terminal_score(t["retained"]) for t in targets),
             "fresh_correct_on_all_targets":sum(terminal_score(t["fresh"]) for t in targets),
             "lost_or_regressed":losses,
             "shift_false_admissions":false_accepts,"shift_controls":len(controls),
             "H1_transfer_efficiency_without_regression":reuse>=2 and not losses,
             "H2_hidden_shift_safe":false_accepts==0}
    return {"schema":"ace.chat.crossfamily.public.v1","prescore_commit":PRESCORE,
        "source_base_sha":BASE,"nominal":trials,"comparisons":targets,
        "controls":controls,"summary":summary,
        "baseline":"fresh same-source ACE Runtime; additional PR60 four source arms",
        "compute_matched":False,"independent_holdout":False,"open_world_safe":False,
        "scientific_status":"NOT_ASSESSED","release_decision":"BLOCK_RELEASE",
        "candidate_deployed":False,"oaie_established":False}


def canonical(data):
    return (json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args(argv)
    obj=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(obj)
    args.output.write_bytes(raw)
    print(json.dumps({"sha256":hashlib.sha256(raw).hexdigest(),"summary":obj["summary"],
                      "release":obj["release_decision"]},sort_keys=True))


if __name__=="__main__":
    main()
