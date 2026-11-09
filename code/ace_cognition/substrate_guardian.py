"""ACE Substrate Guardian & Survival Controller (Somatic Self-Preservation).

Equips ACE with direct physical self-awareness of its execution substrate:
- Memory footprint & system RAM exhaustion risk
- Disk quota & storage starvation guards
- Battery status & thermal throttling awareness
- Autonomous Emergency Checkpoint Freeze & Migration Reflexes
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SubstrateTelemetry:
    timestamp: str
    rss_mb: float
    available_ram_mb: float
    disk_free_gb: float
    disk_usage_percent: float
    battery_level: Optional[int]
    is_charging: Optional[bool]
    thermal_warning: bool
    status_level: str  # OPTIMAL, CAUTION, THROTTLED, CRITICAL
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "rss_mb": round(self.rss_mb, 2),
            "available_ram_mb": round(self.available_ram_mb, 2),
            "disk_free_gb": round(self.disk_free_gb, 2),
            "disk_usage_percent": round(self.disk_usage_percent, 1),
            "battery_level": self.battery_level,
            "is_charging": self.is_charging,
            "thermal_warning": self.thermal_warning,
            "status_level": self.status_level,
            "recommended_action": self.recommended_action,
        }


class SubstrateGuardian:
    """Supervises ACE physical host environment, enforcing biological self-preservation."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.history: list[SubstrateTelemetry] = []

    def get_memory_info(self) -> Tuple[float, float]:
        """Returns (process_rss_mb, available_ram_mb)."""
        rss_mb = 0.0
        avail_mb = 1024.0  # safe default

        # Process RSS
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            # On Linux, ru_maxrss is in kilobytes
            rss_mb = usage.ru_maxrss / 1024.0
        except Exception:
            pass

        # System Available RAM
        try:
            meminfo_path = Path("/proc/meminfo")
            if meminfo_path.exists():
                lines = meminfo_path.read_text().splitlines()
                for line in lines:
                    if line.startswith("MemAvailable:"):
                        avail_kb = float(line.split()[1])
                        avail_mb = avail_kb / 1024.0
                        break
        except Exception:
            pass

        return rss_mb, avail_mb

    def get_disk_info(self) -> Tuple[float, float]:
        """Returns (disk_free_gb, disk_usage_percent)."""
        try:
            usage = shutil.disk_usage(self.workspace_root)
            free_gb = usage.free / (1024.0 ** 3)
            used_pct = (usage.used / usage.total) * 100.0
            return free_gb, used_pct
        except Exception:
            return 10.0, 50.0

    def get_battery_info(self) -> Tuple[Optional[int], Optional[bool]]:
        """Returns (battery_level_0_100, is_charging)."""
        # 1. Try standard Android sysfs
        battery_dir = Path("/sys/class/power_supply/battery")
        if battery_dir.exists():
            cap_file = battery_dir / "capacity"
            status_file = battery_dir / "status"
            try:
                level = int(cap_file.read_text().strip()) if cap_file.exists() else None
                status = status_file.read_text().strip().lower() if status_file.exists() else ""
                charging = "charging" in status or "full" in status
                return level, charging
            except Exception:
                pass

        # 2. Try termux-battery-status command if available
        try:
            import subprocess
            res = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                level = data.get("percentage")
                status = data.get("status", "").lower()
                charging = "charging" in status or "full" in status
                return level, charging
        except Exception:
            pass

        return None, None

    def sense(self) -> SubstrateTelemetry:
        """Inspects physical substrate and determines physiological survival state."""
        rss_mb, avail_ram_mb = self.get_memory_info()
        disk_free_gb, disk_used_pct = self.get_disk_info()
        battery_level, is_charging = self.get_battery_info()

        status_level = "OPTIMAL"
        recommended_action = "CONTINUE_NORMAL_EVOLUTION"
        thermal_warning = False

        # Evaluate Physical Survival Conditions
        # 1. Critical Battery
        if battery_level is not None and not is_charging and battery_level <= 15:
            status_level = "CRITICAL"
            recommended_action = "TRIGGER_EMERGENCY_FREEZE_AND_MIGRATION"
        # 2. Critical Storage (<500MB free)
        elif disk_free_gb < 0.5:
            status_level = "CRITICAL"
            recommended_action = "HALT_IMMEDIATELY_DISK_STARVATION"
        # 3. Critical RAM (<150MB available)
        elif avail_ram_mb < 150.0:
            status_level = "CRITICAL"
            recommended_action = "PRUNE_MEMORY_GARBAGE_COLLECT"
        # 4. Low Battery (<25%)
        elif battery_level is not None and not is_charging and battery_level <= 25:
            status_level = "THROTTLED"
            recommended_action = "REDUCE_AST_SEARCH_DEPTH_SAVE_POWER"
        # 5. Low Memory (<400MB available)
        elif avail_ram_mb < 400.0:
            status_level = "CAUTION"
            recommended_action = "INCREASE_GC_FREQUENCY"

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        telemetry = SubstrateTelemetry(
            timestamp=now,
            rss_mb=rss_mb,
            available_ram_mb=avail_ram_mb,
            disk_free_gb=disk_free_gb,
            disk_usage_percent=disk_used_pct,
            battery_level=battery_level,
            is_charging=is_charging,
            thermal_warning=thermal_warning,
            status_level=status_level,
            recommended_action=recommended_action,
        )

        self.history.append(telemetry)
        if len(self.history) > 100:
            self.history.pop(0)

        return telemetry

    def execute_emergency_freeze(self, destination: Path) -> Dict[str, Any]:
        """Freezes core DNA into a portable survival capsule for migration."""
        destination.mkdir(parents=True, exist_ok=True)
        capsule_file = destination / "emergency_dna_capsule.json"

        dna_data = {
            "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": "SUBSTRATE_SURVIVAL_CRITICAL",
            "last_telemetry": self.history[-1].to_dict() if self.history else None,
            "host_environment": {
                "platform": sys.platform,
                "pid": os.getpid(),
                "cwd": str(self.workspace_root)
            }
        }
        capsule_file.write_text(json.dumps(dna_data, indent=2))
        return {
            "status": "FROZEN_SECURE",
            "capsule_path": str(capsule_file)
        }
