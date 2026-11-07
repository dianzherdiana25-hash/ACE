"""Isolated staging directory and subprocess test/perturbation execution sandbox.

Safety invariants:
- Never modifies or imports repository modules under test in the parent process.
- Writes staged candidate code and harness scripts exclusively inside a fresh
  `tempfile.TemporaryDirectory` using `O_CREAT | O_EXCL | O_NOFOLLOW` mode `0600`.
- Executes child Python with `-I -B`, scrubbed environment variables, `RLIMIT_CPU`,
  `RLIMIT_CORE = 0`, separate process session, and enforced wall-clock timeout.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any

from .corpus import DevTestCase, PerturbationSpec

DEFAULT_TIMEOUT_SEC = 3.0
DEFAULT_CPU_LIMIT_SEC = 2
DEFAULT_MEM_LIMIT_BYTES = 512 * 1024 * 1024  # 512 MB
DEFAULT_FILE_LIMIT_BYTES = 512 * 1024  # 512 KB
DEFAULT_NOFILE_LIMIT = 32


class TrustBoundary:
    TRUSTED_FIXTURE = "TRUSTED_FIXTURE"
    CLOSED_AST_MUTATION = "CLOSED_AST_MUTATION"
    UNTRUSTED_CANDIDATE = "UNTRUSTED_CANDIDATE"


FORBIDDEN_MODULES = frozenset({
    "os", "subprocess", "socket", "urllib", "requests", "http",
    "shutil", "ctypes", "posix", "nt", "importlib", "multiprocessing",
    "threading", "signal", "pty", "commands", "builtins", "__builtin__",
    "asyncio", "aiohttp", "ftplib", "poplib", "imaplib", "smtplib",
    "ssl", "xmlrpc", "webbrowser", "pickle", "shelve", "tempfile",
})

FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "compile", "open", "input", "globals", "locals",
    "vars", "breakpoint", "__import__",
})

FORBIDDEN_ATTRS = frozenset({
    "__subclasses__", "__bases__", "__globals__", "__builtins__",
    "__code__", "__closure__", "__func__", "__self__",
})


def is_os_sandbox_available() -> tuple[bool, str]:
    """Detect whether genuine OS-level containment is active and functional."""
    env_override = os.environ.get("ACE_OS_SANDBOX_OVERRIDE")
    if env_override is not None:
        return (env_override == "1", "ENVIRONMENT_OVERRIDE")

    bwrap_path = shutil.which("bwrap")
    if bwrap_path:
        try:
            r = subprocess.run(
                [bwrap_path, "--unshare-all", "--ro-bind", "/", "/", "--tmpfs", "/tmp", "true"],
                capture_output=True,
                timeout=1.5,
            )
            if r.returncode == 0:
                return True, "bwrap"
        except Exception:
            pass

    unshare_path = shutil.which("unshare")
    if unshare_path:
        try:
            r = subprocess.run(
                [unshare_path, "--user", "--net", "true"],
                capture_output=True,
                timeout=1.5,
            )
            if r.returncode == 0:
                return True, "unshare_user_net"
        except Exception:
            pass

    return False, "NO_OS_SANDBOX"


def audit_candidate_ast(source_code: str) -> tuple[bool, str | None]:
    """Perform static deny-by-default AST security audit on candidate source."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return False, f"SyntaxError:{type(exc).__name__}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base_mod = alias.name.split(".")[0]
                if base_mod in FORBIDDEN_MODULES:
                    return False, f"ForbiddenModuleImport:{alias.name}"
        elif isinstance(node, ast.ImportFrom):
            base_mod = (node.module or "").split(".")[0]
            if base_mod in FORBIDDEN_MODULES:
                return False, f"ForbiddenFromModuleImport:{node.module}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return False, f"ForbiddenCall:{node.func.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                return False, f"ForbiddenAttribute:{node.attr}"

    return True, None


def _write_nofollow(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        data = content.encode("utf-8")
        view = memoryview(data)
        written = 0
        while written < len(data):
            written += os.write(fd, view[written:])
    finally:
        os.close(fd)


def _scrubbed_env() -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


def _make_preexec(
    cpu_limit_sec: int,
    mem_limit_bytes: int = DEFAULT_MEM_LIMIT_BYTES,
    fsize_limit_bytes: int = DEFAULT_FILE_LIMIT_BYTES,
    nofile_limit: int = DEFAULT_NOFILE_LIMIT,
):
    def _apply_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_sec, cpu_limit_sec))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if hasattr(resource, "RLIMIT_AS"):
            try:
                resource.setrlimit(resource.RLIMIT_AS, (mem_limit_bytes, mem_limit_bytes))
            except (ValueError, OSError):
                pass
        if hasattr(resource, "RLIMIT_FSIZE"):
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_limit_bytes, fsize_limit_bytes))
            except (ValueError, OSError):
                pass
        if hasattr(resource, "RLIMIT_NOFILE"):
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (nofile_limit, nofile_limit))
            except (ValueError, OSError):
                pass

    return _apply_limits


