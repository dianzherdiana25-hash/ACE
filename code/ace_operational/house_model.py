"""Pembangun model dunia rumah ACE dari telemetri JSON dengan aturan kebaruan (AG76).

Mengolah telemetri empat subsistem (anggaran per peran, ``bridge_health``,
``engine_status``, dan ``queue``) serta menilai kebaruan stempel waktunya
secara ketat terhadap ``now`` dan ``max_age_seconds``:
- Data tanpa stempel waktu atau lebih tua dari ``max_age_seconds`` wajib
  ditandai ``stale=True`` (basi), tidak pernah dianggap segar.
- Hanya impor pustaka standar tanpa menyentuh ``autonomous_engine``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


SCHEMA = "ace.house-world-model.v1"
DEFAULT_MAX_AGE_SECONDS = 300


def _parse_ts(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _eval_freshness(
    section: Mapping[str, Any] | None,
    *,
    now_dt: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not isinstance(section, Mapping):
        return {"present": False, "fresh": False, "stale": True, "freshness": "missing", "age_seconds": None}
    raw_ts = section.get("updated_at") or section.get("observed_at") or section.get("ts")
    ts = _parse_ts(raw_ts)
    if ts is None:
        return {
            "present": True,
            "fresh": False,
            "stale": True,
            "freshness": "missing_or_invalid_timestamp",
            "age_seconds": None,
        }
    age = (now_dt - ts).total_seconds()
    if age < 0:
        return {
            "present": True,
            "fresh": False,
            "stale": True,
            "freshness": "future_timestamp_invalid",
            "age_seconds": age,
        }
    is_stale = age > max_age_seconds
    return {
        "present": True,
        "fresh": not is_stale,
        "stale": is_stale,
        "freshness": "stale" if is_stale else "fresh",
        "age_seconds": round(age, 3),
    }


def build_house_world_model(
    telemetry: Mapping[str, Any],
    *,
    now: datetime | str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Bangun model dunia rumah berstatus kebaruan per subsistem dari telemetri JSON."""
    if not isinstance(telemetry, Mapping):
        raise ValueError("telemetry wajib berupa mapping JSON")
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("max_age_seconds wajib integer nonnegatif")
    now_dt = _parse_ts(now)
    if now_dt is None:
        raise ValueError(f"Timestamp acuan now wajib memiliki zona waktu: {now!r}")

    stale_subsystems: list[str] = []
    world_gaps: list[dict[str, str]] = []

    # 1. Budgets per peran
    raw_budgets = telemetry.get("budgets")
    b_fresh = _eval_freshness(raw_budgets if isinstance(raw_budgets, Mapping) else None, now_dt=now_dt, max_age_seconds=max_age_seconds)
    roles_src = {}
    if isinstance(raw_budgets, Mapping):
        roles_src = raw_budgets.get("roles") if isinstance(raw_budgets.get("roles"), Mapping) else {
            k: v for k, v in raw_budgets.items() if isinstance(v, Mapping)
        }
    roles_out: dict[str, dict[str, Any]] = {}
    exhausted_roles: list[str] = []
    for role, r_info in sorted(roles_src.items()):
        rem = int(r_info.get("remaining", 0))
        lim = int(r_info.get("limit", rem))
        if rem <= 0:
            exhausted_roles.append(str(role))
        roles_out[str(role)] = {"remaining": rem, "limit": lim, "exhausted": rem <= 0}
    if b_fresh["stale"]:
        stale_subsystems.append("budgets")
        world_gaps.append({"subsystem": "budgets", "reason": b_fresh["freshness"]})

    # 2. Bridge health
    raw_bridge = telemetry.get("bridge_health")
    br_fresh = _eval_freshness(raw_bridge if isinstance(raw_bridge, Mapping) else None, now_dt=now_dt, max_age_seconds=max_age_seconds)
    bridge_ok = bool(raw_bridge.get("ok")) if isinstance(raw_bridge, Mapping) else False
    if br_fresh["stale"]:
        stale_subsystems.append("bridge_health")
        world_gaps.append({"subsystem": "bridge_health", "reason": br_fresh["freshness"]})

    # 3. Engine status
    raw_engine = telemetry.get("engine_status")
    eng_fresh = _eval_freshness(raw_engine if isinstance(raw_engine, Mapping) else None, now_dt=now_dt, max_age_seconds=max_age_seconds)
    engine_running = bool(raw_engine.get("running")) if isinstance(raw_engine, Mapping) else False
    if eng_fresh["stale"]:
        stale_subsystems.append("engine_status")
        world_gaps.append({"subsystem": "engine_status", "reason": eng_fresh["freshness"]})

    # 4. Queue depth
    raw_queue = telemetry.get("queue")
    q_fresh = _eval_freshness(raw_queue if isinstance(raw_queue, Mapping) else None, now_dt=now_dt, max_age_seconds=max_age_seconds)
    q_depth = int(raw_queue.get("depth", 0)) if isinstance(raw_queue, Mapping) else 0
    q_crit = int(raw_queue.get("critical_pending", 0)) if isinstance(raw_queue, Mapping) else 0
    if q_fresh["stale"]:
        stale_subsystems.append("queue")
        world_gaps.append({"subsystem": "queue", "reason": q_fresh["freshness"]})

    any_unhealthy_signal = (not bridge_ok) or (not engine_running) or len(exhausted_roles) > 0
    if any_unhealthy_signal:
        house_state = "sick"
    elif stale_subsystems:
        house_state = "stale"
    else:
        house_state = "healthy"

    return {
        "schema": SCHEMA,
        "evaluated_at": now_dt.isoformat().replace("+00:00", "Z"),
        "max_age_seconds": max_age_seconds,
        "house_state": house_state,
        "all_fresh": len(stale_subsystems) == 0,
        "is_sick": house_state != "healthy",
        "stale_subsystems": stale_subsystems,
        "exhausted_roles": exhausted_roles,
        "world_gaps": world_gaps,
        "budgets": {**b_fresh, "roles": roles_out},
        "bridge_health": {**br_fresh, "ok": bridge_ok},
        "engine_status": {**eng_fresh, "running": engine_running},
        "queue": {**q_fresh, "depth": q_depth, "critical_pending": q_crit},
    }
