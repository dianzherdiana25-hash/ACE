"""Putar ulang ramalan pada jendela krisis historis yang disimulasikan.

Baseline laju dasar dibekukan per jendela dengan embargo. Masukan
mengisolasi referensi latihan dari seluruh pertanyaan held-out. Skor
dibandingkan pada pasangan yang sama dan diurutkan per episode, tanpa
mengganti data yang absen dengan skor nol.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction

from ._advanced import InputError, integer, json_main, rows, shape, stamp, text, unique
from .brier_scorer import Forecast, Resolution, _rational


MAX_ROWS = 10_000
MAX_WINDOWS = 100


@dataclass(frozen=True, slots=True)
class Window:
    key: str
    start: datetime
    stop: datetime
    ref: str

    @classmethod
    def read(cls, raw, identifiers, refs):
        shape(raw, ("id", "start", "end_exclusive", "source_ref"))
        item = cls(unique(text(raw["id"], "jendela"), identifiers, "Jendela"),
                   stamp(raw["start"]), stamp(raw["end_exclusive"]),
                   unique(text(raw["source_ref"], "sumber jendela"), refs))
        if item.start >= item.stop:
            raise InputError("Jendela harus mempunyai durasi positif.")
        return item


def _index(raw, read, refs):
    lookup = {}
    for record in rows(raw, 0, MAX_ROWS):
        row = read(record)
        unique(row.source_ref, refs)
        if row.question_id in lookup:
            raise InputError("ID kasus ganda di daftar.")
        lookup[row.question_id] = row
    return lookup


def _summarize(scored):
    if not scored:
        return {"paired_cases": 0, "brier": None, "baseline_brier": None, "improvement": None}
    count = len(scored)
    forecast = sum(Fraction(**row["brier"]) for row in scored) / count
    baseline = sum(Fraction(**row["baseline_brier"]) for row in scored) / count
    return {"paired_cases": count, "brier": _rational(forecast), "baseline_brier": _rational(baseline),
            "improvement": _rational(baseline - forecast)}


def replay(raw):
    shape(raw, ("protocol_ref", "as_of", "embargo_days", "minimum_training", "windows",
                "training", "forecasts", "resolutions"))
    protocol = text(raw["protocol_ref"], "protokol")
    refs = {protocol}
    seen = set()
    windows = sorted((Window.read(row, seen, refs) for row in rows(raw["windows"], 1, MAX_WINDOWS)),
                     key=lambda item: (item.start, item.key))
    if any(earlier.stop > later.start for earlier, later in zip(windows, windows[1:])):
        raise InputError("Jendela krisis tidak boleh tumpang tindih.")
    cutoff = stamp(raw["as_of"])
    embargo = integer(raw["embargo_days"], 0, 366)
    minimum = integer(raw["minimum_training"], 1, MAX_ROWS)
    forecasts = _index(raw["forecasts"], Forecast.from_dict, refs)
    resolutions = _index(raw["resolutions"], Resolution.from_dict, refs)
    prior = _index(raw["training"], Resolution.from_dict, refs)
    if prior.keys() & (forecasts.keys() | resolutions.keys()):
        raise InputError("ID latihan dan held-out bertumpang tindih.")

    results, compared = [], []
    assigned = set()
    for window in windows:
        try:
            boundary = window.start - timedelta(days=embargo)
        except OverflowError as exc:
            raise InputError("Embargo keluar dari rentang tanggal.") from exc
        boundary = min(boundary, cutoff)
        training = sorted((row for row in prior.values() if row.at < boundary), key=lambda row: row.question_id)
        base = Fraction(sum(row.value for row in training), len(training)) if len(training) >= minimum else None
        records = []
        for key, candidate in sorted(forecasts.items()):
            if not window.start <= candidate.at < window.stop:
                continue
            assigned.add(key)
            item = {"question_id": key, "forecast_ref": candidate.source_ref,
                    "forecast_at": candidate.at.isoformat(), "probability": _rational(candidate.probability)}
            outcome = resolutions.get(key)
            if candidate.at > cutoff:
                item["status"] = "unissued_at_audit"
            elif outcome is None or outcome.at > cutoff:
                item["status"] = "unresolved_at_audit"
            elif outcome.at <= candidate.at:
                item.update(status="late_forecast", resolution_ref=outcome.source_ref)
            else:
                item.update(status="scored" if base is not None else "baseline_unavailable",
                            outcome=outcome.value, resolved_at=outcome.at.isoformat(),
                            resolution_ref=outcome.source_ref, brier=_rational((candidate.probability - outcome.value)**2))
                if base is not None:
                    item["baseline_brier"] = _rational((base - outcome.value)**2)
                    compared.append(item)
            records.append(item)
        results.append({
            "id": window.key, "source_ref": window.ref, "start": window.start.isoformat(),
            "end_exclusive": window.stop.isoformat(), "training_before": boundary.isoformat(),
            "training": [{"question_id": row.question_id, "resolution_ref": row.source_ref,
                          "resolved_at": row.at.isoformat(), "outcome": row.value} for row in training],
            "baseline_rate": _rational(base) if base is not None else None,
            "records": records, **_summarize([row for row in records if row["status"] == "scored"]),
        })
    return {
        "schema": "ace.crisis-backtest.v1", "protocol_ref": protocol, "as_of": cutoff.isoformat(),
        "embargo_days": embargo, "minimum_training": minimum, "windows": results,
        "outside_windows": sorted(forecasts.keys() - assigned), "pooled": _summarize(compared),
    }


def main(argv=None):
    return json_main(argv, __doc__, replay)


if __name__ == "__main__":
    raise SystemExit(main())
