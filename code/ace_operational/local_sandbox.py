"""Least-privilege local Python test runner for experimental code candidates.

This is a Linux/bubblewrap adapter, not a substitute for evaluator custody.
Only the fixed unittest runner below is admitted: callers cannot supply commands.
Candidate and evaluator trees are read-only; the host constructs the receipt.
Python candidates can still interfere with tests in the same interpreter, so a
passing run is engineering evidence, never independent scientific confirmation.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import errno
import hashlib
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


_RUNNER = r'''
import json, sys, unittest
sys.path[:0] = ["/candidate", "/evaluator"]
suite = unittest.TestLoader().discover("/evaluator", pattern="test_*.py")
count = suite.countTestCases()
if count == 0:
    print("ACE_SANDBOX_NO_TESTS", file=sys.stderr)
    raise SystemExit(2)
result = unittest.TextTestRunner(verbosity=2).run(suite)
print("ACE_SANDBOX_COMPLETION_" + "__ACE_RECEIPT_NONCE__" + "=" + json.dumps({
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "successful": result.wasSuccessful(),
}), flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
'''

_PROBE = r'''
import errno, json, os, pathlib, socket
checks = {}
checks["host_workspace_hidden"] = not pathlib.Path("/workspace").exists()
checks["host_home_hidden"] = not pathlib.Path("/home").exists()
checks["host_root_credentials_hidden"] = not pathlib.Path("/root").exists()
checks["environment_scrubbed"] = (set(os.environ) <= {"HOME", "PATH", "LANG", "LC_ALL", "PWD"}
                                     and os.environ.get("PWD") == "/candidate")
checks["private_pid_namespace"] = os.getppid() <= 2
checks["no_network_interfaces"] = sorted(pathlib.Path("/sys/class/net").glob("*")) == []
try:
    socket.socket()
    checks["sockets_denied"] = False
except OSError as exc:
    checks["sockets_denied"] = exc.errno == errno.EPERM
try:
    child = os.fork()
except OSError as exc:
    checks["process_creation_denied"] = exc.errno == errno.EPERM
else:
    if child == 0:
        os._exit(71)
    os.waitpid(child, 0)
    checks["process_creation_denied"] = False
for name in ("candidate", "evaluator"):
    try:
        pathlib.Path("/" + name + "/.ace-write-probe").write_text("denied")
        checks[name + "_readonly"] = False
    except OSError as exc:
        checks[name + "_readonly"] = exc.errno in (errno.EROFS, errno.EACCES)
print(json.dumps(checks, sort_keys=True))
raise SystemExit(0 if all(checks.values()) else 72)
'''


def _tree_digest(directory: Path) -> str:
    """Bounded admission: no symlinks, hardlinks, devices or large input trees."""
    digest = hashlib.sha256()
    count, total = 0, 0
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink input rejected")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("nonregular or hardlinked input rejected")
        count += 1
        size = path.stat().st_size
        total += size
        if count > 1000 or size > 1_048_576 or total > 16_777_216:
            raise ValueError("sandbox input tree exceeds budget")
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class LocalPythonSandbox:
    """Fail-closed Linux test execution with a mandatory runtime isolation probe.

    Run this adapter in an execution context allowed to create namespaces. It
    never attempts sudo, changes host policy, or falls back to host execution.
    The admitted workload is single-process, stdlib-only Python unittest.
    """

    def __init__(self, *, python_binary: str = "/usr/bin/python3", memory_mb: int = 512):
        if not 128 <= memory_mb <= 2048:
            raise ValueError("memory_mb must be in [128, 2048]")
        self.python_binary = str(Path(python_binary).resolve())
        self.memory_mb = memory_mb

    @staticmethod
    def _seccomp_file() -> Any:
        library = ctypes.util.find_library("seccomp")
        if not library:
            raise RuntimeError("libseccomp unavailable")
        lib = ctypes.CDLL(library, use_errno=True)
        lib.seccomp_init.argtypes = [ctypes.c_uint32]
        lib.seccomp_init.restype = ctypes.c_void_p
        lib.seccomp_release.argtypes = [ctypes.c_void_p]
        lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
        lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
        lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
        ctx = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
        if not ctx:
            raise RuntimeError("seccomp_init failed")
        output = tempfile.TemporaryFile()
        try:
            for name in (
                "fork", "vfork", "clone", "clone3", "unshare", "setns",
                "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
                "ptrace", "bpf", "perf_event_open", "mount", "umount2", "pivot_root",
                "open_by_handle_at", "name_to_handle_at", "process_vm_readv", "process_vm_writev",
                "keyctl", "add_key", "request_key", "userfaultfd",
            ):
                number = lib.seccomp_syscall_resolve_name(name.encode("ascii"))
                if number < 0 or lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, number, 0) != 0:
                    raise RuntimeError("seccomp rule unavailable: " + name)
            if lib.seccomp_export_bpf(ctx, output.fileno()) != 0:
                raise RuntimeError("seccomp_export_bpf failed")
            output.seek(0)
            return output
        except BaseException:
            output.close()
            raise
        finally:
            lib.seccomp_release(ctx)

    def _command(self, candidate: Path, evaluator: Path, program: str, seccomp_fd: int) -> list[str]:
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("bubblewrap unavailable")
        python = Path(self.python_binary)
        if python.parent != Path("/usr/bin") or not python.is_file():
            raise RuntimeError("supported system Python /usr/bin/python3 required")
        # Resolve runtime metadata with the trusted installed system interpreter.
        probe = subprocess.run(
            [str(python), "-I", "-S", "-c", "import sysconfig;print(sysconfig.get_path('stdlib'))"],
            check=True, capture_output=True, text=True, timeout=5,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        stdlib = Path(probe.stdout.strip())
        if stdlib.parent != Path("/usr/lib") or not stdlib.name.startswith("python3."):
            raise RuntimeError("unsupported system stdlib path")
        libdir = Path("/usr/lib") / ("aarch64-linux-gnu" if os.uname().machine == "aarch64" else "x86_64-linux-gnu")
        if not libdir.is_dir():
            raise RuntimeError("supported platform libraries unavailable")
        command = [
            bwrap, "--unshare-all", "--unshare-user", "--disable-userns",
            "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv",
            "--ro-bind", str(python), str(python),
            "--ro-bind", str(stdlib), str(stdlib),
            "--ro-bind", str(libdir), str(libdir),
            "--symlink", "usr/lib", "/lib",
        ]
        if Path("/usr/lib64").is_dir():
            command += ["--ro-bind", "/usr/lib64", "/usr/lib64", "--symlink", "usr/lib64", "/lib64"]
        command += [
            "--ro-bind", str(candidate), "/candidate", "--ro-bind", str(evaluator), "/evaluator",
            "--proc", "/proc", "--dev", "/dev", "--size", "16777216", "--tmpfs", "/tmp",
            "--remount-ro", "/proc", "--remount-ro", "/dev", "--remount-ro", "/",
            "--setenv", "HOME", "/tmp", "--setenv", "PATH", "/usr/bin",
            "--setenv", "LANG", "C.UTF-8", "--setenv", "LC_ALL", "C.UTF-8",
            "--chdir", "/candidate", "--seccomp", str(seccomp_fd),
            "--", str(python), "-I", "-S", "-B", "-c", program,
        ]
        return command

    def _execute(self, candidate: Path, evaluator: Path, program: str, timeout: float, output_limit: int) -> dict[str, Any]:
        started = time.monotonic()
        usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        output: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        stopped = ""

        def limits() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_mb * 1024**2,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(timeout), math.ceil(timeout) + 1))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2,) * 2)
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

        with self._seccomp_file() as seccomp:
            command = self._command(candidate, evaluator, program, seccomp.fileno())
            proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, pass_fds=(seccomp.fileno(),),
                start_new_session=True, preexec_fn=limits,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            )
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
                            remaining = output_limit - sum(len(value) for value in output.values())
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
        usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return {
            "returncode": proc.returncode,
            "stdout": output["stdout"].decode("utf-8", errors="replace"),
            "stderr": output["stderr"].decode("utf-8", errors="replace"),
            "stopped_reason": stopped,
            "duration_seconds": round(time.monotonic() - started, 6),
            "resources": {
                "cpu_seconds": round(usage_after.ru_utime + usage_after.ru_stime - usage_before.ru_utime - usage_before.ru_stime, 6),
                "max_rss_kib_children_high_water": usage_after.ru_maxrss,
                "rss_scope": "cumulative_child_high_water_in_this_host_process",
                "address_space_limit_mb": self.memory_mb,
                "output_limit_bytes": output_limit,
            },
        }

    def run_tests(
        self,
        candidate_dir: Path,
        evaluator_dir: Path,
        *,
        timeout_seconds: float = 30,
        output_limit_bytes: int = 262144,
    ) -> dict[str, Any]:
        if not 0.2 <= timeout_seconds <= 120 or not 1024 <= output_limit_bytes <= 1_048_576:
            raise ValueError("invalid execution budget")
        receipt: dict[str, Any] = {
            "schema": "ace.local_sandbox.v1", "status": "BLOCKED_ENVIRONMENT", "passed": False,
            "isolation": "bubblewrap+seccomp", "independent_scientific_confirmation": False,
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
            run = self._execute(candidate, evaluator, _RUNNER.replace("__ACE_RECEIPT_NONCE__", nonce),
                                timeout_seconds, output_limit_bytes)
            receipt.update(run)
            completion_prefix = "ACE_SANDBOX_COMPLETION_" + nonce + "="
            completion_lines = [line[len(completion_prefix):] for line in run["stdout"].splitlines()
                                if line.startswith(completion_prefix)]
            try:
                completion = json.loads(completion_lines[0]) if len(completion_lines) == 1 else {}
            except (TypeError, ValueError):
                completion = {}
            completed = (isinstance(completion, dict) and type(completion.get("tests_run")) is int
                         and completion["tests_run"] > 0 and completion.get("successful") is True
                         and completion.get("failures") == 0 and completion.get("errors") == 0)
            receipt["runner_completion"] = completion
            receipt["completion_guard"] = "per_run_nonce_and_nonzero_test_count; not_adversarial_authentication"
            unchanged = (_tree_digest(candidate) == receipt["candidate_digest"] and
                         _tree_digest(evaluator) == receipt["evaluator_digest"])
            receipt["input_digests_unchanged"] = unchanged
            receipt["passed"] = (run["returncode"] == 0 and not run["stopped_reason"] and unchanged and completed)
            if run["returncode"] == 0 and not completed:
                receipt["error"] = "RUNNER_COMPLETION_NOT_OBSERVED"
            receipt["status"] = "PASS" if receipt["passed"] else "STOPPED_BUDGET" if run["stopped_reason"] else "FAIL"
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            receipt["error"] = type(exc).__name__ + ": " + str(exc)[:500]
        return receipt
