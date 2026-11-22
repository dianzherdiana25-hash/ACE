"""Bandingkan perilaku belajar per format pada tugas berpasangan dengan cakupan yang jelas."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import ProductionError, anchor, cli, decode, identifier, integer, items, obj, schema, source_bytes, text


def probe(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.format-probe-plan.v1", ("observations", "formats", "minimum_pairs", "minimum_delta_bp"))
    names = [identifier(name, "Format") for name in items(plan["formats"], 2, 2)]
    if len(set(names)) != 2:
        raise ProductionError("Uji format memerlukan dua kelas berbeda.")
    needed = integer(plan["minimum_pairs"], "Pasangan minimum", 2, 200)
    threshold = integer(plan["minimum_delta_bp"], "Ambang beda", 1, 10000)
    ref = obj(plan["observations"], ("path", "sha256"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 1_000_000)
    arms = defaultdict(dict)
    for number, item in enumerate(raw.splitlines(), 1):
        if number > 12000:
            raise ProductionError("Observasi format melewati batas baris.")
        if not item.strip():
            continue
        row = obj(decode(item), ("pair", "format", "score_bp", "seconds", "source_ref"))
        group = identifier(row["pair"], "Pasangan")
        variant = identifier(row["format"], "Format percobaan")
        if variant not in names or variant in arms[group]:
            raise ProductionError("Format tidak terdaftar atau satu sisi pasangan ganda.")
        arms[group][variant] = {"score": integer(row["score_bp"], "Skor", 0, 10000),
                              "seconds": integer(row["seconds"], "Durasi percobaan", 1, 10000),
                              "line": number, "source_ref": text(row["source_ref"], "Pointer observasi")}
    pairs = []
    held = []
    for key, cases in sorted(arms.items()):
        if cases.keys() != set(names):
            held.append({"pair": key, "missing_formats": sorted(set(names) - cases.keys())})
        else:
            first, second = [cases[name] for name in names]
            pairs.append({"pair": key, "delta_bp": second["score"] - first["score"],
                          "seconds_difference": second["seconds"] - first["seconds"], "observations": cases})
    estimate = int(Fraction(sum(item["delta_bp"] for item in pairs), len(pairs))) if pairs else None
    if len(pairs) < needed:
        result = "insufficient_comparable_pairs"
    elif abs(estimate) < threshold:
        result = "no_material_observed_difference"
    else:
        result = "higher_observed_scores_in_" + names[int(estimate > 0)]
    return {"schema": "ace.teaching.format-probe.v1", "plan_sha256": expected,
            "scope": "observed_matched_format_outcomes", "formats": names, "source": ref,
            "status": result, "pair_count": len(pairs), "mean_second_minus_first_bp": estimate,
            "pairs": pairs, "held": held}


if __name__ == "__main__":
    raise SystemExit(cli(probe, __doc__, rooted=True))
