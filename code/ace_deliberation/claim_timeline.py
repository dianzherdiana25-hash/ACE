"""Rekonstruksi versi klaim pada titik waktu tanpa menimpa catatan sebelumnya.

Setiap peristiwa membawa versi yang diharapkan dan rujukan tersendiri.
Revisi, penarikan, dan pemulihan mengikuti transisi eksplisit. Snapshot
menampilkan hanya bukti yang tersedia hingga batas waktu yang diminta.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from .brier_scorer import _stamp


MAX_EVENTS = 40_000
MAX_BYTES = 8_000_000


class TimelineError(ValueError):
    """Riwayat klaim tidak memenuhi urutan atau kontrak sumber."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise TimelineError("Field riwayat klaim tidak sesuai skema.")


def _text(value, label, maximum=128):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise TimelineError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise TimelineError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _refs(raw):
    if not isinstance(raw, list) or len(raw) > 200:
        raise TimelineError("Daftar rujukan melampaui batas.")
    refs = sorted(_text(ref, "rujukan bukti", 512) for ref in raw)
    if len(refs) != len(set(refs)):
        raise TimelineError("Rujukan bukti ganda.")
    return refs


@dataclass(frozen=True, slots=True)
class Event:
    id: str
    claim: str
    source_ref: str
    at: datetime
    operation: str
    previous_version: int
    statement: str
    evidence_refs: list[str]
    reason: str

    @classmethod
    def from_dict(cls, row):
        _shape(row, ("id", "claim", "source_ref", "at", "operation", "previous_version",
                     "statement", "evidence_refs", "reason"))
        old = row["previous_version"]
        operation = row["operation"]
        if type(old) is not int or not 0 <= old <= MAX_EVENTS or operation not in (
            "publish", "revise", "retract", "reinstate",
        ):
            raise TimelineError("Versi atau transisi tidak dikenal.")
        return cls(_text(row["id"], "ID event"), _text(row["claim"], "klaim"),
                   _text(row["source_ref"], "sumber event", 512), _stamp(row["at"]), operation, old,
                   _text(row["statement"], "pernyataan", 12_000), _refs(row["evidence_refs"]),
                   _text(row["reason"], "alasan", 4_000))


def _change(event, versions):
    prior = versions[-1] if versions else None
    if event.previous_version != len(versions):
        raise TimelineError("Peristiwa membawa nomor versi usang atau berlompatan.")
    if prior is None:
        if event.operation != "publish" or not event.evidence_refs:
            raise TimelineError("Versi pertama harus publish dengan rujukan bukti.")
    else:
        if event.at <= _stamp(prior["at"]) or event.operation == "publish":
            raise TimelineError("Peristiwa mendahului versi aktif atau mengulang publish.")
        was_retracted = prior["status"] == "retracted"
        if was_retracted != (event.operation == "reinstate"):
            raise TimelineError("Klaim ditarik hanya bisa dilanjutkan dengan reinstate.")
        if event.operation == "retract":
            if (event.statement != prior["statement"]
                    or event.evidence_refs != prior["evidence_refs"]):
                raise TimelineError("Penarikan tidak boleh mengganti teks atau bukti sebelumnya.")
        else:
            if not event.evidence_refs:
                raise TimelineError("Revisi atau pemulihan wajib bersumber.")
            if (event.operation == "revise" and event.statement == prior["statement"]
                    and event.evidence_refs == prior["evidence_refs"]):
                raise TimelineError("Revisi tidak mengubah isi atau bukti.")
    before = set(prior["evidence_refs"]) if prior else set()
    after = set(event.evidence_refs)
    return {
        "version": len(versions) + 1, "previous_event_id": prior["event_id"] if prior else None,
        "event_id": event.id, "source_ref": event.source_ref, "at": event.at.isoformat(),
        "operation": event.operation, "status": "retracted" if event.operation == "retract" else "asserted",
        "statement": event.statement, "evidence_refs": event.evidence_refs.copy(), "reason": event.reason,
        "statement_changed": prior is None or event.statement != prior["statement"],
        "evidence_added": sorted(after - before), "evidence_removed": sorted(before - after),
    }


def build_timeline(raw):
    _shape(raw, ("as_of", "events"))
    as_of = _stamp(raw["as_of"])
    rows = raw["events"]
    if not isinstance(rows, list) or len(rows) > MAX_EVENTS:
        raise TimelineError("Jumlah event melampaui batas.")
    identifiers, refs = set(), set()
    entries = defaultdict(list)
    for raw_event in rows:
        event = Event.from_dict(raw_event)
        if event.id in identifiers or event.source_ref in refs:
            raise TimelineError("ID atau rujukan event ganda.")
        identifiers.add(event.id)
        refs.add(event.source_ref)
        entries[event.claim].append(event)

    results = []
    for claim, events in sorted(entries.items()):
        # Snapshot as_of memverifikasi riwayat yang terlihat saat cutoff.
        versions = []
        for event in sorted(events, key=lambda item: (item.at, item.id)):
            if event.at <= as_of:
                versions.append(_change(event, versions))
        if versions:
            results.append({"claim": claim, "current": versions[-1], "versions": versions})
    return {"schema": "ace.claim-timeline.v1", "as_of": as_of.isoformat(), "claims": results}


def diff_since(raw, since):
    """Laporkan perubahan antar-snapshot beserta semua revisi dalam selang."""
    report = build_timeline(raw)
    start = _stamp(since)
    if start > _stamp(report["as_of"]):
        raise TimelineError("Awal perbandingan melampaui as_of.")
    changes = []
    for claim in report["claims"]:
        earlier = [row for row in claim["versions"] if _stamp(row["at"]) <= start]
        later = claim["versions"][len(earlier):]
        if not later:
            continue
        before = earlier[-1] if earlier else None
        after = later[-1]
        changes.append({
            "claim": claim["claim"], "before": before, "after": after,
            "operations": [{"kind": row["operation"], "source_ref": row["source_ref"],
                            "at": row["at"]} for row in later],
        })
    return {"schema": "ace.claim-timeline-diff.v1", "since": start.isoformat(),
            "as_of": report["as_of"], "changes": changes}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--diff-since", help="Bandingkan dengan snapshot pada cap waktu ISO 8601.")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise TimelineError("Berkas riwayat melampaui batas.")
        raw = json.loads(data)
        report = build_timeline(raw) if args.diff_since is None else diff_since(raw, args.diff_since)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
