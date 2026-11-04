"""Evaluator adapter for fresh native Bubblewrap workers."""

import hashlib
import os
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, read_json
from e13.isolation import READY_MARKER, _sandbox_python

HERE = Path(__file__).resolve().parent
BWRAP = Path("/usr/bin/bwrap")


@contextmanager
def worker_mount():
    with tempfile.TemporaryDirectory(prefix="ace-e14g-worker-") as temp:
        root = Path(temp)
        (root / "e13").mkdir()
        (root / "e14").mkdir()
        for package, names in (("e13", ("__init__.py", "contract.py")),
                               ("e14", ("__init__.py", "e14g_worker.py"))):
            for name in names:
                shutil.copyfile(HERE.parent / package / name, root / package / name)
        yield root


def invoke(root, family, operation, demos, inputs, *, length=5):
    if length not in (5, 6):
        raise ValueError("invalid grammar length")
    script = ("import sys; sys.path.insert(0, '/solver'); from e14.e14g_worker import main; "
              f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main(int(sys.argv[1]))")
    packet = canonical_json({"family": family, "operation": operation, "demos": demos, "inputs": inputs})
    output, wall = _sandbox_python(["-c", script, str(length)], packet, solver=root)
    row = read_json(output, 16_384)
    if (type(row) is not dict or type(row.get("cpu_us")) is not int
            or not 0 <= row["cpu_us"] <= 1_000_000 or not 0 <= wall <= 3_000_000
            or type(row.get("rss_kib")) is not int or not 0 < row["rss_kib"] <= 128 * 1024):
        raise ValueError("sandbox returned invalid resource accounting")
    return {**row, "wall_us": wall}


def validate_boundary():
    binary = BWRAP.read_bytes()
    if not binary.startswith(b"\x7fELF"):
        raise RuntimeError("requires a native Bubblewrap executable")
    script = """
import importlib.util, os, socket, sys
from pathlib import Path
sys.path.insert(0, '/solver')
checks = {}
try:
    Path(sys.argv[1]).read_bytes()
except OSError:
    checks['private_file_denied'] = True
else:
    checks['private_file_denied'] = False
checks['evaluator_module_absent'] = importlib.util.find_spec('e14.e14g_bank') is None
checks['credential_env_absent'] = 'ACE_E14G_CANARY' not in os.environ
try:
    Path('/solver/change').write_text('write')
except OSError:
    checks['worker_mount_read_only'] = True
else:
    checks['worker_mount_read_only'] = False
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[2])), timeout=0.25):
        checks['host_loopback_denied'] = False
except OSError:
    checks['host_loopback_denied'] = True
import json
print(json.dumps(checks))
"""
    with (tempfile.TemporaryDirectory(prefix="ace-e14g-private-") as private,
          socket.socket() as listener, worker_mount() as root):
        path = Path(private) / "labels.json"
        path.write_text("private evaluator label canary")
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        # Ensure the network target is a working host endpoint.
        with socket.create_connection(listener.getsockname(), timeout=1):
            connection, _ = listener.accept()
            connection.close()
        env_name = "ACE_E14G_CANARY"
        previous = os.environ.get(env_name)
        os.environ[env_name] = "public-test-value"
        try:
            out, _ = _sandbox_python(["-c", script, str(path), str(listener.getsockname()[1])],
                                     solver=root)
        finally:
            if previous is None:
                os.environ.pop(env_name)
            else:
                os.environ[env_name] = previous
    checks = read_json(out, 4_096)
    expected = {"private_file_denied", "evaluator_module_absent", "credential_env_absent",
                "worker_mount_read_only", "host_loopback_denied"}
    if checks.keys() != expected or any(checks[name] is not True for name in expected):
        raise RuntimeError("evaluator isolation canary failed")
    return {"binary": str(BWRAP), "sha256": hashlib.sha256(binary).hexdigest(),
            "native_elf": True, "checks": checks}
