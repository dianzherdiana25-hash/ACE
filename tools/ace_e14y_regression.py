"""Bounded, evidence-preserving ACE E1.4t-y local compatible-workspace regression.

Runs each group in a new Python process with fixed timeout. Fails visibly and
records SHA256 of each actual log. Does not claim a clean complete repository
checkout; that remains separate. No background work or fake PASS flags.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from time import monotonic

GROUPS={
 't_engineering':('e14.test_e14_integrated_graph','e14.test_e14_integrated_policy',
                  'e14.test_e14_issue13_smoke'),
 't_scored':('e14.test_e14t','e14.test_e14t_audit'),
 'u_core':('e14.test_e14u_primitive','e14.test_e14u_audit_worker'),
 'u_ablation_a':tuple('e14.test_e14u_ablation.E14UAblationTests.'+x for x in
        ('test_all_five_conditions_and_pair_truths','test_conservative_grammar_union_has_no_wrong_exact_accept',
         'test_invalid_range_fails','test_namespace_runner_batched_and_deterministic_metrics')),
 'u_ablation_b':tuple('e14.test_e14u_ablation.E14UAblationTests.'+x for x in
        ('test_no_budget_overdraft_and_receipts_replay','test_positive_only_does_not_prove_single_grammar',
         'test_source_ablation_falsifies_premature_single_grammar_acceptance',
         'test_worker_union_matches_independent_fitter_across_inputs')),
 'u_algebra':('e14.test_e14u_algebra_union',),
 'u_robust':('e14.test_e14u_robustness',),
 'v':('e14.test_e14v_operator','e14.test_e14v_topology',
      'e14.test_e14v_topology_audit'),
 'w':('e14.test_e14w_synthesis','e14.test_e14w_integration','e14.test_e14w_worker'),
 'x':('e14.test_e14x_identifiability','e14.test_e14x_replay',
      'e14.test_e14x_assumption_contract'),
 'y':('e14.test_e14y_induction','e14.test_e14y_audit','e14.test_e14y_witness'),
 'semantic':('tools.test_ace_e14t_semantic_audit',),
}


def run(root,out,timeout=90,selected=None):
    out.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'PYTHONPATH':str(root/'code')+os.pathsep+str(root)}
    receipts=[]
    for key,modules in GROUPS.items():
        if selected is not None and key not in selected:continue
        args=[sys.executable,'-W','error::ResourceWarning','-m','unittest',*modules,'-q']
        started=monotonic()
        p=subprocess.Popen(args,cwd=root,env=env,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,start_new_session=True)
        try:
            stdout,stderr=p.communicate(timeout=timeout)
            code=p.returncode;timedout=False;data=stdout+b'\n'+stderr
        except subprocess.TimeoutExpired:
            # Kill the entire group, including inherited pipes from child workers.
            os.killpg(p.pid,signal.SIGKILL)
            stdout,stderr=p.communicate(timeout=10)
            code=124;timedout=True;data=stdout+b'\n'+stderr+b'\nTIMEOUT\n'
        filepath=out/f'e14y-regression-{key}.log'
        filepath.write_bytes(data)
        found=re.search(rb'Ran (\d+) tests? in ',data)
        count=int(found.group(1)) if found else None
        status='PASS' if code==0 and not timedout and count is not None and b'OK' in data else 'FAILED'
        receipt={'group':key,'status':status,'tests':count,
                         'exit_code':code,'timeout':timedout,
                         'elapsed_s':round(monotonic()-started,3),
                         'log_sha256':hashlib.sha256(data).hexdigest(),
                         'modules':modules,'log_file':filepath.name}
        (out/f'e14y-regression-{key}.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        receipts.append(receipt)
        print(f'{key} {status} {count} tests code={code}',flush=True)
    passed=all(r['status']=='PASS' for r in receipts)
    report={'status':'LOCAL_COMPATIBLE_WORKSPACE_PASS' if passed else 'INCOMPLETE_OR_FAIL',
            'scientific_decision':'NOT_ASSESSED',
            'scope':'ACE E1.4t-y partial compatible-workspace regression; not full clean GitHub checkout',
            'groups':receipts,'groups_passed':sum(r['status']=='PASS' for r in receipts),
            'tests_passed':sum((r['tests'] or 0) for r in receipts if r['status']=='PASS'),
            'total_group_count':len(GROUPS)}
    raw=json.dumps(report,sort_keys=True,separators=(',',':')).encode()
    report['sha256']=hashlib.sha256(raw).hexdigest()
    (out/'e14y-regression-summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return 0 if passed else 2


def collect(out):
    rows=[]
    for key in GROUPS:
        log=out/f'e14y-regression-{key}.log'
        receipt=out/f'e14y-regression-{key}.json'
        if not receipt.is_file() or not log.is_file():
            rows.append({'group':key,'status':'MISSING'});continue
        r=json.loads(receipt.read_text());raw=log.read_bytes()
        if r.get('group')!=key or r.get('log_sha256')!=hashlib.sha256(raw).hexdigest():
            rows.append({'group':key,'status':'CORRUPTED'});continue
        rows.append(r)
    passed=len(rows)==len(GROUPS) and all(r['status']=='PASS' for r in rows)
    report={'status':'LOCAL_COMPATIBLE_WORKSPACE_PASS' if passed else 'INCOMPLETE_OR_FAIL',
            'scientific_decision':'NOT_ASSESSED','groups':rows,
            'groups_passed':sum(r['status']=='PASS' for r in rows),
            'tests_passed':sum(r.get('tests',0) or 0 for r in rows if r['status']=='PASS'),
            'total_group_count':len(GROUPS),
            'scope':'partial compatible checkout; not full exact-head GitHub regression'}
    report['sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out.mkdir(parents=True,exist_ok=True)
    (out/'e14y-regression-summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='groups'},sort_keys=True))
    return 0 if passed else 2


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=90)
    p.add_argument('--group',action='append',choices=tuple(GROUPS))
    p.add_argument('--collect',action='store_true')
    a=p.parse_args()
    return collect(a.out.resolve()) if a.collect else run(a.root.resolve(),a.out.resolve(),a.timeout,a.group)

if __name__=='__main__':sys.exit(main())
