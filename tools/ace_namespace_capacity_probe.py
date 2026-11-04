"""Developer-only capacity probe for real Linux namespaces, not an ACE scorer.

This script is an independent host check. It neither modifies the frozen
E1.4n protocol nor claims Bubblewrap-equivalent execution.
"""
from __future__ import annotations
import json, os, pathlib, socket, subprocess, tempfile, textwrap, time
from datetime import datetime, timezone

PAYLOAD = r'''
import importlib.util, json, os, pathlib, socket, sys
checks = {}
checks['private_evaluator_file_denied'] = not pathlib.Path(sys.argv[1]).exists()
checks['secret_environment_cleared'] = 'ACE_E14N_CANARY' not in os.environ
checks['evaluator_module_absent'] = importlib.util.find_spec('e14') is None
try:
    pathlib.Path('/solver/trywrite').write_text('bad')
except OSError:
    checks['solver_read_only'] = True
else:
    checks['solver_read_only'] = False
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[2])), timeout=0.35):
        checks['host_loopback_denied'] = False
except OSError:
    checks['host_loopback_denied'] = True
try:
    pathlib.Path('/etc/shadow').read_bytes()
except OSError:
    checks['host_etc_denied'] = True
else:
    checks['host_etc_denied'] = False
print(json.dumps(checks, sort_keys=True))
'''
MOUNT_SCRIPT = r'''#!/bin/sh
set -eu
ROOT="$1"; PRIVATE="$2"; PORT="$3"
mount --make-rprivate /
mount --bind /usr "$ROOT/usr"
mount -o remount,bind,ro "$ROOT/usr"
mount --bind "$ROOT/worker" "$ROOT/solver"
mount -o remount,bind,ro "$ROOT/solver"
mount -t tmpfs -o size=1m,nosuid,nodev tmpfs "$ROOT/tmp"
exec env -i PATH=/usr/bin LANG=C /usr/sbin/chroot "$ROOT" /usr/bin/python3 -I -S /solver/canary.py "$PRIVATE" "$PORT"
'''

def run():
    with tempfile.TemporaryDirectory(prefix='ace-e14n-namespace-') as base, socket.socket() as listener:
        base = pathlib.Path(base)
        listener.bind(('127.0.0.1', 0)); listener.listen(1)
        with socket.create_connection(listener.getsockname(), timeout=2):
            client,_ = listener.accept(); client.close()
        root=base/'jail'; root.mkdir()
        for d in ['usr', 'worker','solver','tmp']:(root/d).mkdir()
        for name,target in [('bin','usr/bin'),('lib','usr/lib'),('lib64','usr/lib64')]:
            (root/name).symlink_to(target)
        (root/'worker'/'canary.py').write_text(PAYLOAD)
        (base/'inside.sh').write_text(MOUNT_SCRIPT)
        private='/mnt/data/ACE_PRIVATE_E14N_NOT_MOUNTED.txt'
        pathlib.Path(private).write_text('confidential evaluator fixture — not exposed to test jail')
        env={**os.environ,'ACE_E14N_CANARY':'HOST_ONLY_DO_NOT_EXPOSE'}
        cmd=['/usr/bin/unshare','--user','--map-root-user','--mount','--net','--pid','--fork',
             '/bin/sh',str(base/'inside.sh'),str(root),private,str(listener.getsockname()[1])]
        t=time.monotonic()
        try:
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=18,env=env)
        finally:
            pathlib.Path(private).unlink(missing_ok=True)
        result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'purpose':'HOST_NAMESPACE_FEASIBILITY_ONLY',
                'frozen_ace_scoring_executed':False,'bubblewrap_validated':False,'elapsed_s':round(time.monotonic()-t,3),
                'exit_code':cp.returncode,'stdout':cp.stdout[-3000:],'stderr':cp.stderr[-3000:]}
        if cp.returncode==0:
            checks=json.loads(cp.stdout.strip()); result['checks']=checks
            result['pass']=all(checks.values()) and len(checks)==6
        else: result['pass']=False
        out=pathlib.Path('/mnt/data/ACE_E14N_namespace_capacity_v1.json');out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return result
if __name__=='__main__':run()