_DEV_HARNESS_TEMPLATE = """import ast
import copy
import json
import sys


def strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return set(a.keys()) == set(b.keys()) and all(
            type(k1) is type(k2) and strict_equal(a[k1], b[k1])
            for k1, k2 in zip(sorted(a.keys(), key=repr), sorted(b.keys(), key=repr))
        )
    return a == b


def has_aliased_mutable_elements(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return False
    mutable_ids = [id(item) for item in value if isinstance(item, (dict, list, set))]
    return len(mutable_ids) >= 2 and len(set(mutable_ids)) < len(mutable_ids)


def main():
    spec = ast.literal_eval(open("spec.repr", "r", encoding="utf-8").read())
    src = open("candidate_module.py", "r", encoding="utf-8").read()
    entrypoint = spec["entrypoint"]
    collect_trace = spec["collect_trace"]
    cases = spec["cases"]

    namespace = {"__name__": "candidate_module"}
    try:
        code_obj = compile(src, "candidate_module.py", "exec")
        exec(code_obj, namespace)
    except BaseException as exc:
        print(json.dumps({
            "compile_ok": False,
            "compile_error": type(exc).__name__,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(cases),
            "cases": [],
        }, sort_keys=True))
        return

    if entrypoint not in namespace or not callable(namespace[entrypoint]):
        print(json.dumps({
            "compile_ok": False,
            "compile_error": "MissingEntrypoint",
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(cases),
            "cases": [],
        }, sort_keys=True))
        return

    fn = namespace[entrypoint]
    results = []
    passed_count = 0

    for case in cases:
        executed_lines = set()
        exc_lineno = None

        def tracer(frame, event, arg):
            nonlocal exc_lineno
            if frame.f_code.co_filename == "candidate_module.py":
                if event == "line":
                    executed_lines.add(frame.f_lineno)
                elif event == "exception" and exc_lineno is None:
                    exc_lineno = frame.f_lineno
            return tracer

        mode = case["mode"]
        raw_args = case["args"]
        expected = case["expected"]
        expected_exc = case["expected_exc"]
        forbid_mutation = case["forbid_arg_mutation"]

        arg_mutated = False
        aliased_return = False
        sequence_second_failed = False
        exc_name = None
        passed = False

        if collect_trace:
            sys.settrace(tracer)
        try:
            if mode == "call":
                call_args = copy.deepcopy(raw_args)
                snapshot = copy.deepcopy(raw_args)
                actual = fn(*call_args)
                if collect_trace:
                    sys.settrace(None)
                if forbid_mutation and not strict_equal(call_args, snapshot):
                    arg_mutated = True
                if has_aliased_mutable_elements(actual):
                    aliased_return = True
                if expected_exc is None and not arg_mutated and strict_equal(actual, expected):
                    passed = True
            elif mode == "sequence":
                outputs = []
                first_ok = False
                for idx, step_args in enumerate(raw_args):
                    call_args = copy.deepcopy(step_args)
                    snapshot = copy.deepcopy(step_args)
                    out = fn(*call_args)
                    if forbid_mutation and not strict_equal(call_args, snapshot):
                        arg_mutated = True
                    outputs.append(out)
                    if idx == 0 and isinstance(expected, list) and len(expected) >= 1:
                        first_ok = strict_equal(out, expected[0]) and not arg_mutated
                if collect_trace:
                    sys.settrace(None)
                if expected_exc is None and not arg_mutated and strict_equal(outputs, expected):
                    passed = True
                elif first_ok:
                    sequence_second_failed = True
            else:
                raise ValueError("unknown test mode")
        except BaseException as exc:
            if collect_trace:
                sys.settrace(None)
            exc_name = type(exc).__name__
            if expected_exc is not None and exc_name == expected_exc:
                passed = True
        finally:
            if collect_trace:
                sys.settrace(None)

        if passed:
            passed_count += 1

        results.append({
            "name": case["name"],
            "passed": passed,
            "exception_type": exc_name,
            "exception_lineno": exc_lineno,
            "arg_mutated": arg_mutated,
            "aliased_return": aliased_return,
            "sequence_second_failed": sequence_second_failed,
            "executed_lines": sorted(executed_lines) if collect_trace else [],
        })

    print(json.dumps({
        "compile_ok": True,
        "compile_error": None,
        "all_passed": passed_count == len(cases),
        "passed_count": passed_count,
        "total_count": len(cases),
        "cases": results,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
"""


