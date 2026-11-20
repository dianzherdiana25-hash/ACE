"""Perkirakan kredibilitas sumber dari catatan pemeriksaan pada domain tertentu.

Beberapa pemeriksaan atas satu klaim memberi satu kontribusi. Pemeriksaan
yang saling bertentangan dicatat sebagai contested. Bobot usia dan prior
Beta(1, 1) dicatat agar angka dapat dihitung ulang. Skor ditahan jika
riwayat yang selesai belum memenuhi ambang.
"""
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational, _stamp


MAX_REFERENCES = 20_000
MAX_SOURCES = 1_000
MAX_BYTES = 8_000_000


class CredibilityError(ValueError):
    """Katalog sumber atau riwayat pemeriksaan tidak sah."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise CredibilityError("Field kredibilitas tidak sesuai skema.")


def _text(value, label, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise CredibilityError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise CredibilityError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _number(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise CredibilityError("Parameter usia atau sampel di luar batas.")
    return value


def _rows(raw, maximum):
    if not isinstance(raw, list) or len(raw) > maximum:
        raise CredibilityError("Jumlah record kredibilitas melewati batas.")
    return raw


def _sensitivity(resolved, yes, no, minimum):
    if len(resolved) <= minimum:
        return None
    leave_one = []
    for case, verdict, weight in resolved:
        altered_yes = yes - weight if verdict == "supported" else yes
        altered_no = no - weight if verdict == "contradicted" else no
        leave_one.append(((1 + altered_yes) / (2 + altered_yes + altered_no), case))
    low = min(leave_one)
    high = min(leave_one, key=lambda entry: (-entry[0], entry[1]))
    return {
        "minimum": {"estimate": _rational(low[0]), "claim_removed": low[1]},
        "maximum": {"estimate": _rational(high[0]), "claim_removed": high[1]},
    }


def assess(raw):
    _shape(raw, ("as_of", "topic", "window_days", "half_weight_after_days", "minimum_cases",
                 "sources", "assessments"))
    now = _stamp(raw["as_of"])
    topic = _text(raw["topic"], "topik")
    window = _number(raw["window_days"], 1, 7_300)
    half = _number(raw["half_weight_after_days"], 0, window)
    minimum = _number(raw["minimum_cases"], 1, MAX_REFERENCES)
    catalog = {}
    refs = set()
    for row in _rows(raw["sources"], MAX_SOURCES):
        _shape(row, ("id", "source_ref"))
        identifier = _text(row["id"], "sumber")
        reference = _text(row["source_ref"], "rujukan katalog", 512)
        if identifier in catalog or reference in refs:
            raise CredibilityError("ID atau rujukan sumber ganda.")
        catalog[identifier] = reference
        refs.add(reference)

    grouped = defaultdict(lambda: defaultdict(list))
    excluded = []
    for row in _rows(raw["assessments"], MAX_REFERENCES):
        _shape(row, ("source", "topic", "claim_id", "verdict", "at", "source_ref"))
        source_id = _text(row["source"], "ID sumber")
        domain = _text(row["topic"], "topik penilaian")
        case = _text(row["claim_id"], "ID klaim")
        ref = _text(row["source_ref"], "rujukan audit", 512)
        at = _stamp(row["at"])
        verdict = row["verdict"]
        if source_id not in catalog or ref in refs or at > now or verdict not in ("supported", "contradicted", "unresolved"):
            raise CredibilityError("Penilaian asing, ganda, atau belum tersedia.")
        refs.add(ref)
        if domain != topic or now - at > timedelta(days=window):
            excluded.append({"source_ref": ref, "reason": "other_topic" if domain != topic else "outside_window"})
            continue
        grouped[source_id][case].append((at, verdict, ref))

    scores = []
    for source, ref in sorted(catalog.items()):
        trace = []
        weight_yes, weight_no = Fraction(0), Fraction(0)
        resolved_cases = []
        for claim, observations in sorted(grouped[source].items()):
            resolved = [item for item in observations if item[1] != "unresolved"]
            outcomes = {item[1] for item in resolved}
            weight = Fraction(0)
            if len(outcomes) == 1:
                verdict = next(iter(outcomes))
                # Usia ditambatkan pada pemeriksaan tuntas pertama dalam jendela.
                first = min(item[0] for item in resolved)
                weight = Fraction(1, 2) if now - first > timedelta(days=half) else Fraction(1)
                resolved_cases.append((claim, verdict, weight))
                if verdict == "supported":
                    weight_yes += weight
                else:
                    weight_no += weight
            else:
                verdict = "contested" if outcomes else "unresolved"
            trace.append({"claim_id": claim, "state": verdict, "weight": _rational(weight),
                          "assessment_refs": sorted(item[2] for item in observations)})
        resolved_count = len(resolved_cases)
        posterior = (1 + weight_yes) / (2 + weight_yes + weight_no) if resolved_count >= minimum else None
        scores.append({
            "id": source, "source_ref": ref, "status": "scored" if posterior is not None else "insufficient_history",
            "estimate": _rational(posterior) if posterior is not None else None,
            "resolved_case_count": resolved_count, "support_weight": _rational(weight_yes),
            "contradiction_weight": _rational(weight_no), "claims": trace,
            "leave_one_case_out": _sensitivity(resolved_cases, weight_yes, weight_no, minimum),
        })
    return {"schema": "ace.source-credibility.v1", "topic": topic, "as_of": now.isoformat(),
            "minimum_cases": minimum, "window_days": window, "half_weight_after_days": half,
            "sources": scores, "excluded": sorted(excluded, key=lambda row: row["source_ref"])}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise CredibilityError("Berkas kredibilitas melampaui batas.")
        print(json.dumps(assess(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
