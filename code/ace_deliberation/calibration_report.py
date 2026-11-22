"""Buat laporan kalibrasi berkala untuk pemilik dari sampel berpasangan.

Bin dan protokol dipakai konsisten untuk seluruh domain. Selisih hanya
dihitung antarperiode berurutan dengan sampel yang cukup. Perubahan
komposisi pertanyaan bisa mengubah delta, sehingga delta dideskripsikan
bersama cakupan dan rujukan, tanpa klaim sebab.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from html import escape
import json
from pathlib import Path

from ._advanced import InputError, integer, read, rows, shape, stamp, text, unique
from .brier_scorer import _rational, score_brier
from .calibration_analyzer import MAX_BINS, analyze


MAX_PERIODS = 100
METRICS = ("brier", "baseline_brier", "improvement", "ece")


def _period(raw, bins):
    shape(raw, ("domain", "period", "source_ref", "brier_input"))
    domain, period = (text(raw[key], key) for key in ("domain", "period"))
    evidence = text(raw["source_ref"], "rujukan pengukuran")
    score = score_brier(raw["brier_input"])
    calibration = analyze(raw["brier_input"], bins=bins)
    return {
        "domain": domain, "period": period, "source_ref": evidence,
        "start": score["cutoff"], "end": score["as_of"], "baseline_rate": score["baseline_rate"],
        "history_count": score["history_count"], "count": score["question_count"],
        "metrics": {key: score[key] for key in METRICS if key != "ece"} | {"ece": calibration["ece"]},
        "bins": calibration["bins"], "history": score["baseline_history"],
    }


def _compare(prior, current, minimum):
    common = {"since": prior["period"], "from_source": prior["source_ref"], "to_source": current["source_ref"]}
    if min(prior["count"], current["count"]) < minimum:
        return {**common, "status": "insufficient_sample", "delta": None}
    metrics = {key: _rational(Fraction(**current["metrics"][key]) - Fraction(**prior["metrics"][key]))
               for key in METRICS}
    return {**common, "status": "compared", "delta": metrics}


def report(raw):
    shape(raw, ("protocol_ref", "bins", "minimum_sample", "periods"))
    protocol = text(raw["protocol_ref"], "rujukan protokol")
    bins = integer(raw["bins"], 2, MAX_BINS)
    minimum = integer(raw["minimum_sample"], 1, 10_000)
    refs = {protocol}
    grouped = defaultdict(list)
    for row in rows(raw["periods"], 0, MAX_PERIODS):
        item = _period(row, bins)
        unique(item["source_ref"], refs)
        grouped[item["domain"]].append(item)
    domains = []
    for domain, periods in sorted(grouped.items()):
        periods.sort(key=lambda item: stamp(item["start"]))
        period_ids, held_out, forecast_refs, resolution_refs = set(), set(), set(), set()
        previous = None
        for item in periods:
            unique(item["period"], period_ids, "ID periode")
            for group in item["bins"]:
                for question in group["questions"]:
                    unique(question["id"], held_out, "ID held-out lintas periode")
                    unique(question["forecast_ref"], forecast_refs)
                    unique(question["resolution_ref"], resolution_refs)
            if previous is not None and stamp(previous["end"]) > stamp(item["start"]):
                raise InputError("Periode dalam domain yang sama harus berurutan tanpa tumpang tindih.")
            item["change_since_previous"] = _compare(previous, item, minimum) if previous is not None else None
            previous = item
        domains.append({"domain": domain, "periods": periods})
    return {"schema": "ace.calibration-report.v1", "protocol_ref": protocol,
            "bins": bins, "minimum_sample": minimum, "domains": domains}


def _safe(value):
    raw = " ".join(value.split())
    return escape(raw).replace("|", "&#124;").replace("`", "&#96;").replace("[", "&#91;").replace("]", "&#93;").replace("*", "&#42;")


def _ratio(value):
    fraction = Fraction(**value)
    return f"{fraction.numerator}/{fraction.denominator}"


def format_markdown(result):
    lines = ["# Laporan kalibrasi ramalan", "", f"Protokol {_safe(result['protocol_ref'])}.",
             f"Bin {result['bins']}. Minimum sampel per periode untuk delta {result['minimum_sample']}."]
    for domain in result["domains"]:
        lines += ["", f"## {_safe(domain['domain'])}", "",
                  "| Periode | N | Brier | Baseline | ECE | Δ Brier | Δ ECE | Sumber |",
                  "|---|---:|---:|---:|---:|---:|---:|---|"]
        for row in domain["periods"]:
            change = row["change_since_previous"]
            delta = change["delta"] if change else None
            unavailable = "Sampel kurang" if change else "—"
            columns = (_safe(row["period"]), str(row["count"]), _ratio(row["metrics"]["brier"]),
                       _ratio(row["metrics"]["baseline_brier"]), _ratio(row["metrics"]["ece"]),
                       _ratio(delta["brier"]) if delta else unavailable,
                       _ratio(delta["ece"]) if delta else unavailable, _safe(row["source_ref"]))
            lines.append("| " + " | ".join(columns) + " |")
    if not result["domains"]:
        lines += ["", "Belum ada periode yang disertakan."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        result = report(read(args.input, 10_000_000))
        if args.format == "markdown":
            print(format_markdown(result), end="")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