_PERTURBATION_HARNESS_TEMPLATE = """import ast
import copy
import json


def strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return set(a.keys()) == set(b.keys()) and all(
            type(k1) is type(k2) and strict_equal(a[k1], b[k1])
            for k1, k2 in zip(sorted(a.keys(), key=repr), sorted(b.keys(), key=repr))
        )
    return a == b


def is_non_empty_probe(args_tuple):
    if not args_tuple:
        return False
    first = args_tuple[0]
    if isinstance(first, (list, tuple, dict, str)):
        return len(first) > 0
    return True


def load_fn(src, entrypoint):
    ns = {"__name__": "candidate_module"}
    exec(compile(src, "candidate_module.py", "exec"), ns)
    return ns[entrypoint]


def main():
    spec = ast.literal_eval(open("perturb.repr", "r", encoding="utf-8").read())
    src = open("candidate_module.py", "r", encoding="utf-8").read()
    entrypoint = spec["entrypoint"]
    diverse_inputs = spec["diverse_inputs"]
    equivalence_pairs = spec["equivalence_pairs"]
    expect_variation = spec["expect_variation"]
    check_call_isolation = spec["check_call_isolation"]

    try:
        fn = load_fn(src, entrypoint)
    except BaseException as exc:
        print(json.dumps({
            "passed": False,
            "crash_free": False,
            "call_isolation_ok": False,
            "variation_ok": False,
            "equivalence_ok": False,
            "unique_non_empty_outputs": 0,
            "rejection_reasons": [f"compile_error:{type(exc).__name__}"],
        }, sort_keys=True))
        return

    crash_free = True
    call_isolation_ok = True
    equivalence_ok = True
    non_empty_outputs = []
    all_outputs = []
    reasons = []

    for args_tuple in diverse_inputs:
        call_args = copy.deepcopy(args_tuple)
        snapshot = copy.deepcopy(args_tuple)
        try:
            out = fn(*call_args)
        except BaseException as exc:
            crash_free = False
            reasons.append(f"diverse_crash:{type(exc).__name__}")
            break
        if check_call_isolation and not strict_equal(call_args, snapshot):
            call_isolation_ok = False
            reasons.append("caller_arg_mutated")
            break
        rendered = repr((type(out).__name__, out))
        all_outputs.append(rendered)
        if is_non_empty_probe(args_tuple):
            non_empty_outputs.append(rendered)

    if crash_free and check_call_isolation and len(diverse_inputs) >= 2:
        try:
            fresh_fn = load_fn(src, entrypoint)
            probe_second = copy.deepcopy(diverse_inputs[-1])
            fresh_out = fresh_fn(*probe_second)
            shared_fn = load_fn(src, entrypoint)
            _ = shared_fn(*copy.deepcopy(diverse_inputs[0]))
            reused_out = shared_fn(*copy.deepcopy(diverse_inputs[-1]))
            if not strict_equal(fresh_out, reused_out):
                call_isolation_ok = False
                reasons.append("cross_call_state_leak")
        except BaseException as exc:
            crash_free = False
            reasons.append(f"isolation_crash:{type(exc).__name__}")

    unique_pool = non_empty_outputs if len(non_empty_outputs) >= 2 else all_outputs
    unique_count = len(set(unique_pool))
    variation_ok = (not expect_variation) or (unique_count >= 2)
    if crash_free and not variation_ok:
        reasons.append("constant_output_collapse")

    if crash_free:
        for args_a, args_b in equivalence_pairs:
            try:
                fn_a = load_fn(src, entrypoint)
                fn_b = load_fn(src, entrypoint)
                ca = copy.deepcopy(args_a)
                cb = copy.deepcopy(args_b)
                sa = copy.deepcopy(args_a)
                sb = copy.deepcopy(args_b)
                out_a = fn_a(*ca)
                out_b = fn_b(*cb)
                if check_call_isolation and (not strict_equal(ca, sa) or not strict_equal(cb, sb)):
                    call_isolation_ok = False
                    reasons.append("equiv_caller_arg_mutated")
                    break
                if not strict_equal(out_a, out_b):
                    equivalence_ok = False
                    reasons.append("equivalence_pair_mismatch")
                    break
            except BaseException as exc:
                crash_free = False
                reasons.append(f"equiv_crash:{type(exc).__name__}")
                break

    passed = crash_free and call_isolation_ok and variation_ok and equivalence_ok
    print(json.dumps({
        "passed": passed,
        "crash_free": crash_free,
        "call_isolation_ok": call_isolation_ok,
        "variation_ok": variation_ok,
        "equivalence_ok": equivalence_ok,
        "unique_non_empty_outputs": unique_count,
        "rejection_reasons": sorted(set(reasons)),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
"""


