"""E1.4t actual-worker Linux namespaces: experimental host capacity only.

This is not native Bubblewrap and is NOT automatically a certified equivalent.
A full isolation threat-model review remains mandatory for scientific acceptance.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path

WORKER = Path(__file__).with_name('e14t_worker.py')


class IsolationUnavailable(RuntimeError):
    pass


def _limit():
    resource.setrlimit(resource.RLIMIT_CPU,(3,3))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**2,4*1024**2))


def sandbox_call(packet, *, timeout=8, worker=None):
    """Run a staged worker without the host checkout, network or home paths.

    Only explicitly staged source is mounted; there is no /mnt, /home, /etc,
    /proc, /sys or host root in the worker's chroot. Use fresh namespaces and
    a network namespace per invocation. Host stdout/stderr are bounded.
    """
    if shutil.which('unshare') is None or shutil.which('chroot') is None:
        raise IsolationUnavailable('unshare/chroot unavailable')
    raw=json.dumps(packet,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
    if len(raw)>131072:
        raise ValueError('worker input too large')
    source=WORKER if worker is None else Path(worker)
    with tempfile.TemporaryDirectory(prefix='ace-e14t-stage-') as parent:
        home=Path(parent)
        stage=home/'stage';stage.mkdir()
        shutil.copyfile(source,stage/'worker.py')
        root=home/'root';root.mkdir()
        script='''
set -eu
mount --make-rprivate /
mount -t tmpfs -o size=128m,nosuid,nodev tmpfs "$ACE_ROOT"
for d in usr lib lib64 solver tmp dev; do mkdir -p "$ACE_ROOT/$d"; done
for d in usr lib lib64; do
  mount --rbind "/$d" "$ACE_ROOT/$d"
  mount -o remount,bind,ro "$ACE_ROOT/$d"
done
mount --bind "$ACE_STAGE" "$ACE_ROOT/solver"
mount -o remount,bind,ro "$ACE_ROOT/solver"
/usr/bin/env -i PATH=/usr/bin:/bin HOME=/nonexistent PYTHONDONTWRITEBYTECODE=1 /usr/sbin/chroot "$ACE_ROOT" /usr/bin/python3 -I -B /solver/worker.py
'''
        env={'PATH':'/usr/bin:/bin','ACE_ROOT':str(root),'ACE_STAGE':str(stage),
             'PYTHONDONTWRITEBYTECODE':'1','HOME':'/nonexistent'}
        try:
            proc=subprocess.run(['unshare','-Urnm','--pid','--fork','sh','-c',script],
                        input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        timeout=timeout,check=False,env=env,preexec_fn=_limit)
        except subprocess.TimeoutExpired as e:
            raise IsolationUnavailable('worker wall-time exceeded') from e
        if len(proc.stdout)>65536 or len(proc.stderr)>65536:
            raise IsolationUnavailable('worker output cap exceeded')
        if proc.returncode:
            raise IsolationUnavailable('worker failed rc='+str(proc.returncode)+' stderr='+proc.stderr.decode('utf-8','replace')[-1500:])
        try:
            result=json.loads(proc.stdout)
        except (ValueError,UnicodeError) as e:
            raise IsolationUnavailable('invalid worker JSON') from e
        return result


def isolation_canary():
    code='''
import json,os,socket
r={"evaluator_absent":not os.path.exists("/mnt/data/ace_sprint/code/e14/e14_integrated_graph.py"),
   "home_absent":not os.path.exists("/home/oai"),
   "project_absent":not os.path.exists("/mnt/data"),
   "host_etc_absent":not os.path.exists("/etc/passwd"),
   "no_root_path_env":"ACE_ROOT" not in os.environ and "ACE_STAGE" not in os.environ,
   "pid_namespace_small_pid":os.getpid()<128}
try:
 s=socket.socket();s.settimeout(.2);s.connect(("1.1.1.1",443));r["external_network_blocked"]=False
except OSError:
 r["external_network_blocked"]=True
try:
 fd=os.open("/usr/bin/ace-illegal-write-probe",os.O_CREAT|os.O_WRONLY,0o600)
 os.close(fd)
 r["system_mount_readonly"]=False
except OSError:
 r["system_mount_readonly"]=True
print(json.dumps(r))
'''
    with tempfile.NamedTemporaryFile('w',suffix='.py',delete=True) as f:
        f.write(code);f.flush()
        packet=sandbox_call({},worker=f.name)
    if not all(packet.values()):
        raise IsolationUnavailable('isolation canary failed '+str(packet))
    return packet
