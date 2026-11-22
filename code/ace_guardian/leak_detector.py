"""Tandai tren RSS berulang dengan median kemiringan dan pisahkan sesi lintas restart."""
from collections import defaultdict
from fractions import Fraction
from statistics import median

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema, text
from .snapshot_scheduler import instant

def detect(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rss-leak.v1", ("samples", "minimum", "growth_mib_per_hour", "min_total_mib"))
    floor = integer(plan["minimum"], "Minimum sampel", 3, 200)
    threshold = integer(plan["growth_mib_per_hour"], "Ambang kemiringan", 1, 100_000)
    min_gain = integer(plan["min_total_mib"], "Pertumbuhan minimum", 1, 100_000)
    processes = defaultdict(list)
    for row in items(plan["samples"], 4000):
        obj(row, ("instance", "at", "rss_mib", "source"))
        name = identifier(row["instance"], "Instance proses")
        value = integer(row["rss_mib"], "RSS MiB", 0, 1_000_000)
        processes[name].append((instant(row["at"]), value, text(row["source"], "Bukti RSS")))
    report = []
    for key, values in sorted(processes.items()):
        values.sort()
        if len({row[0] for row in values}) != len(values):
            raise GuardianError("Cap waktu RSS ganda dalam instance.")
        part = values[-200:]
        slope = None
        if len(part) >= floor:
            slopes = [Fraction((second[1] - first[1]) * 3600, int((second[0] - first[0]).total_seconds()))
                      for i, first in enumerate(part) for second in part[i + 1:]]
            slope = median(slopes)
        gain = part[-1][1] - part[0][1]
        reason = "insufficient" if slope is None else "suspected_leak" if slope >= threshold and gain >= min_gain else "no_signal"
        report.append({"instance": key, "status": reason, "samples": len(part), "omitted": len(values) - len(part),
                       "slope": str(slope) if slope is not None else None, "gain_mib": gain,
                       "sources": [row[2] for row in part]})
    return {"instances": report}

if __name__ == "__main__":
    raise SystemExit(cli(detect, __doc__))
