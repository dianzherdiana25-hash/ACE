"""ACE E1.4x bounded test launcher: durable per-group terminal states.

Run `--group NAME` for one group (not --all on time-limited hosts), then
`--collect` to verify all group receipts, byte-hashed logs and test counts.
No pass is inferred from a timed-out or interrupted job.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ABL='e14.test_e14u_ablation.E14UAblationTests.'
GROUPS={
 'foundation':('e14.test_e14_integrated_graph','e14.test_e14_integrated_policy','e14.test_e14_issue13_smoke','e14.test_e14v_operator','e14.test_e14v_topology','e14.test_e14v_topology_audit'),
 'e14t':('e14.test_e14t','e14.test_e14t_audit'),
 'e14u':('e14.test_e14u_primitive','e14.test_e14u_robustness','e14.test_e14u_audit_worker'),
 'ablation_a':tuple(ABL+x for x in ('test_all_five_conditions_and_pair_truths','test_conservative_grammar_union_has_no_wrong_exact_accept','test_invalid_range_fails','test_namespace_runner_batched_and_deterministic_metrics')),
 'ablation_b':tuple(ABL+x for x in ('test_no_budget_overdraft_and_receipts_replay','test_positive_only_does_not_prove_single_grammar','test_source_ablation_falsifies_premature_single_grammar_acceptance','test_worker_union_matches_independent_fitter_across_inputs')),
 'algebra':('e14.test_e14u_algebra_union',),
 'semantic':('tools.test_ace_e14t_semantic_audit',),
 'w_synthesis':('e14.test_e14w_synthesis','e14.test_e14w_integration'),
 'w_worker':('e14.test_e14w_worker',),
 'x_identifiability':('e14.test_e14x_identifiability','e14.test_e14x_replay','e14.test_e14x_assumption_contract'),
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def atomic_write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes(raw)
    os.replace(temp,path)


def run_one(name,timeout=90):
    if name not in GROUPS:raise ValueError('unknown test group')
    env={**os.environ,'PYTHONPATH':str(ROOT/'code')+os.pathsep+str(ROOT)}
    cmd=[sys.executable,'-W','error::ResourceWarning','-m','unittest',*GROUPS[name],'-q']
    begun=time.monotonic()
    try:
        r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,timeout=timeout,check=False)
        raw=r.stdout+b'\n'+r.stderr
        status='PASS' if r.returncode==0 and b'\nOK' in raw else 'FAIL'
        exit_code=r.returncode
    except subprocess.TimeoutExpired as e:
        raw=(e.stdout or b'')+b'\n'+(e.stderr or b'')
        status='TIMEOUT';exit_code=124
    m=re.search(rb'Ran (\d+) tests?',raw)
    receipt={'version':1,'group':name,'status':status,'exit_code':exit_code,
             'test_count':int(m.group(1)) if m else None,
             'elapsed_seconds':round(time.monotonic()-begun,3),
             'log_sha256':sha(raw),'script_version':'2026-11-05-e14x'}
    folder=ROOT/'WORK'
    atomic_write(folder/f'e14x-run-{name}.log',raw)
    atomic_write(folder/f'e14x-run-{name}.json',(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode())
    return receipt


def collect():
    folder=ROOT/'WORK';rows=[]
    for name in GROUPS:
        receipt_path=folder/f'e14x-run-{name}.json'
        log_path=folder/f'e14x-run-{name}.log'
        if not receipt_path.exists() or not log_path.exists():
            rows.append({'group':name,'status':'MISSING'});continue
        r=json.loads(receipt_path.read_text());raw=log_path.read_bytes()
        if (r.get('group')!=name or r.get('version')!=1 or r.get('log_sha256')!=sha(raw)):
            rows.append({'group':name,'status':'CORRUPTED'});continue
        rows.append(r)
    done=len(rows)==len(GROUPS) and all(r['status']=='PASS' for r in rows)
    result={'version':1,'status':'PASS' if done else 'INCOMPLETE',
            'local_checkout_only':True,'scientific_decision':'NOT_ASSESSED',
            'complete_groups':sum(r['status']=='PASS' for r in rows),
            'required_groups':len(GROUPS),
            'passed_tests':sum(r.get('test_count',0) or 0 for r in rows if r['status']=='PASS'),
            'receipts':rows}
    atomic_write(folder/'e14x-run-aggregate.json',(json.dumps(result,sort_keys=True,indent=2)+'\n').encode())
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    t=p.add_mutually_exclusive_group(required=True)
    t.add_argument('--group',choices=tuple(GROUPS))
    t.add_argument('--collect',action='store_true')
    p.add_argument('--timeout',type=int,default=90)
    a=p.parse_args()
    result=collect() if a.collect else run_one(a.group,a.timeout)
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='PASS' else 2

if __name__=='__main__':sys.exit(main())
