"""Petakan beda posisi pada isu yang benar-benar ditanggapi kedua peserta.

Perbandingan memakai bobot isu. Abstain dan data hilang dikeluarkan dari
penyebut dan dihitung terpisah. Peta SVG memakai skala tetap serta tanda
untuk pasangan tanpa data agar sel kosong tidak menyerupai kesepakatan.
"""
from collections import Counter
from fractions import Fraction
from html import escape
from itertools import combinations
import json
from pathlib import Path

from .brier_scorer import _rational


MAX_PARTICIPANTS = 30
MAX_ISSUES = 250
MAX_BYTES = 5_000_000


class MapError(ValueError):
    """Katalog posisi atau matriks perbedaan tidak dapat diperiksa."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise MapError("Field peta perbedaan tidak sesuai skema.")


def _text(raw, label, limit=140):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > limit or not raw.isprintable():
        raise MapError(f"{label} tidak sah.")
    try:
        raw.encode("utf-8")
    except UnicodeError as exc:
        raise MapError(f"{label} bukan teks UTF-8.") from exc
    return raw.strip()


def _list(raw, minimum, max_count):
    if not isinstance(raw, list) or not minimum <= len(raw) <= max_count:
        raise MapError("Jumlah entri peta di luar batas.")
    return raw


def _pair(left, right, issues, votes):
    available = []
    different = []
    missing = []
    abstained = []
    total_weight, different_weight = 0, 0
    for issue_id, (weight, ref) in issues.items():
        first, second = votes.get((left, issue_id)), votes.get((right, issue_id))
        if first is None or second is None:
            missing.append(issue_id)
        elif first[0] == "abstain" or second[0] == "abstain":
            abstained.append(issue_id)
        else:
            total_weight += weight
            available.append(issue_id)
            if first[0] != second[0]:
                different_weight += weight
                different.append({"issue": issue_id, "issue_ref": ref,
                                  "left_ref": first[1], "right_ref": second[1]})
    probability = Fraction(different_weight, total_weight) if total_weight else None
    return {"left": left, "right": right, "compared_weight": total_weight, "different_weight": different_weight,
            "distance": _rational(probability) if probability is not None else None,
            "compared_issues": available, "missing_issues": missing, "abstained_issues": abstained,
            "difference_sources": different}


def compare(raw):
    _shape(raw, ("participants", "issues", "positions"))
    people = [_text(row, "peserta", 60) for row in _list(raw["participants"], 2, MAX_PARTICIPANTS)]
    if len(set(people)) != len(people):
        raise MapError("Peserta ganda.")
    issues = {}
    source_refs = set()
    for row in _list(raw["issues"], 1, MAX_ISSUES):
        _shape(row, ("id", "weight", "source_ref"))
        identifier = _text(row["id"], "isu")
        ref = _text(row["source_ref"], "sumber isu", 512)
        weight = row["weight"]
        if identifier in issues or ref in source_refs or type(weight) is not int or not 1 <= weight <= 1_000:
            raise MapError("Isu ganda atau bobot tidak sah.")
        issues[identifier] = weight, ref
        source_refs.add(ref)
    votes = {}
    for row in _list(raw["positions"], 0, MAX_PARTICIPANTS * MAX_ISSUES):
        _shape(row, ("participant", "issue", "stance", "source_ref"))
        participant = _text(row["participant"], "peserta", 60)
        issue = _text(row["issue"], "isu")
        source = _text(row["source_ref"], "sumber posisi", 512)
        stance = row["stance"]
        key = participant, issue
        if (participant not in people or issue not in issues or key in votes or source in source_refs
                or stance not in ("for", "against", "abstain")):
            raise MapError("Posisi ganda atau tidak dikenal.")
        votes[key] = stance, source
        source_refs.add(source)
    roster = sorted(people)
    issue_catalog = dict(sorted(issues.items()))
    rows = [_pair(left, right, issue_catalog, votes) for left, right in combinations(roster, 2)]
    positive = [row for row in rows if row["different_weight"]]
    maximum = max((Fraction(**row["distance"]) for row in positive), default=None)
    highest = [[row["left"], row["right"]] for row in positive if Fraction(**row["distance"]) == maximum]
    issue_profiles = []
    for issue, (weight, ref) in issue_catalog.items():
        counts = Counter(votes.get((participant, issue), ("missing", None))[0] for participant in roster)
        issue_profiles.append({
            "id": issue, "weight": weight, "source_ref": ref,
            "opposing_pairs": counts["for"] * counts["against"],
            "stances": {key: counts[key] for key in ("for", "against", "abstain", "missing")},
        })
    return {"schema": "ace.disagreement-map.v1", "participants": roster, "issues": sorted(issue_catalog),
            "issue_profiles": issue_profiles, "pairs": rows, "highest_disagreement": highest}


def render_svg(report):
    members = report["participants"]
    cell = 42
    margin = 184
    canvas = margin + len(members) * cell + 25
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas} {canvas}" role="img">',
        '<title>Peta perbedaan posisi</title>',
        '<desc>Persentase beda pada isu yang ditanggapi bersama. Tanda ? berarti tidak ada pembanding.</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
    ]
    cells = {(row["left"], row["right"]): row["distance"] for row in report["pairs"]}
    for i, left in enumerate(members):
        short = escape(left if len(left) <= 23 else left[:22] + "…", quote=False)
        full = escape(left, quote=False)
        point = margin + i * cell + 20
        parts.append(f'<text x="{margin - 10}" y="{point + 4}" text-anchor="end" font-size="12">'
                     f'<title>{full}</title>{short}</text>')
        parts.append(f'<text transform="translate({point},{margin - 10}) rotate(-55)" font-size="12">'
                     f'<title>{full}</title>{short}</text>')
        for j, right in enumerate(members):
            diagonal = i == j
            raw = cells.get(tuple(sorted((left, right))))
            x, y = margin + j * cell, margin + i * cell
            if diagonal:
                fill, label = "#e4e8ef", "–"
            elif raw is None:
                fill, label = "#f3f5f7", "?"
            else:
                distance = Fraction(**raw)
                percentage = float(distance * 100)
                color = round(237 - percentage * 1.3)
                fill, label = f"rgb(249,{color},{color})", f"{percentage:.0f}%"
            parts.append(f'<rect x="{x}" y="{y}" width="40" height="40" fill="{fill}" stroke="#6e7780"/>')
            parts.append(f'<text x="{x + 20}" y="{y + 25}" text-anchor="middle" '
                         f'font-size="12" fill="#15202b">{label}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise MapError("Berkas peta melampaui batas.")
        report = compare(json.loads(data))
        if args.format == "svg":
            print(render_svg(report), end="")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
