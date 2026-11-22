"""Pilih ambang keputusan dari kurva selective risk dengan ukuran sampel dan cakupan minimum."""
from collections import Counter
from fractions import Fraction

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema

def calibrate(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.abstention-calibration.v1", ("samples", "thresholds", "max_error_bp", "minimum_accepted"))
    cutoffs = sorted({integer(value, "Ambang basis point", 0, 10_000) for value in items(plan["thresholds"], 101, 1)})
    maximum = Fraction(integer(plan["max_error_bp"], "Batas risiko basis point", 0, 10_000), 10_000)
    minimum = integer(plan["minimum_accepted"], "Minimum keputusan", 1, 5000)
    rows = Counter()
    seen = set()
    for row in items(plan["samples"], 6000, 1):
        obj(row, ("id", "confidence_bp", "correct"))
        key = identifier(row["id"], "Contoh")
        confidence = integer(row["confidence_bp"], "Confidence basis point", 0, 10_000)
        if key in seen or type(row["correct"]) is not bool:
            raise GuardianError("Contoh berulang atau hasil bukan boolean.")
        seen.add(key)
        rows[confidence, row["correct"]] += 1
    curve = []
    for cutoff in cutoffs:
        accepted = sum(quantity for (p, _), quantity in rows.items() if p >= cutoff)
        errors = sum(quantity for (p, good), quantity in rows.items() if p >= cutoff and not good)
        rate = Fraction(errors, accepted) if accepted else None
        curve.append({"threshold": cutoff, "accepted": accepted, "errors": errors,
                      "coverage": str(Fraction(accepted, len(seen))), "selective_risk": str(rate) if rate is not None else None,
                      "qualified": accepted >= minimum and rate is not None and rate <= maximum})
    chosen = next((row["threshold"] for row in curve if row["qualified"]), None)
    return {"scope": "empirical_labeled_sample", "chosen_threshold_bp": chosen, "curve": curve, "sample_count": len(seen)}

if __name__ == "__main__":
    raise SystemExit(cli(calibrate, __doc__))
