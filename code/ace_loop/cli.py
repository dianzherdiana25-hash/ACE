"""python -m ace_loop.cli run|status --root DIRECTORY [--cycles N]"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .engine import ResearchEngine, ResearchIntegrityError
from .operators import OperatorAdapter


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('run','status','portfolio'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--cycles',type=int,default=12)
    parser.add_argument('--patience',type=int,default=12)
    parser.add_argument('--seed',type=int,default=20261105)
    parser.add_argument('--outsiders-per-split',type=int,default=2)
    parser.add_argument('--pilot-trials',type=int,default=8)
    parser.add_argument('--stop-after-trials',type=int)
    args=parser.parse_args(argv)
    try:
        if args.action=='portfolio':
            from .portfolio import run_portfolio
            response=run_portfolio(args.root,pilot_trials=args.pilot_trials,total_trials=args.cycles)
        else:
            adapter=OperatorAdapter(seed=args.seed,outsiders_per_split=args.outsiders_per_split)
            engine=ResearchEngine(args.root,adapter,max_cycles=args.cycles,patience=args.patience)
            if args.action=='run':
                response=engine.run(stop_after_trials=args.stop_after_trials)
            else:
                rows=engine.ledger.events
                response={'status':rows[-1]['kind'],'events':len(rows),
                          'trials':sum(x['kind']=='trial' for x in rows),
                          'chain_head':rows[-1]['sha256']}
        print(json.dumps(response,sort_keys=True,indent=2))
        return 0
    except ResearchIntegrityError as exc:
        print(json.dumps({'status':'HALT_INTEGRITY_ERROR','reason':str(exc)}))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
