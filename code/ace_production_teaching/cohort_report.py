"""Rekap perubahan skor pasangan per cohort dengan penyembunyian sel kecil."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import (ProductionError, anchor, cli, day, decode, identifier,
                         integer, obj, schema, source_bytes, text)


def summarize_cohorts(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.cohort-plan.v1", ("input", "through", "minimum_group"))
    now = day(plan["through"])
    threshold = integer(plan["minimum_group"], "Ukuran cohort minimum", 3, 200)
    ref = obj(plan["input"], ("path", "sha256"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 1_500_000)
    groups = defaultdict(dict)
    known = {}
    for line, content in enumerate(raw.splitlines(), 1):
        if line > 18000:
            raise ProductionError("Terlalu banyak catatan cohort.")
        if not content.strip():
            continue
        row = obj(decode(content), ("cohort", "learner", "phase", "date", "earned", "possible", "source_ref"))
        name, key = [identifier(row[field], field) for field in ("cohort", "learner")]
        stage = row["phase"]
        stamp = day(row["date"])
        if stage not in ("before", "after") or stamp > now or known.setdefault(key, name) != name:
            raise ProductionError("Fase, tanggal atau afiliasi cohort bermasalah.")
        status = groups[name].setdefault(key, {})
        if stage in status:
            raise ProductionError("Penilaian per fase ganda pada learner yang sama.")
        possible = integer(row["possible"], "Maksimum", 1, 100000)
        score = Fraction(integer(row["earned"], "Skor", 0, possible), possible)
        text(row["source_ref"], "Pointer tes")
        status[stage] = (score, stamp, line)
    groups_report = []
    totals = []
    for name, members in sorted(groups.items()):
        pairs = []
        missing = 0
        for key, row in members.items():
            if row.keys() != {"before", "after"}:
                missing += 1
                continue
            before, after = row["before"], row["after"]
            if before[1] >= after[1]:
                raise ProductionError("Before harus mendahului after pada learner berpasangan.")
            pairs.append((before[0], after[0]))
        count = len(pairs)
        if count < threshold:
            groups_report.append({"cohort": name, "status": "suppressed_small_cell"})
            continue
        totals.extend(pairs)
        before_total, after_total = [sum(scores) * 10000 / count for scores in zip(*pairs, strict=True)]
        groups_report.append({"cohort": name, "status": "observed", "paired": count, "unpaired": missing,
                              "before_mean_bp": int(before_total), "after_mean_bp": int(after_total),
                              "paired_mean_delta_bp": int(after_total - before_total)})
    return {"schema": "ace.teaching.cohort-report.v1", "plan_sha256": expected, "source": ref,
            "through": plan["through"], "scope": "paired_observations_in_reportable_groups",
            "cohorts": groups_report, "reported_pairs": len(totals),
            "aggregate_delta_bp": int(sum(after - before for before, after in totals) * 10000 / len(totals)) if totals else None}


if __name__ == "__main__":
    raise SystemExit(cli(summarize_cohorts, __doc__, rooted=True))
