"""Gambar reliabilitas probabilitas agar skor rata-rata tidak menyembunyikan bias.

Analisis memakai pasangan held-out yang lolos validasi Brier. Setiap bin
menyimpan rata-rata ramalan, frekuensi teramati, dan rujukan pertanyaan.
Bin kosong diberi null dan tidak digambar sebagai frekuensi nol.
"""
from fractions import Fraction
from html import escape
import json
import math
from pathlib import Path

from . import brier_scorer


DEFAULT_BINS = 10
MAX_BINS = 100
_WIDTH = 680
_HEIGHT = 550
_LEFT = 92
_TOP = 36
_SIZE = 440


def _exact(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction(value):
    return Fraction(value["numerator"], value["denominator"])


def _wilson(hits, count):
    z = 1.959963984540054
    rate = hits / count
    base = 1 + z**2 / count
    center = (rate + z**2 / (2 * count)) / base
    radius = z * math.sqrt(rate * (1 - rate) / count + z**2 / (4 * count**2)) / base
    return [round(max(0, center - radius), 6), round(min(1, center + radius), 6)]


def analyze(raw, *, bins=DEFAULT_BINS):
    """Hitung ECE dan dekomposisi Brier untuk ramalan yang dikelompokkan."""
    if type(bins) is not int or not 2 <= bins <= MAX_BINS:
        raise ValueError(f"bins wajib 2–{MAX_BINS}.")
    scoring = brier_scorer.score_brier(raw)
    observations = scoring["questions"]
    groups = [[] for _ in range(bins)]
    for row in observations:
        probability = _fraction(row["probability"])
        index = min(int(probability * bins), bins - 1)
        groups[index].append((probability, row))

    count = len(observations)
    observed_rate = Fraction(sum(row["outcome"] for row in observations), count)
    ece = reliability = resolution = grouped_brier = Fraction(0)
    overprediction = underprediction = Fraction(0)
    rows = []
    for index, group in enumerate(groups):
        size = len(group)
        interval = {"low": _exact(Fraction(index, bins)), "high": _exact(Fraction(index + 1, bins)),
                    "include_high": index == bins - 1}
        record = {"bin": index, **interval, "count": size, "mean_prediction": None,
                  "observed_rate": None, "confidence_95": None, "signed_gap": None,
                  "ece_contribution": None, "questions": []}
        if group:
            hits = sum(row["outcome"] for _, row in group)
            average = sum(probability for probability, _ in group) / size
            rate = Fraction(hits, size)
            mass = Fraction(size, count)
            gap = average - rate
            contribution = mass * abs(gap)
            ece += contribution
            if gap > 0:
                overprediction += contribution
            elif gap < 0:
                underprediction += contribution
            reliability += mass * gap ** 2
            resolution += mass * (rate - observed_rate) ** 2
            grouped_brier += sum((average - row["outcome"]) ** 2 for _, row in group) / count
            record.update(
                mean_prediction=_exact(average), observed_rate=_exact(rate),
                confidence_95=_wilson(hits, size), signed_gap=_exact(gap),
                ece_contribution=_exact(contribution),
                questions=[{"id": row["question_id"], "forecast_ref": row["forecast_ref"],
                            "resolution_ref": row["resolution_ref"]} for _, row in group],
            )
        rows.append(record)

    return {
        "schema": "ace.calibration-analyzer.v1", "bin_count": bins, "question_count": count,
        "ece": _exact(ece), "reliability": _exact(reliability), "resolution": _exact(resolution),
        "uncertainty": _exact(observed_rate * (1 - observed_rate)), "grouped_brier": _exact(grouped_brier),
        "individual_brier": scoring["brier"],
        "overprediction_ece": _exact(overprediction), "underprediction_ece": _exact(underprediction),
        "bins": rows,
    }


def _x(rate):
    return f"{_LEFT + _SIZE * float(rate):.2f}"


def _y(rate):
    return f"{_TOP + _SIZE * (1 - float(rate)):.2f}"


def render_svg(report):
    bottom = _TOP + _SIZE
    right = _LEFT + _SIZE
    title = escape(f"Kurva kalibrasi · {report['question_count']} pertanyaan")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" role="img">',
        f'<title>{title}</title>',
        '<desc>Probabilitas rata-rata terhadap frekuensi teramati. Batang menunjukkan interval Wilson.</desc>',
        '<rect x="0" y="0" width="100%" height="100%" fill="#fff"/>',
        f'<rect x="{_LEFT}" y="{_TOP}" width="{_SIZE}" height="{_SIZE}" fill="none" stroke="#53565b"/>',
        f'<line x1="{_LEFT}" y1="{bottom}" x2="{right}" y2="{_TOP}" stroke="#707780" stroke-dasharray="5 4"/>',
    ]
    for index in range(6):
        tick = Fraction(index, 5)
        label = f"{float(tick):.1f}"
        parts.extend((
            f'<text x="{_x(tick)}" y="{bottom + 22}" text-anchor="middle">{label}</text>',
            f'<text x="{_LEFT - 12}" y="{_y(tick)}" text-anchor="end">{label}</text>',
        ))
    for row in report["bins"]:
        if not row["count"]:
            continue
        px = _x(_fraction(row["mean_prediction"]))
        py = _y(_fraction(row["observed_rate"]))
        low, high = row["confidence_95"]
        parts.extend((
            f'<line x1="{px}" x2="{px}" y1="{_y(low)}" y2="{_y(high)}" stroke="#08736b" stroke-width="2"/>',
            f'<circle cx="{px}" cy="{py}" r="5" fill="#08736b"><title>Bin {row["bin"]}, n={row["count"]}</title></circle>',
        ))
    midpoint = _LEFT + _SIZE // 2
    parts.extend((
        f'<text x="{midpoint}" y="{bottom + 50}" text-anchor="middle">Probabilitas rata-rata</text>',
        '<text x="0" y="0" transform="translate(22,256) rotate(-90)" text-anchor="middle">Frekuensi teramati</text>',
        '</svg>',
    ))
    return "\n".join(parts) + "\n"


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            data = stream.read(brier_scorer.MAX_BYTES + 1)
        if len(data) > brier_scorer.MAX_BYTES:
            raise ValueError("Masukan kalibrasi melebihi batas.")
        result = analyze(json.loads(data), bins=args.bins)
        if args.format == "svg":
            print(render_svg(result), end="")
        else:
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
