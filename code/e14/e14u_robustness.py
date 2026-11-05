"""E1.4u post-development seed sensitivity study, never confirmatory scoring."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import e14u_dev as dev
from .e14u_primitive import PAIR_SPACE

SEEDS=(2026110507,2026110508,2026110509,2026110510,2026110511,2026110512,2026110513,2026110514)


def evaluate():
    original=dev.SEED
    trials=[]
    try:
        for seed in SEEDS:
            dev.SEED=seed
            summary={m:{"exact":0,"purchased":0,"wrong_accepted":0,"covered":0} for m in dev.MODES}
            with tempfile.TemporaryDirectory(prefix="ace-e14u-seed-") as tmp:
                for idx in range(len(PAIR_SPACE)):
                    world=dev.make_world("pair",idx)
                    for mode in dev.MODES:
                        row=dev.run_arm(world,mode,Path(tmp)/"journals.sqlite")
                        for key in summary[mode]:summary[mode][key]+=row[key]
            trials.append({"seed":seed,"worlds":len(PAIR_SPACE),"arms":len(PAIR_SPACE)*len(dev.MODES),
                           "summary":summary})
    finally:
        dev.SEED=original
    return {"status":"POST_DEVELOPMENT_SENSITIVITY_ONLY",
            "original_development_seed":SEEDS[0],"trials":trials,
            "caveat":"same 28 pair truths, varied demonstration contexts and policy seeds; not held-out independent distribution"}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path)
    args=p.parse_args();r=evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":r['status'],"rows":[(x['seed'],x['summary']['active']['exact'],
                       x['summary']['fixed']['exact'],x['summary']['random']['exact'])
                       for x in r['trials']]},sort_keys=True))

if __name__=='__main__':main()
