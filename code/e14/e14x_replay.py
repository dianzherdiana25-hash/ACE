"""Replay the E1.4w deterministic learner against transcript-identical countermodels.

The countermodels are synthesized only *after* the completed public development
runs, as adversarial hindsight falsifiers. This is NOT confirmatory scoring.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE
from .e14w_synthesis import evaluate,library,render
from .e14w_study import world,evaluate_arm,source_acquire,IN_FAMILY_EXPRESSIONS
from .e14x_identifiability import audit_reports,build_certificate,measured_costs


FORMULAS={render(library(5)[i]):i for i in IN_FAMILY_EXPRESSIONS}


def verify(paths):
    certificates=audit_reports(paths)
    passed=[];failures=[]
    with tempfile.TemporaryDirectory(prefix='ace-e14x-countermodel-') as temp:
        db=Path(temp)/'replay.sqlite'
        sources={i:source_acquire(i,db) for i in range(12)}
        for case in certificates['cases']:
            source_i=int(case['world'].split(':',2)[1])
            formula=case['world'].split(':',2)[2]
            if formula not in FORMULAS:
                failures.append({'id':case['world'],'reason':'not-in-canonical-base'});continue
            base_world=world(source_i,FORMULAS[formula])
            canonical=next(t for t in library(5) if render(t)==case['accepted_expression'])
            witness=tuple(case['witness_route_costs'])
            motif_pair=PAIR_SPACE[source_i]
            def countermodel(g,ast=canonical,selected=witness,pair=motif_pair):
                return min((evaluate(ast,*c)+int(c==selected)
                            for c in measured_costs(g,pair)),default=None)
            alt_world={**base_world,'oracle':countermodel}
            replay=evaluate_arm(alt_world,sources[source_i],'synthesis-safe',db)
            # Compare public complete transcript against original receipt record.
            original=next(row for path in paths for row in json.loads(Path(path).read_text())['rows']
                          if row['id']==case['world'] and row['mode']==case['mode'])
            orig_receipts=original['target_journal']['receipts']
            replay_receipts=replay['target_journal']['receipts']
            stable_fields=('query_sha256','label','stage','cost','reused_in')
            same=(len(orig_receipts)==len(replay_receipts) and
                  all(all(a[key]==b[key] for key in stable_fields)
                      for a,b in zip(orig_receipts,replay_receipts,strict=True)))
            ok=(same and replay['selected_expr']==case['accepted_expression'] and
                replay['accepted']==1 and replay['semantic_exact']==0 and
                replay['wrong_accepted']==1)
            record={'world':case['world'],'same_transcript':same,
                    'same_selected_program':replay['selected_expr']==case['accepted_expression'],
                    'adversarial_wrong_accepted':bool(replay['wrong_accepted']),
                    'target_labels':replay['target_labels']}
            (passed if ok else failures).append(record)
    return {'version':1,'status':'POSTSCORE_DETERMINISTIC_COUNTERMODEL_REPLAY',
            'scientific_decision':'NOT_ASSESSED','original_certificates':len(certificates['cases']),
            'replay_pass':len(passed),'replay_fail':len(failures),
            'proof_context':'out-of-family operator patches; hindsight witnesses',
            'passed':passed,'failures':failures}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    report=verify(a.reports)
    raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps({**report,'sha256':digest},sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'replayed':report['replay_pass'],
                      'failures':report['replay_fail'],'sha256':digest},sort_keys=True))
    if report['replay_fail']:raise SystemExit(1)

if __name__=='__main__':main()
