"""Tandai pergeseran sinyal dari pengamatan sebelum as_of yang dapat diaudit.

Aktivasi perlu sampel beruntun melewati ambang. Hysteresis menahan
bolak-balik pada zona antara ambang buka dan tutup. Jeda panjang
mengakhiri episode lama sebagai stale dan memutus urutan sampel. Program
membaca arsip dan tidak mengambil pengamatan baru.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational, _stamp
from .devil_advocate import _number


MAX_RULES = 120
MAX_ROWS = 60_000
MAX_BYTES = 10_000_000


class SignalError(ValueError):
    """Aturan sinyal atau pengamatan tidak dapat dibandingkan."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise SignalError("Objek sinyal tidak sesuai skema.")


def _text(value, label, limit=128):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise SignalError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise SignalError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _bounded(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise SignalError(f"Nilai harus integer {lo}–{hi}.")
    return value


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    sense: str
    enter: Fraction
    exit: Fraction
    consecutive: int
    max_age: int
    ref: str

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("id", "direction", "enter", "exit", "consecutive", "max_age_seconds", "rule_ref"))
        sense = raw["direction"]
        enter, exit = _number(raw["enter"]), _number(raw["exit"])
        if sense == "above" and exit < enter or sense == "below" and exit > enter:
            return cls(_text(raw["id"], "ID sinyal"), sense, enter, exit,
                       _bounded(raw["consecutive"], 1, 100), _bounded(raw["max_age_seconds"], 1, 604_800),
                       _text(raw["rule_ref"], "rujukan aturan", 512))
        raise SignalError("Ambang masuk dan keluar tidak membentuk hysteresis.")

    def opens(self, value):
        return value >= self.enter if self.sense == "above" else value <= self.enter

    def closes(self, value):
        return value <= self.exit if self.sense == "above" else value >= self.exit


def _analyze(rule, samples, now):
    events = []
    active = False
    run = []
    last = None

    def expire(at):
        if last is None or at - last[0] <= timedelta(seconds=rule.max_age):
            return False
        if active:
            end = last[0] + timedelta(seconds=rule.max_age)
            events.append({"kind": "stale", "at": end.isoformat(),
                           "observation_refs": [last[2]], "rule_ref": rule.ref})
        return True

    for at, value, ref in samples:
        if expire(at):
            active = False
            run.clear()
        if active:
            if rule.closes(value):
                active = False
                events.append({"kind": "cleared", "at": at.isoformat(), "observation_refs": [ref], "rule_ref": rule.ref})
        elif rule.opens(value):
            run.append(ref)
            if len(run) == rule.consecutive:
                active = True
                events.append({"kind": "activated", "at": at.isoformat(),
                               "observation_refs": run.copy(), "rule_ref": rule.ref})
                run.clear()
        else:
            run.clear()
        last = at, value, ref

    stale = expire(now)
    if last is None:
        status = "unobserved"
    elif stale:
        status = "stale"
    else:
        status = "active" if active else "clear"
    age = now - last[0] if last is not None else None
    current_activation = None
    if status == "active":
        opening = next(event for event in reversed(events) if event["kind"] == "activated")
        current_activation = {"since": opening["at"], "observation_refs": opening["observation_refs"].copy()}
    return {
        "id": rule.id, "status": status, "observations_seen": len(samples), "rule_ref": rule.ref,
        "consecutive_pending": 0 if stale else len(run), "transitions": events,
        "current_activation": current_activation,
        "observation_age_microseconds": (
            (age.days * 86_400 + age.seconds) * 1_000_000 + age.microseconds if age is not None else None
        ),
        "last_observation": {"at": last[0].isoformat(), "value": _rational(last[1]),
                             "source_ref": last[2]} if last is not None else None,
    }


def watch(raw):
    _shape(raw, ("as_of", "rules", "observations"))
    now = _stamp(raw["as_of"])
    rules = raw["rules"]
    if not isinstance(rules, list) or not 1 <= len(rules) <= MAX_RULES:
        raise SignalError("Jumlah aturan sinyal di luar batas.")
    parsed = [Rule.from_dict(row) for row in rules]
    indexed = {rule.id: rule for rule in parsed}
    if len(indexed) != len(parsed) or len({rule.ref for rule in parsed}) != len(parsed):
        raise SignalError("ID atau rujukan aturan ganda.")
    observations = raw["observations"]
    if not isinstance(observations, list) or len(observations) > MAX_ROWS:
        raise SignalError("Jumlah pengamatan di luar batas.")
    samples = defaultdict(list)
    refs, times = set(), set()
    for row in observations:
        _shape(row, ("id", "at", "value", "source_ref"))
        identifier, at = _text(row["id"], "ID pengamatan"), _stamp(row["at"])
        ref = _text(row["source_ref"], "rujukan pengamatan", 512)
        if identifier not in indexed or ref in refs or (identifier, at) in times or at > now:
            raise SignalError("Pengamatan asing, ganda, atau dari masa depan.")
        samples[identifier].append((at, _number(row["value"]), ref))
        refs.add(ref)
        times.add((identifier, at))
    output = [_analyze(indexed[key], sorted(samples[key]), now) for key in sorted(indexed)]
    return {"schema": "ace.signal-watcher.v1", "as_of": now.isoformat(),
            "active_ids": [row["id"] for row in output if row["status"] == "active"],
            "stale_ids": [row["id"] for row in output if row["status"] == "stale"],
            "signals": output}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise SignalError("Masukan sinyal melampaui batas.")
        print(json.dumps(watch(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