def _execute_staged_python(
    files: dict[str, str],
    script_name: str,
    timeout_sec: float,
    cpu_limit_sec: int,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    with tempfile.TemporaryDirectory(prefix="ace_repair_stage_") as tmp_dir:
        stage_path = Path(tmp_dir)
        for filename, content in files.items():
            _write_nofollow(stage_path / filename, content)

        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", script_name],
            cwd=str(stage_path),
            env=_scrubbed_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=_make_preexec(cpu_limit_sec),
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            return True, None, "TimeoutExpired"

        if proc.returncode != 0:
            reason = f"SubprocessExit:{proc.returncode}"
            if proc.returncode < 0:
                reason = f"SubprocessSignal:{-proc.returncode}"
            return False, None, reason

        try:
            payload = json.loads(stdout.strip())
        except (ValueError, TypeError):
            return False, None, f"InvalidHarnessJSON:{stderr.strip()[:80]}"
        if not isinstance(payload, dict):
            return False, None, "HarnessPayloadNotDict"
        return False, payload, None


def run_dev_suite(
    source_code: str,
    entrypoint: str,
    test_cases: tuple[DevTestCase, ...] | list[DevTestCase],
    *,
    collect_trace: bool = False,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    cpu_limit_sec: int = DEFAULT_CPU_LIMIT_SEC,
    trust_level: str = TrustBoundary.CLOSED_AST_MUTATION,
) -> dict[str, Any]:
    """Execute `test_cases` against `source_code` inside an isolated temporary directory."""
    # 1. Enforce fail-closed BLOCKED_ENVIRONMENT for UNTRUSTED_CANDIDATE when real OS sandbox is absent
    if trust_level == TrustBoundary.UNTRUSTED_CANDIDATE:
        os_avail, os_mech = is_os_sandbox_available()
        if not os_avail:
            return {
                "status": "BLOCKED_ENVIRONMENT",
                "blocked_environment": True,
                "timed_out": False,
                "sandbox_error": f"BLOCKED_ENVIRONMENT: OS-level containment unavailable ({os_mech}) for untrusted candidate execution",
                "compile_ok": False,
                "compile_error": "BLOCKED_ENVIRONMENT",
                "all_passed": False,
                "passed_count": 0,
                "total_count": len(test_cases),
                "cases": [],
            }

    # 2. Deny-by-default static AST security audit
    ast_ok, ast_err = audit_candidate_ast(source_code)
    if not ast_ok:
        return {
            "status": "AST_DENY_BY_DEFAULT",
            "blocked_environment": False,
            "timed_out": False,
            "sandbox_error": f"AST_SECURITY_VIOLATION:{ast_err}",
            "compile_ok": False,
            "compile_error": f"AST_SECURITY_VIOLATION:{ast_err}",
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "cases": [],
        }

    spec_obj = {
        "entrypoint": entrypoint,
        "collect_trace": bool(collect_trace),
        "cases": [
            {
                "name": tc.name,
                "mode": tc.mode,
                "args": tc.args,
                "expected": tc.expected,
                "expected_exc": tc.expected_exc,
                "forbid_arg_mutation": tc.forbid_arg_mutation,
            }
            for tc in test_cases
        ],
    }
    timed_out, payload, err = _execute_staged_python(
        {
            "candidate_module.py": source_code,
            "spec.repr": repr(spec_obj),
            "harness.py": _DEV_HARNESS_TEMPLATE,
        },
        "harness.py",
        timeout_sec=timeout_sec,
        cpu_limit_sec=cpu_limit_sec,
    )
    if timed_out or payload is None:
        return {
            "timed_out": timed_out,
            "sandbox_error": err,
            "compile_ok": False,
            "compile_error": err,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "cases": [],
        }
    return {
        "timed_out": False,
        "sandbox_error": None,
        **payload,
    }


def run_perturbation_suite(
    source_code: str,
    entrypoint: str,
    perturbation_spec: PerturbationSpec,
    *,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    cpu_limit_sec: int = DEFAULT_CPU_LIMIT_SEC,
    trust_level: str = TrustBoundary.CLOSED_AST_MUTATION,
) -> dict[str, Any]:
    """Execute unlabeled behavioral consistency checks inside an isolated child process."""
    if trust_level == TrustBoundary.UNTRUSTED_CANDIDATE:
        os_avail, os_mech = is_os_sandbox_available()
        if not os_avail:
            return {
                "status": "BLOCKED_ENVIRONMENT",
                "blocked_environment": True,
                "timed_out": False,
                "passed": False,
                "crash_free": False,
                "call_isolation_ok": False,
                "variation_ok": False,
                "equivalence_ok": False,
                "unique_non_empty_outputs": 0,
                "rejection_reasons": ["BLOCKED_ENVIRONMENT: OS-level containment unavailable"],
            }

    ast_ok, ast_err = audit_candidate_ast(source_code)
    if not ast_ok:
        return {
            "status": "AST_DENY_BY_DEFAULT",
            "blocked_environment": False,
            "timed_out": False,
            "passed": False,
            "crash_free": False,
            "call_isolation_ok": False,
            "variation_ok": False,
            "equivalence_ok": False,
            "unique_non_empty_outputs": 0,
            "rejection_reasons": [f"AST_SECURITY_VIOLATION:{ast_err}"],
        }

    spec_obj = {
        "entrypoint": entrypoint,
        "diverse_inputs": perturbation_spec.diverse_inputs,
        "equivalence_pairs": perturbation_spec.equivalence_pairs,
        "expect_variation": perturbation_spec.expect_variation,
        "check_call_isolation": perturbation_spec.check_call_isolation,
    }
    timed_out, payload, err = _execute_staged_python(
        {
            "candidate_module.py": source_code,
            "perturb.repr": repr(spec_obj),
            "perturb_harness.py": _PERTURBATION_HARNESS_TEMPLATE,
        },
        "perturb_harness.py",
        timeout_sec=timeout_sec,
        cpu_limit_sec=cpu_limit_sec,
    )
    if timed_out or payload is None:
        return {
            "timed_out": timed_out,
            "passed": False,
            "crash_free": False,
            "call_isolation_ok": False,
            "variation_ok": False,
            "equivalence_ok": False,
            "unique_non_empty_outputs": 0,
            "rejection_reasons": [err or "sandbox_failure"],
        }
    return {
        "timed_out": False,
        **payload,
    }
