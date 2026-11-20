"""Kebijakan penjadwalan praktik berjarak (spaced repetition) & eskalasi kesulitan (AG64).

Beroperasi murni sebagai pustaka atas ``Protocol`` store (tanpa impor engine)
untuk menyusun jadwal praktik per gap berdasarkan riwayat keberhasilan/kegagalan:
- Gap yang baru gagal dijadwalkan lebih awal (interval ulang singkat/segera)
  dan menurunkan kesulitan bertahap bila gagal di tingkat tinggi.
- Gap yang stabil dengan deretan lulus beruntun memperoleh interval ulang lebih
  lebar (eksponensial) sekaligus eskalasi tingkat kesulitan berikutnya.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Protocol, Sequence


DEFAULT_BASE_INTERVAL_HOURS = 12.0
DEFAULT_MAX_INTERVAL_HOURS = 168.0
DEFAULT_MAX_DIFFICULTY = 5


class GapPracticeStore(Protocol):
    def list_gap_histories(self) -> Sequence[Mapping[str, Any]]: ...


def _parse_utc(raw: Any, fallback: datetime) -> datetime:
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    else:
        return fallback
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def schedule_gap_practice(
    store: GapPracticeStore | Sequence[Mapping[str, Any]],
    *,
    now: datetime | str,
    base_interval_hours: float = DEFAULT_BASE_INTERVAL_HOURS,
    max_interval_hours: float = DEFAULT_MAX_INTERVAL_HOURS,
    max_difficulty: int = DEFAULT_MAX_DIFFICULTY,
) -> list[dict[str, Any]]:
    """Hitung jadwal praktik berjarak & rekomendasi kesulitan untuk tiap gap."""
    now_dt = _parse_utc(now, datetime.now(timezone.utc)) if not isinstance(now, datetime) else _parse_utc(now, now)
    if base_interval_hours <= 0 or max_interval_hours < base_interval_hours:
        raise ValueError("Parameter interval tidak sah.")
    if max_difficulty < 1:
        raise ValueError("max_difficulty minimal 1.")

    records = store if isinstance(store, Sequence) and not isinstance(store, (str, bytes)) else store.list_gap_histories()
    scheduled: list[dict[str, Any]] = []

    for idx, raw in enumerate(records, 1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Entri gap[{idx}] wajib berupa mapping")
        gap_id = raw.get("gap_id")
        if not isinstance(gap_id, str) or not gap_id.strip():
            raise ValueError(f"Entri gap[{idx}] wajib memiliki gap_id tak-kosong")
        gap_id = gap_id.strip()

        outcomes_raw = raw.get("recent_outcomes") or []
        outcomes = [str(o).strip().lower() for o in outcomes_raw if str(o).strip()]
        difficulty = int(raw.get("difficulty", raw.get("current_difficulty", 1)))
        difficulty = max(1, min(max_difficulty, difficulty))
        last_dt = _parse_utc(raw.get("last_practiced_at"), now_dt)

        consecutive_passes = 0
        for val in reversed(outcomes):
            if val in {"pass", "passed", "ok", "success"}:
                consecutive_passes += 1
            else:
                break

        consecutive_fails = 0
        for val in reversed(outcomes):
            if val in {"fail", "failed", "error"}:
                consecutive_fails += 1
            else:
                break

        total_failures = sum(1 for val in outcomes if val in {"fail", "failed", "error"})
        reasons: list[str] = []

        if consecutive_fails > 0:
            # Baru gagal -> ulang sangat cepat; kegagalan berulang memperketat urgensi & turunkan kesulitan jika perlu.
            interval_hours = round(max(0.25, 1.0 / (1 + consecutive_fails)), 4)
            due_dt = max(now_dt, last_dt + timedelta(hours=interval_hours))
            reasons.append(f"recent_failure_streak={consecutive_fails}")
            if difficulty > 1:
                next_difficulty = difficulty - 1
                difficulty_action = "step_down_remediation"
                reasons.append(f"difficulty_step_down:{difficulty}->{next_difficulty}")
            else:
                next_difficulty = 1
                difficulty_action = "hold_baseline"
                reasons.append("difficulty_hold_baseline:1")
            urgency = round(100.0 + consecutive_fails * 10.0 + total_failures, 4)
        elif consecutive_passes >= 2:
            interval_hours = round(
                min(max_interval_hours, base_interval_hours * (2 ** (consecutive_passes - 1))),
                4,
            )
            due_dt = last_dt + timedelta(hours=interval_hours)
            reasons.append(f"stable_pass_streak={consecutive_passes}")
            if difficulty < max_difficulty:
                next_difficulty = difficulty + 1
                difficulty_action = "escalate"
                reasons.append(f"difficulty_escalate:{difficulty}->{next_difficulty}")
            else:
                next_difficulty = max_difficulty
                difficulty_action = "hold_max"
                reasons.append(f"difficulty_at_max:{max_difficulty}")
            urgency = round(max(1.0, 20.0 - consecutive_passes * 3.0 + total_failures * 0.5), 4)
        else:
            # Belum cukup data atau baru 1 pass setelah gagal: jeda sedang.
            interval_hours = round(base_interval_hours / (1.0 + 0.5 * total_failures), 4)
            due_dt = last_dt + timedelta(hours=interval_hours)
            next_difficulty = difficulty
            difficulty_action = "consolidate"
            reasons.append(f"consolidating_streak={consecutive_passes}_failures={total_failures}")
            urgency = round(40.0 + total_failures * 2.0, 4)

        scheduled.append(
            {
                "gap_id": gap_id,
                "family": raw.get("family"),
                "recent_outcomes": outcomes,
                "total_failures": total_failures,
                "consecutive_passes": consecutive_passes,
                "consecutive_fails": consecutive_fails,
                "current_difficulty": difficulty,
                "recommended_difficulty": next_difficulty,
                "difficulty_action": difficulty_action,
                "interval_hours": interval_hours,
                "scheduled_at": _format_utc(due_dt),
                "urgency_score": urgency,
                "reasons": reasons,
                "_sort_ts": due_dt.timestamp(),
            }
        )

    scheduled.sort(key=lambda row: (row["_sort_ts"], -row["urgency_score"], row["gap_id"]))
    for rank, row in enumerate(scheduled, 1):
        row.pop("_sort_ts", None)
        row["priority_rank"] = rank
    return scheduled
