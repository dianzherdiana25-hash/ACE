"""Cari pola aksi jarang dan perubahan kuantitas dari baseline yang dinyatakan sebelum observasi."""
from collections import Counter, defaultdict
from fractions import Fraction
from statistics import median

from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema

def detect(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.action-anomalies.v1", ("baseline", "observed", "minimum_count", "mad_multiplier"))
    minimum = integer(plan["minimum_count"], "Sampel baseline", 2, 1000)
    factor = integer(plan["mad_multiplier"], "Pengali MAD", 1, 20)
    known = defaultdict(list)
    counts = Counter()
    seen = set()
    def validate(row):
        obj(row, ("id", "kind", "actor", "units", "source"))
        key = identifier(row["id"], "Aksi")
        kind = identifier(row["kind"], "Kelas")
        actor = identifier(row["actor"], "Aktor")
        units = integer(row["units"], "Unit aksi", 0, 1_000_000)
        source = digest(row["source"])
        if key in seen:
            raise GuardianError("Aksi berulang antara baseline dan observasi.")
        seen.add(key)
        return key, kind, actor, units, source
    for row in items(plan["baseline"], 5000):
        _, kind, actor, units, _ = validate(row)
        known[kind].append(Fraction(units))
        counts[kind, actor] += 1
    distribution = {}
    for kind, values in known.items():
        center = median(values)
        mad = median([abs(value - center) for value in values])
        distribution[kind] = (center, mad)
    findings = []
    for row in items(plan["observed"], 5000):
        key, kind, actor, units, reference = validate(row)
        tags = []
        n = len(known[kind])
        if not n:
            tags.append("unseen_kind")
        elif counts[kind, actor] == 0:
            tags.append("unseen_actor_for_kind")
        if n >= minimum:
            center, mad = distribution[kind]
            if abs(units - center) > max(Fraction(1), factor * mad):
                tags.append("unit_outlier")
        if tags:
            findings.append({"id": key, "kind": kind, "flags": tags, "baseline_count": n, "source": reference})
    return {"findings": findings, "baseline_count": len(plan["baseline"]), "observed": len(plan["observed"])}

if __name__ == "__main__":
    raise SystemExit(cli(detect, __doc__))
