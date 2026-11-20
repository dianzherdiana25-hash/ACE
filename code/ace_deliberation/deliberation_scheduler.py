"""Jadwalkan deliberasi yang sudah tersedia dalam satu jendela sumber daya.

Pekerjaan terpilih berjalan menurut tenggat paling awal. Program memilih
subset berurgensi total terbesar yang bisa selesai tepat waktu dengan biaya
internal maksimal sesuai masukan. Jadwal berupa data dan tidak menjalankan
siklus atau menganggarkan uang.
"""
from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path

from .brier_scorer import _stamp


MAX_REQUESTS = 48
MAX_WINDOW = 360
MAX_CREDITS = 250
MAX_EXPLANATIONS = 8
MAX_BYTES = 2_000_000


class ScheduleError(ValueError):
    """Masukan jadwal tidak bisa ditafsirkan sebagai jendela yang sah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ScheduleError("Field penjadwalan tidak sesuai skema.")


def _text(value, label, limit=100):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ScheduleError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ScheduleError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ScheduleError(f"Bilangan bulat wajib {lo}–{hi}.")
    return value


@dataclass(frozen=True, slots=True)
class Request:
    id: str
    duration: int
    due: int
    cost: int
    urgency: int
    ref: str

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("id", "duration_minutes", "due_minute", "cost_units", "urgency", "source_ref"))
        return cls(_text(raw["id"], "ID deliberasi"), _integer(raw["duration_minutes"], 1, MAX_WINDOW),
                   _integer(raw["due_minute"], 1, 10_080), _integer(raw["cost_units"], 0, MAX_CREDITS),
                   _integer(raw["urgency"], 1, 10_000), _text(raw["source_ref"], "sumber permintaan", 512))


def _select(requests, window, credits, *, required=None):
    """Simpan jadwal terbaik per pasangan durasi × kredit dalam urutan tenggat."""
    routes = {(0, 0): (0, ())}
    for request in requests:
        allowed_end = min(window, request.due)
        mandatory = request.id == required
        if request.duration > allowed_end or request.cost > credits:
            if mandatory:
                return None
            continue
        updated = {} if mandatory else dict(routes)
        for (minute, cost), (points, selected) in routes.items():
            finish = minute + request.duration
            spend = cost + request.cost
            if finish > allowed_end or spend > credits:
                continue
            candidate = (points + request.urgency, (*selected, request.id))
            old = updated.get((finish, spend))
            if old is None or (-candidate[0], candidate[1]) < (-old[0], old[1]):
                updated[finish, spend] = candidate
        routes = updated
    if not routes:
        return None
    (minute, cost), (points, selected) = min(
        routes.items(), key=lambda item: (-item[1][0], item[0][1], item[0][0], item[1][1])
    )
    return minute, cost, points, selected


def schedule(raw):
    """Rencanakan satu mesin dan satu jendela untuk semua permintaan tersedia."""
    fields = {"opens_at", "window_minutes", "budget_units", "requests"}
    if isinstance(raw, dict) and "explain_ids" in raw:
        fields.add("explain_ids")
    _shape(raw, fields)
    try:
        opened = _stamp(raw["opens_at"])
    except ValueError as exc:
        raise ScheduleError("Awal jadwal wajib cap waktu berzona.") from exc
    window = _integer(raw["window_minutes"], 1, MAX_WINDOW)
    budget = _integer(raw["budget_units"], 0, MAX_CREDITS)
    try:
        closes = opened + timedelta(minutes=window)
    except OverflowError as exc:
        raise ScheduleError("Jendela melebihi rentang kalender.") from exc
    rows = raw["requests"]
    if not isinstance(rows, list) or len(rows) > MAX_REQUESTS:
        raise ScheduleError("Jumlah permintaan melampaui batas.")
    requests = sorted((Request.from_dict(item) for item in rows), key=lambda item: (item.due, item.id))
    indexed = {request.id: request for request in requests}
    if len(indexed) != len(requests) or len({request.ref for request in requests}) != len(requests):
        raise ScheduleError("ID atau rujukan permintaan ganda.")
    explain = raw.get("explain_ids", [])
    if not isinstance(explain, list) or len(explain) > MAX_EXPLANATIONS:
        raise ScheduleError("explain_ids melampaui batas.")
    explain_ids = [_text(item, "permintaan yang dijelaskan") for item in explain]
    if set(explain_ids) - indexed.keys() or len(set(explain_ids)) != len(explain_ids):
        raise ScheduleError("Permintaan yang dijelaskan asing atau ganda.")

    elapsed, cost, urgency, winners = _select(requests, window, budget)
    plans, unscheduled = [], []
    minute = 0
    for identifier in winners:
        request = indexed[identifier]
        end = minute + request.duration
        plans.append({"id": request.id, "source_ref": request.ref, "start_minute": minute, "finish_minute": end,
                      "due_minute": request.due, "starts_at": (opened + timedelta(minutes=minute)).isoformat(),
                      "ends_at": (opened + timedelta(minutes=end)).isoformat(),
                      "cost_units": request.cost, "urgency": request.urgency})
        minute = end
    selected = set(winners)
    for request in requests:
        if request.id in selected:
            continue
        reasons = []
        if request.duration > min(window, request.due):
            reasons.append("duration_exceeds_window_or_deadline")
        if request.cost > budget:
            reasons.append("cost_exceeds_budget")
        unscheduled.append({"id": request.id, "source_ref": request.ref,
                            "reasons": reasons or ["excluded_by_optimum"]})
    explanations = []
    for identifier in sorted(explain_ids):
        alternative = (elapsed, cost, urgency, winners) if identifier in selected else _select(
            requests, window, budget, required=identifier,
        )
        feasible = alternative is not None
        explanations.append({
            "id": identifier, "status": "already_selected" if identifier in selected else
            "feasible_if_required" if feasible else "infeasible_even_alone",
            "urgency_loss": urgency - alternative[2] if feasible else None,
            "candidate_schedule_ids": list(alternative[3]) if feasible else [],
        })
    return {"schema": "ace.deliberation-scheduler.v1", "opens_at": opened.isoformat(),
            "closes_at": closes.isoformat(), "used_minutes": elapsed, "cost_units": cost,
            "urgency_total": urgency, "schedule": plans, "unscheduled": unscheduled,
            "explanations": explanations}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ScheduleError("Masukan penjadwalan melampaui batas.")
        print(json.dumps(schedule(json.loads(raw)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
