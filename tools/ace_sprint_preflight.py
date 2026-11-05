"""Verify the exact E1.4n worker mount, resource limits and frozen bank."""

import json
import subprocess

from e13.isolation import _sandbox_python
from e14.e14g_isolation import validate_boundary
from e14.e14n_run import frozen, stage

PROBE = """
import importlib.util, json, pathlib, resource, sys
sys.path.insert(0, '/solver')
checks = {
    'private_shadow_absent': not pathlib.Path('/etc/shadow').exists(),
    'proc_host_absent': not pathlib.Path('/proc/1/root').exists(),
    'actual_worker_importable': importlib.util.find_spec('e14.e14n_worker') is not None,
    'evaluator_import_denied': importlib.util.find_spec('e14.e14n_run') is None,
}
print(json.dumps({'checks': checks, 'cpu_limit': list(resource.getrlimit(resource.RLIMIT_CPU)),
                  'memory_limit': list(resource.getrlimit(resource.RLIMIT_AS))}))
"""


def check():
    _, digest, lock = frozen()
    boundary = validate_boundary()
    with stage() as root:
        raw, _ = _sandbox_python(["-c", PROBE], solver=root)
    actual = json.loads(raw)
    if not all(actual["checks"].values()) or actual["cpu_limit"] != [1, 1] or actual["memory_limit"] != [128*1024**2]*2:
        raise RuntimeError("worker preflight or resource limit mismatch")
    version = subprocess.run([boundary["binary"], "--version"], check=True, text=True,
                             capture_output=True, timeout=5).stdout.strip()
    return {"status": "COMPLETE", "bubblewrap_version": version, "boundary": boundary,
            "worker_mount_and_limits": actual, "bank_sha256": digest, "frozen_sha256_objects": len(lock["sha256"])}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
