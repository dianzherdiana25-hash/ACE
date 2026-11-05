"""ACE E1.5 bounded, no-network stdlib regression groups with durable receipts.

Use --group NAME for one small process, repeat all eight groups, then --collect.
Never treats a timeout, missing receipt, or falsified log as a passing test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

TESTS={
'e15':['ace_loop.test_engine','ace_loop.test_portfolio'],
'legacy':['e14.test_e14y_induction','e14.test_e14y_audit','e14.test_e14z_drift','e14.test_e14z_audit','e14.test_e14_integrated_graph','e14.test_e14_integrated_policy'],
'u':['e14.test_e14u_primitive','e14.test_e14u_robustness','e14.test_e14u_algebra_union'],
'v':['e14.test_e14v_operator','e14.test_e14v_topology','e14.test_e14v_topology_audit'],
'w':['e14.test_e14w_synthesis','e14.test_e14w_integration','e14.test_e14w_worker'],
'x':['e14.test_e14x_identifiability','e14.test_e14x_replay','e14.test_e14x_assumption_contract'],
't':['e14.test_e14t','e14.test_e14t_audit','e14.test_e14_issue13_smoke'],
'u-ablation':['e14.test_e14u_ablation'],
'tooling':['tools.test_ace_e15_regression']}
PATTERN=re.compile(r'^Ran (\d+) tests? in [\d.]+s\s*\n\s*OK\s*$',re.M)


def sha(b):return hashlib.sha256(b).hexdigest()
def atomic(path,obj):
    blob=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False).encode()+b'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('xb') as out:
        out.write(blob);out.flush();os.fsync(out.fileno())
    temp.replace(path)


def run(group,root,output,timeout):
    if group not in TESTS:raise ValueError('unknown frozen test group')
    if type(timeout) is not int or not 10<=timeout<=240:raise ValueError('invalid process timeout')
    output.mkdir(parents=True,exist_ok=True)
    receipt=output/(group+'.json')
    if receipt.exists():raise FileExistsError('immutable group receipt exists: '+str(receipt))
    args=[sys.executable,'-m','unittest',*TESTS[group],'-q']
    env=dict(os.environ,PYTHONPATH=str(root/'code')+os.pathsep+str(root))
    start=time.monotonic()
    try:
        process=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                               timeout=timeout,check=False)
        exitcode=process.returncode;content=process.stdout
    except subprocess.TimeoutExpired as exc:
        exitcode=124;content=(exc.stdout or b'')+b'\nTIMEOUT_FROZEN_TEST_GROUP\n'
    log=output/(group+'.log')
    with log.open('xb') as out:
        out.write(content);out.flush();os.fsync(out.fileno())
    match=PATTERN.search(content.decode('utf-8','replace'))
    count=int(match.group(1)) if match else 0
    summary={'group':group,'modules':TESTS[group],'exit_code':exitcode,'tests_passed':count if exitcode==0 else 0,
             'status':'PASS' if exitcode==0 and match else 'FAIL_OR_INCOMPLETE',
             'log_sha256':sha(content),'log_bytes':len(content),
             'wall_seconds':round(time.monotonic()-start,3),'python':sys.version.split()[0]}
    atomic(receipt,summary)
    return summary


def collect(output):
    rows=[]
    for name,modules in TESTS.items():
        receipt=output/(name+'.json');log=output/(name+'.log')
        if not receipt.is_file() or not log.is_file():raise ValueError('missing group receipt '+name)
        obj=json.loads(receipt.read_bytes())
        b=log.read_bytes()
        m=PATTERN.search(b.decode('utf-8','replace'))
        if set(obj)!={'group','modules','exit_code','tests_passed','status','log_sha256','log_bytes','wall_seconds','python'}:
            raise ValueError('invalid receipt fields')
        if obj['group']!=name or obj['modules']!=modules or type(obj['exit_code']) is not int or obj['exit_code']!=0 or obj['status']!='PASS':
            raise ValueError('invalid test outcome '+name)
        if not m or type(obj['tests_passed']) is not int or obj['tests_passed']!=int(m.group(1)) or obj['log_sha256']!=sha(b) or obj['log_bytes']!=len(b):
            raise ValueError('log/receipt mismatch '+name)
        rows.append(obj)
    return {'status':'PASS_COMPATIBLE_CHECKOUT_ONLY','tests':sum(x['tests_passed'] for x in rows),
            'groups':len(rows),'receipts':rows,'not_exact_head_full_repo':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=tuple(TESTS))
    parser.add_argument('--collect',action='store_true')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=120)
    args=parser.parse_args()
    if bool(args.group)==bool(args.collect):parser.error('choose exactly --group or --collect')
    try:
        result=collect(args.output) if args.collect else run(args.group,args.root.resolve(),args.output,args.timeout)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result['status'].startswith('PASS') else 2
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'HALT_INCOMPLETE','error':str(exc)}))
        return 2

if __name__=='__main__':raise SystemExit(main())
