#!/usr/bin/env python3
"""Print a read-only local hardware/runtime snapshot; never infer model readiness.

No network requests, inference, subprocesses, services or environment-value dumps.
Model hashing is opt-in because large artifacts consume measurable CPU and I/O.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def _integer(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None and raw != "max" else None
    except ValueError:
        return None


def _cgroups() -> list[dict]:
    root = Path("/sys/fs/cgroup")
    directories = {root}
    for line in (_read(Path("/proc/self/cgroup")) or "").splitlines():
        if line.startswith("0::"):
            relative = Path(line[3:].lstrip("/"))
            if ".." not in relative.parts:
                nested = root / relative
                directories.update(d for d in [nested, *nested.parents] if d == root or root in d.parents)
    records = []
    for directory in sorted(directories, key=str):
        values = {name: _read(directory / name) for name in (
            "memory.max", "memory.current", "memory.peak", "memory.swap.max", "cpu.max", "pids.max",
        )}
        if any(value is not None for value in values.values()):
            records.append({"path": str(directory), "values": values})
    return records


def _model(path: Path, hash_artifact: bool) -> dict:
    result = {"path": str(path), "present": path.is_file(), "inference_status": "NOT_ASSESSED"}
    if not result["present"]:
        return result
    try:
        result["size_bytes"] = path.stat().st_size
        with path.open("rb") as stream:
            result["gguf_magic_valid"] = stream.read(4) == b"GGUF"
            if hash_artifact:
                stream.seek(0)
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                result["sha256"] = digest.hexdigest()
    except OSError as exc:
        result["read_error"] = type(exc).__name__
    return result


def probe(workspace: Path, model_paths: list[Path], hash_artifacts: bool = False) -> dict:
    meminfo = {}
    for line in (_read(Path("/proc/meminfo")) or "").splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] in ("MemTotal:", "MemAvailable:", "MemFree:", "SwapTotal:"):
            value = _integer(fields[1])
            if value is not None and fields[2] == "kB":
                meminfo[fields[0].rstrip(":")] = value * 1024
    groups = _cgroups()
    memory_limits, remaining_memory, cpu_quotas = [], [], []
    for group in groups:
        values = group["values"]
        limit, used = _integer(values["memory.max"]), _integer(values["memory.current"])
        if limit is not None:
            memory_limits.append(limit)
            if used is not None:
                remaining_memory.append(max(0, limit - used))
        fields = (values["cpu.max"] or "").split()
        if len(fields) == 2:
            quota, period = _integer(fields[0]), _integer(fields[1])
            if quota is not None and period is not None and period > 0:
                cpu_quotas.append(quota / period)
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    cpuinfo = _read(Path("/proc/cpuinfo")) or ""
    model_name = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                       if line.startswith("model name") and ":" in line), None)
    flags = next((line.split(":", 1)[1].split() for line in cpuinfo.splitlines()
                  if line.startswith("flags") and ":" in line), [])
    try:
        usage = shutil.disk_usage(workspace)
        disk = {"path": str(workspace), "total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
    except OSError as exc:
        disk = {"path": str(workspace), "read_error": type(exc).__name__}
    policy_path = Path("/etc/codex/network-policy.json")
    policy = {"startup_snapshot_present": policy_path.is_file(), "live_access": "NOT_ASSESSED"}
    try:
        data = json.loads(_read(policy_path) or "{}")
        policy["startup_http_mode"] = data.get("http_network_policy", {}).get("type")
        policy["vpn_configured"] = data.get("vpn_configured")
    except (ValueError, TypeError, AttributeError):
        policy["startup_snapshot_parse_error"] = True
    gpu_devices = sorted(str(path) for pattern in ("nvidia[0-9]*", "dri/renderD*", "dri/card*")
                         for path in Path("/dev").glob(pattern))
    cpu_caps = ([len(affinity)] if affinity else []) + cpu_quotas
    return {
        "schema": "ace.omega.environment_snapshot.v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ATTESTED_SNAPSHOT",
        "os": {"system": platform.system(), "release": platform.release(), "architecture": platform.machine(),
               "distribution": _read(Path("/etc/os-release"))},
        "cpu": {"model_name": model_name, "logical_visible": os.cpu_count(), "affinity_cpus": affinity,
                "cgroup_quota_cores": min(cpu_quotas) if cpu_quotas else None,
                "effective_core_capacity_upper_bound": min(cpu_caps) if cpu_caps else None},
        "memory": {"host_bytes": meminfo, "cgroup_limit_bytes": min(memory_limits) if memory_limits else None,
                   "cgroup_unallocated_bytes": min(remaining_memory) if remaining_memory else None,
                   "unallocated_note": "Excludes reclaimable page cache; this is not a model-fit guarantee."},
        "cgroups_v2": groups,
        "disk": disk,
        "gpu": {"exposed_device_paths": gpu_devices, "vram_bytes": None, "inference_acceleration": "NOT_ASSESSED"},
        "virtualization": {"hypervisor_cpu_flag": "hypervisor" in flags,
                           "cpu_virtualization_flags": [flag for flag in ("vmx", "svm") if flag in flags],
                           "kvm_device_present": Path("/dev/kvm").exists(),
                           "nested_virtualization_usable": "NOT_ASSESSED"},
        "runtime_presence": {name: shutil.which(name) for name in (
            "python3", "ollama", "llama-completion", "llama-cli", "llama-server", "docker", "bwrap",
        )},
        "explicit_llama_binary": {"configured": bool(os.environ.get("ACE_LLAMA_BIN")),
                                  "executable_present": bool(os.environ.get("ACE_LLAMA_BIN") and
                                      Path(os.environ["ACE_LLAMA_BIN"]).is_file() and
                                      os.access(os.environ["ACE_LLAMA_BIN"], os.X_OK))},
        "models": [_model(path, hash_artifacts) for path in model_paths],
        "network": policy,
        "process_lifetime": {"pid_1_command": _read(Path("/proc/1/comm")),
                             "after_session_end": "NOT_ASSESSED", "after_vm_shutdown": "processes_do_not_survive",
                             "daemon_health": "NOT_ASSESSED"},
        "model_readiness": "NOT_ASSESSED_REQUIRES_ACTUAL_INFERENCE",
        "scientific_status": "NOT_ASSESSED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--model-file", type=Path, action="append", default=[])
    parser.add_argument("--sha256", action="store_true", help="Read and hash explicitly named model artifacts.")
    args = parser.parse_args()
    print(json.dumps(probe(args.workspace, args.model_file, args.sha256), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
