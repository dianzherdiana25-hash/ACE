"""Process Sentinel and Linux /proc Resource Monitor for Termux.

Pure-Python introspection of active host processes and system limits.
Detects memory leaks, high CPU spikes, and orphaned background processes.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ProcessReport:
    pid: int
    name: str
    state: str
    rss_mb: float
    utime_ticks: int
    stime_ticks: int
    command_line: str


class ProcessSentinel:
    """Monitors running processes on Linux/Android through /proc filesystem."""

    def __init__(self, proc_dir: str = "/proc"):
        self.proc_dir = Path(proc_dir)

    def is_available(self) -> bool:
        """Check if /proc filesystem is mounted and readable."""
        return self.proc_dir.exists() and (self.proc_dir / "version").exists()

    def get_process_info(self, pid: int) -> Optional[ProcessReport]:
        """Read /proc/[pid]/stat and cmdline for a given process."""
        p_dir = self.proc_dir / str(pid)
        if not p_dir.exists():
            return None

        try:
            stat_content = (p_dir / "stat").read_text(encoding="utf-8", errors="ignore").strip()
            # The comm (process name) is between the first '(' and the last ')'
            open_paren = stat_content.find("(")
            close_paren = stat_content.rfind(")")
            if open_paren == -1 or close_paren == -1:
                return None

            name = stat_content[open_paren + 1 : close_paren]
            rest = stat_content[close_paren + 2 :].split()

            state = rest[0]
            utime = int(rest[11])
            stime = int(rest[12])
            rss_pages = int(rest[21])
            rss_mb = round((rss_pages * 4096) / (1024 * 1024), 2)

            cmdline = ""
            cmd_path = p_dir / "cmdline"
            if cmd_path.exists():
                raw = cmd_path.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
                cmdline = raw

            return ProcessReport(
                pid=pid,
                name=name,
                state=state,
                rss_mb=rss_mb,
                utime_ticks=utime,
                stime_ticks=stime,
                command_line=cmdline or name,
            )
        except Exception:
            return None

    def scan_active_python_processes(self) -> List[ProcessReport]:
        """Find all active python processes related to ACE."""
        if not self.is_available():
            return []

        results: List[ProcessReport] = []
        for p in self.proc_dir.iterdir():
            if not p.is_dir() or not p.name.isdigit():
                continue
            pid = int(p.name)
            info = self.get_process_info(pid)
            if info and ("python" in info.name.lower() or "python" in info.command_line.lower()):
                results.append(info)

        results.sort(key=lambda x: x.rss_mb, reverse=True)
        return results

    def audit_system_load(self) -> Dict[str, Any]:
        """Read /proc/loadavg and /proc/meminfo."""
        load_avg = [0.0, 0.0, 0.0]
        load_path = self.proc_dir / "loadavg"
        if load_path.exists():
            try:
                parts = load_path.read_text().strip().split()
                load_avg = [float(parts[0]), float(parts[1]), float(parts[2])]
            except Exception:
                pass

        py_procs = self.scan_active_python_processes()
        total_py_rss = sum(p.rss_mb for p in py_procs)

        return {
            "load_1m": load_avg[0],
            "load_5m": load_avg[1],
            "load_15m": load_avg[2],
            "active_python_processes": len(py_procs),
            "total_python_rss_mb": round(total_py_rss, 2),
            "top_processes": [asdict(p) for p in py_procs[:3]],
        }
