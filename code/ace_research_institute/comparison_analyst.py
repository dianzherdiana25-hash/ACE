"""Bandingkan alternatif hanya pada metrik sebanding, dengan bobot dan cakupan eksplisit."""
from decimal import Decimal, localcontext

from ._contracts import (ResearchError, anchor, cli, decode, fmt, identifier, integer,
                         items, obj, schema, source_bytes, text)
from ._evidence import quantity


def _rules(spec):
    criteria = {}
    for row in items(spec, 30, 1):
        obj(row, ("id", "unit", "floor", "ceiling", "prefer", "weight", "required"))
        name = identifier(row["id"], "Metrik")
        units, low = quantity(row["floor"], row["unit"])
        _, high = quantity(row["ceiling"], row["unit"])
        if name in criteria or low >= high or row["prefer"] not in ("higher", "lower") or type(row["required"]) is not bool:
            raise ResearchError("Definisi metrik ganda atau skala tidak sah.")
        weight = integer(row["weight"], "Bobot", 1, 10000)
        criteria[name] = (units, low, high, row["prefer"], weight, row["required"])
    if sum(values[4] for values in criteria.values()) != 10000:
        raise ResearchError("Bobot seluruh kriteria perlu berjumlah 10.000 basis point.")
    return criteria


def compare(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.comparison-plan.v1", ("criteria", "alternatives", "minimum_coverage_bp"))
    criteria = _rules(plan["criteria"])
    min_coverage = integer(plan["minimum_coverage_bp"], "Cakupan bobot", 1, 10000)
    output = []
    unique = set()
    with localcontext() as context:
        context.prec = 36
        for alternative in items(plan["alternatives"], 50, 2):
            obj(alternative, ("id", "path", "sha256"))
            key = identifier(alternative["id"], "Alternatif")
            if key in unique:
                raise ResearchError("Alternatif ganda.")
            unique.add(key)
            record = decode(source_bytes(root, alternative["path"], alternative["sha256"], 250000))
            schema(record, "ace.institute.observations.v1", ("metrics",))
            measurements = {}
            for row in items(record["metrics"], 30):
                obj(row, ("id", "value", "unit", "source_ref"))
                measurement = identifier(row["id"], "Metrik")
                if measurement not in criteria or measurement in measurements:
                    raise ResearchError("Metrik tidak terdaftar atau digandakan.")
                measurements[measurement] = (row["value"], row["unit"], text(row["source_ref"], "Pointer pengukuran"))
            metric_rows = []
            evidence_mass = 0
            weighted = Decimal(0)
            holds = []
            for field, (unit, low, high, prefer, weight, required) in criteria.items():
                if field not in measurements:
                    result = {"status": "missing"}
                else:
                    val, measurement_unit, pointer = measurements[field]
                    kind, measure = quantity(val, measurement_unit)
                    result = {"value": fmt(measure), "source_ref": pointer, "unit": kind, "status": "included"}
                    if kind != unit or not low <= measure <= high:
                        result["status"] = "incompatible_unit" if kind != unit else "outside_scale"
                    else:
                        normalized = ((measure - low) if prefer == "higher" else (high - measure)) / (high - low)
                        evidence_mass += weight
                        weighted += weight * normalized
                        result["benefit_bp"] = int(normalized * 10000)
                if required and result["status"] != "included":
                    holds.append(field)
                metric_rows.append({"metric": field, "weight_bp": weight, **result})
            grade = int(weighted * 10000 / evidence_mass) if not holds and evidence_mass >= min_coverage else None
            output.append({"id": key, "source": alternative, "coverage_bp": evidence_mass,
                           "required_unmet": holds, "score_bp": grade, "metrics": metric_rows})
    return {"schema": "ace.institute.comparison.v1", "plan_sha256": expected,
            "eligible_rank": [row["id"] for row in sorted((row for row in output if row["score_bp"] is not None),
                              key=lambda row: (-row["score_bp"], -row["coverage_bp"], row["id"]))],
            "alternatives": sorted(output, key=lambda row: row["id"])}


if __name__ == "__main__":
    raise SystemExit(cli(compare, __doc__, rooted=True))
