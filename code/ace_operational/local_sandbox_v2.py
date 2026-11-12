"""OMEGA-05 v2 — sandbox backend for hosts without bubblewrap.

Phase 1's `LocalPythonSandbox` mandated bwrap and returned
BLOCKED_ENVIRONMENT where the binary was absent. The Phase 2 isolation
probe (Addendum 18) proved every capability that design needs exists
on this host through other paths; this backend uses them:

* **user + mount + pid + net namespaces** via `unshare` (the payload
  is PID 1 of a private namespace tree);
* **a pivot_root rootfs** assembled from read-only bind mounts —
  system Python, its stdlib and platform libs, the candidate tree at
  /candidate and the evaluator tree at /evaluator, a bounded tmpfs at
  /tmp, and four device files. Host paths simply do not exist inside;
* **a seccomp filter installed through the seccomp(2) syscall** — the
  prctl path is intercepted by this host's outer sandbox profile
  (probe round 2/3 evidence). The filter is the same denylist as v1
  (fork/clone/socket/mount/ptrace/... return EPERM), built as classic
  BPF from a syscall table verified against the host headers;
* host-side rlimits, output budgets and process-group kill discipline
  identical to v1.

The probe and runner programs are imported unchanged from
`local_sandbox` — v2 must pass the *same* OMEGA-05 acceptance checks,
not a weaker set invented for it. Fail-closed like v1: any setup
failure yields BLOCKED_ENVIRONMENT, never a host-execution fallback.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import resource
import selectors
import secrets
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any

from ace_operational.local_sandbox import _PROBE, _RUNNER, _tree_digest

# x86_64 syscall numbers, verified against this host's unistd_64.h.
BLOCKED_SYSCALLS = {
    "fork": 57, "vfork": 58, "clone": 56, "clone3": 435,
    "unshare": 272, "setns": 308, "socket": 41, "socketpair": 53,
    "connect": 42, "bind": 49, "listen": 50, "accept": 43, "accept4": 288,
    "ptrace": 101, "bpf": 321, "perf_event_open": 298, "mount": 165,
    "umount2": 166, "pivot_root": 155, "open_by_handle_at": 304,
    "name_to_handle_at": 303, "process_vm_readv": 310,
    "process_vm_writev": 311, "keyctl": 250, "add_key": 248,
    "request_key": 249, "userfaultfd": 323,
}

_INIT = r'''
import ctypes, json, os, sys
cfg = json.loads(sys.argv[1])
libc = ctypes.CDLL("libc.so.6", use_errno=True)
MS_BIND, MS_REC, MS_PRIVATE, MS_REMOUNT = 4096, 16384, 1 << 18, 32
MS_RDONLY, MS_NOSUID, MS_NODEV = 1, 2, 4

def mount(src, dst, fstype, flags, data=None):
    r = libc.mount(src.encode() if src else None, dst.encode(),
                   fstype.encode() if fstype else None, flags,
                   data.encode() if data else None)
    if r != 0:
        raise OSError(ctypes.get_errno(), "mount failed", (src, dst))

mount(None, "/", None, MS_REC | MS_PRIVATE)
st = cfg["staging"]
mount(st, st, None, MS_BIND)

def bind_ro(src, dst):
    mount(src, dst, None, MS_BIND | MS_REC)
    mount(None, dst, None, MS_REMOUNT | MS_BIND | MS_RDONLY | MS_NOSUID | MS_NODEV)

bind_ro(cfg["python"], st + cfg["python"])
bind_ro(cfg["stdlib"], st + cfg["stdlib"])
bind_ro(cfg["libdir"], st + cfg["libdir"])
if cfg.get("lib64dir"):
    bind_ro(cfg["lib64dir"], st + cfg["lib64dir"])
bind_ro(cfg["candidate"], st + "/candidate")
bind_ro(cfg["evaluator"], st + "/evaluator")
mount("tmpfs", st + "/tmp", "tmpfs", MS_NOSUID | MS_NODEV, "size=16777216")
for dev in ("null", "zero", "full", "urandom"):
    mount("/dev/" + dev, st + "/dev/" + dev, None, MS_BIND)
os.chdir(st)
if libc.pivot_root(b".", b"oldroot") != 0:
    raise OSError(ctypes.get_errno(), "pivot_root failed")
os.chdir("/")
libc.umount2(b"/oldroot", 2)  # MNT_DETACH
mount(None, "/", None, MS_REMOUNT | MS_BIND | MS_RDONLY | MS_NOSUID | MS_NODEV)
os.chdir("/candidate")
os.environ.clear()
os.environ.update({"HOME": "/tmp", "PATH": "/usr/bin", "LANG": "C.UTF-8",
                   "LC_ALL": "C.UTF-8", "PWD": "/candidate"})

# seccomp via the seccomp(2) syscall: default ALLOW, denylist -> EPERM,
# wrong arch -> KILL_PROCESS. (prctl PR_SET_SECCOMP is intercepted by
# the outer sandbox profile on this host; syscall 317 is not.)
# Layout: 0 ld arch; 1 jeq arch (jt -> 3, jf -> 2 KILL); 2 KILL;
# 3 ld nr; 4..4+n-1 jeq checks (jt -> ERRNO at 4+n+1, jf -> next);
# 4+n ALLOW; 4+n+1 ERRNO.
import struct
blocked = sorted(__BLOCKED__)
prog = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x80000000),
        (0x20, 0, 0, 0)]
n = len(blocked)
for i, nr in enumerate(blocked):
    prog.append((0x15, n - i, 0, nr))
prog.append((0x06, 0, 0, 0x7FFF0000))        # ALLOW
prog.append((0x06, 0, 0, 0x00050000 | 1))    # ERRNO | EPERM
bpf = b"".join(struct.pack("HBBI", *ins) for ins in prog)
class Fprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]
buf = ctypes.create_string_buffer(bpf)
fp = Fprog(len(prog), ctypes.cast(buf, ctypes.c_void_p))
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "no_new_privs failed")
if libc.syscall(317, 1, 0, ctypes.byref(fp)) != 0:
    raise OSError(ctypes.get_errno(), "seccomp install failed")
os.execv(cfg["python"], [cfg["python"], "-I", "-S", "-B", "-c", cfg["program"]])
'''


class LocalPythonSandboxV2:
    """Fail-closed sandboxed unittest execution without bubblewrap."""

    def __init__(self, *, python_binary: str = "/usr/bin/python3",
                 memory_mb: int = 512):
        if not 128 <= memory_mb <= 2048:
            raise ValueError("memory_mb must be in [128, 2048]")
        self.python_binary = str(Path(python_binary).resolve())
        self.memory_mb = memory_mb

    # -- host-side preparation -------------------------------------------
    def _paths(self) -> dict[str, str]:
        python = Path(self.python_binary)
        if python.parent != Path("/usr/bin") or not python.is_file():
            raise RuntimeError("supported system Python /usr/bin/python3 required")
        probe = subprocess.run(
            [str(python), "-I", "-S", "-c",
             "import sysconfig;print(sysconfig.get_path('stdlib'))"],
            check=True, capture_output=True, text=True, timeout=5,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        stdlib = Path(probe.stdout.strip())
        if stdlib.parent != Path("/usr/lib") or not stdlib.name.startswith("python3."):
            raise RuntimeError("unsupported system stdlib path")
        libdir = Path("/usr/lib") / ("aarch64-linux-gnu"
                                     if os.uname().machine == "aarch64"
                                     else "x86_64-linux-gnu")
        if not libdir.is_dir():
            raise RuntimeError("supported platform libraries unavailable")
        return {"python": str(python), "stdlib": str(stdlib),
                "libdir": str(libdir),
                "lib64dir": "/usr/lib64" if Path("/usr/lib64").is_dir() else ""}

    def _stage_root(self) -> Path:
        staging = Path(tempfile.mkdtemp(prefix="ace-sbx2-"))
        for sub in ("usr/bin", "usr/lib", "candidate", "evaluator", "dev",
                    "tmp", "oldroot"):
            (staging / sub).mkdir(parents=True, exist_ok=True)
        paths = self._paths()
        (staging / "usr/lib" / Path(paths["stdlib"]).name).mkdir()
        (staging / "usr/lib" / Path(paths["libdir"]).name).mkdir()
        (staging / "usr/bin" / Path(paths["python"]).name).touch()
        if paths["lib64dir"]:
            (staging / "usr/lib64").mkdir()
            (staging / "lib64").symlink_to("usr/lib64")
        (staging / "lib").symlink_to("usr/lib")
        for dev in ("null", "zero", "full", "urandom"):
            (staging / "dev" / dev).touch()
        return staging

    # -- execution ---------------------------------------------------------
    def _execute(self, candidate: Path, evaluator: Path, program: str,
                 timeout: float, output_limit: int) -> dict[str, Any]:
        if not shutil.which("unshare"):
            raise RuntimeError("unshare unavailable")
        paths = self._paths()
        staging = self._stage_root()
        started = time.monotonic()
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        output: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        stopped = ""
        cfg = {"staging": str(staging), "program": program,
               "candidate": str(candidate), "evaluator": str(evaluator),
               **paths}
        init = _INIT.replace("__BLOCKED__", repr(sorted(BLOCKED_SYSCALLS.values())))
        command = ["unshare", "-Urmpfn", "--kill-child",
                   paths["python"], "-I", "-S", "-c", init, json.dumps(cfg)]

        def limits() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_mb * 1024**2,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU,
                               (math.ceil(timeout), math.ceil(timeout) + 1))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2,) * 2)
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

        proc = None
        try:
            proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, start_new_session=True,
                preexec_fn=limits, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
                    selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
                    while selector.get_map():
                        if time.monotonic() - started > timeout:
                            stopped = "WALL_TIME_BUDGET"
                            break
                        for key, _ in selector.select(timeout=0.05):
                            chunk = os.read(key.fd, 16384)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            remaining = output_limit - sum(
                                len(v) for v in output.values())
                            output[key.data].extend(chunk[:remaining])
                            if len(chunk) > remaining:
                                stopped = "OUTPUT_BUDGET"
                                break
                        if stopped:
                            break
            finally:
                if not stopped:
                    try:
                        proc.wait(timeout=max(0.1, timeout - (time.monotonic() - started)))
                    except subprocess.TimeoutExpired:
                        stopped = "WALL_TIME_BUDGET"
                if stopped:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return {
            "returncode": proc.returncode if proc else -1,
            "stdout": output["stdout"].decode("utf-8", errors="replace"),
            "stderr": output["stderr"].decode("utf-8", errors="replace"),
            "stopped_reason": stopped,
            "duration_seconds": round(time.monotonic() - started, 6),
            "resources": {
                "cpu_seconds": round(usage_after.ru_utime + usage_after.ru_stime
                                     - usage_before.ru_utime - usage_before.ru_stime, 6),
                "max_rss_kib_children_high_water": usage_after.ru_maxrss,
                "rss_scope": "cumulative_child_high_water_in_this_host_process",
                "address_space_limit_mb": self.memory_mb,
                "output_limit_bytes": output_limit,
            },
        }

    # -- public contract (mirrors v1) --------------------------------------
    def run_tests(self, candidate_dir: Path, evaluator_dir: Path, *,
                  timeout_seconds: float = 30,
                  output_limit_bytes: int = 262144) -> dict[str, Any]:
        if not 0.2 <= timeout_seconds <= 120 or not 1024 <= output_limit_bytes <= 1_048_576:
            raise ValueError("invalid execution budget")
        receipt: dict[str, Any] = {
            "schema": "ace.local_sandbox.v2", "status": "BLOCKED_ENVIRONMENT",
            "passed": False,
            "isolation": "userns+pivot_root+seccomp(2)",
            "independent_scientific_confirmation": False,
            "supported_workload": "single_process_stdlib_python_unittest",
        }
        try:
            candidate = Path(candidate_dir).resolve(strict=True)
            evaluator = Path(evaluator_dir).resolve(strict=True)
            if not candidate.is_dir() or not evaluator.is_dir() or candidate == evaluator:
                raise ValueError("distinct candidate and evaluator directories required")
            if candidate in evaluator.parents or evaluator in candidate.parents:
                raise ValueError("candidate and evaluator custody trees must be separate")
            receipt["candidate_digest"] = _tree_digest(candidate)
            receipt["evaluator_digest"] = _tree_digest(evaluator)
            probe = self._execute(candidate, evaluator, _PROBE, 5, 8192)
            receipt["isolation_probe"] = probe
            if probe["returncode"] != 0 or probe["stopped_reason"]:
                receipt["error"] = "ISOLATION_PROBE_FAILED"
                return receipt
            checks = json.loads(probe["stdout"])
            if not checks or not all(value is True for value in checks.values()):
                receipt["error"] = "ISOLATION_PROBE_CHECK_FAILED"
                return receipt
            receipt["isolation_checks"] = checks
            nonce = secrets.token_hex(16)
            run = self._execute(candidate, evaluator,
                                _RUNNER.replace("__ACE_RECEIPT_NONCE__", nonce),
                                timeout_seconds, output_limit_bytes)
            receipt.update(run)
            completion_prefix = "ACE_SANDBOX_COMPLETION_" + nonce + "="
            completion_lines = [line[len(completion_prefix):]
                                for line in run["stdout"].splitlines()
                                if line.startswith(completion_prefix)]
            try:
                completion = json.loads(completion_lines[0]) if len(completion_lines) == 1 else {}
            except (TypeError, ValueError):
                completion = {}
            completed = (isinstance(completion, dict)
                         and type(completion.get("tests_run")) is int
                         and completion["tests_run"] > 0
                         and completion.get("successful") is True
                         and completion.get("failures") == 0
                         and completion.get("errors") == 0)
            receipt["runner_completion"] = completion
            receipt["completion_guard"] = \
                "per_run_nonce_and_nonzero_test_count; not_adversarial_authentication"
            unchanged = (_tree_digest(candidate) == receipt["candidate_digest"]
                         and _tree_digest(evaluator) == receipt["evaluator_digest"])
            receipt["input_digests_unchanged"] = unchanged
            receipt["passed"] = (run["returncode"] == 0 and not run["stopped_reason"]
                                 and unchanged and completed)
            if run["returncode"] == 0 and not completed:
                receipt["error"] = "RUNNER_COMPLETION_NOT_OBSERVED"
            receipt["status"] = ("PASS" if receipt["passed"] else
                                 "STOPPED_BUDGET" if run["stopped_reason"] else "FAIL")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            receipt["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        return receipt
