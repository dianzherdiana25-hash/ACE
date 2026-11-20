"""Parser klasifikasi status engine bersama untuk house_check dan bridge_home (AG6).

Menyatukan pembacaan dan aturan kesegaran berkas status engine secara baca-saja
agar ``house_check`` maupun preflight ``bridge_home`` menggunakan satu logika
tunggal yang konsisten (K8):
- berkas tak terbaca / JSON cacat / tipe field salah / ``age < 0`` -> ``unavailable``;
- ``running=false`` -> ``stopped`` berapa pun usianya;
- ``running=true`` tanpa ``updated_at`` -> ``healthy``;
- ``running=true`` dengan ``age > max_age_seconds`` -> ``stale`` (tepat pada batas -> ``healthy``).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_MAX_AGE_SECONDS = 300


def parse_engine_status(
    path: Path,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Baca dan klasifikasikan berkas JSON status engine secara read-only."""
    unavailable = {"state": "unavailable", "safe_to_continue": False}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or type(payload.get("running")) is not bool
            or type(payload.get("pid")) is not int
            or payload["pid"] <= 0
            or type(payload.get("cycle_count")) is not int
            or payload["cycle_count"] < 0
        ):
            return unavailable

        base_meta = {
            "pid": payload["pid"],
            "cycle_count": payload["cycle_count"],
            "running": payload["running"],
        }
        if not payload["running"]:
            return {"state": "stopped", "safe_to_continue": False, **base_meta}
        if "updated_at" not in payload:
            return {"state": "healthy", "safe_to_continue": True, **base_meta}

        stamp = payload["updated_at"]
        if not isinstance(stamp, str):
            return unavailable
        updated = datetime.fromisoformat(stamp)
        current = now if now is not None else datetime.now(timezone.utc)
        if updated.utcoffset() is None or current.utcoffset() is None:
            return unavailable
        age = (current - updated).total_seconds()
        if age < 0:
            return unavailable
        state = "stale" if age > max_age_seconds else "healthy"
        return {
            "state": state,
            "safe_to_continue": state == "healthy",
            **base_meta,
            "age_seconds": age,
        }
    except (OSError, ValueError):
        return unavailable


def format_for_house_check(parsed: dict[str, Any]) -> dict[str, Any]:
    """Kembalikan bentuk kamus komponen engine persis seperti kontrak house_check."""
    if parsed["state"] == "unavailable":
        return {"state": "unavailable"}
    out = {
        "state": parsed["state"],
        "pid": parsed["pid"],
        "cycle_count": parsed["cycle_count"],
        "running": parsed["running"],
    }
    if "age_seconds" in parsed:
        out["age_seconds"] = parsed["age_seconds"]
    return out


def format_for_bridge_home(parsed: dict[str, Any]) -> dict[str, Any]:
    """Kembalikan bentuk kamus status engine persis seperti kontrak bridge_home."""
    out: dict[str, Any] = {
        "state": parsed["state"],
        "safe_to_continue": bool(parsed["safe_to_continue"]),
    }
    if "age_seconds" in parsed:
        out["age_seconds"] = parsed["age_seconds"]
    return out
