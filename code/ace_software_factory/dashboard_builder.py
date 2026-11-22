"""Susun dasbor analitik dari snapshot metrik, dengan jejak ke tiap angka.

Jumlah dan pembanding dihitung dari nilai integer dalam dua periode
UTC. Bar visual memakai maksimum bersama per metrik. Sel tetap
memuat angka dan flag bukti hilang agar bisa dibaca tanpa grafik.
"""
import argparse
from collections import defaultdict
from datetime import date
from hashlib import sha256
from html import escape
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


def _date(value, label):
    if not isinstance(value, str) or len(value) != 10:
        raise ContractError(f"{label} perlu YYYY-MM-DD.")
    converted = date.fromisoformat(value)
    if converted.isoformat() != value:
        raise ContractError(f"{label} perlu YYYY-MM-DD kanonis.")
    return converted


def _period(raw):
    obj(raw, ("start", "end"))
    start, end = (_date(raw[key], key) for key in ("start", "end"))
    if start > end or (end-start).days > 730:
        raise ContractError("Periode terbalik atau terlalu panjang.")
    return start, end


def _labels(rows, label):
    result = {}
    for row in entries(rows, 64, minimum=1):
        obj(row, ("id", "label", "source_ref"))
        key = identifier(row["id"], label)
        if key in result:
            raise ContractError(f"{label} ganda.")
        result[key] = (text(row["label"], label, 120), text(row["source_ref"], "Rujukan label", 200))
    return result


CSS = """
:root{color:#172734;background:#f3f7fb;font:100%/1.5 system-ui,sans-serif}
body{margin:0}main{max-width:72rem;margin:auto;padding:clamp(1rem,4vw,3rem)}
h1{font-size:clamp(2rem,5vw,3.8rem);letter-spacing:-.045em;margin:0}h2{margin-top:2rem}
table{width:100%;border-collapse:collapse;text-align:left;background:white;border-radius:.5rem}
th,td{padding:.75rem;border-bottom:1px solid #d9e4ee}
meter{display:block;width:min(11rem,100%)}.overflow{overflow-x:auto}caption{text-align:left;padding:.5rem}
.paths{font-size:.92rem;color:#3e5363}
""".strip()


def _render(report):
    lines = [f"<!doctype html><html lang='id'><head><meta charset='utf-8'><title>{escape(report['title'])}</title>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<link rel='stylesheet' href='dashboard.css'></head><body><main>",
             f"<h1>{escape(report['title'])}</h1>",
             f"<p>{escape(report['periods']['target']['start'])} – {escape(report['periods']['target']['end'])}</p>"]
    for metric in report["metrics"]:
        name = escape(metric["label"])
        lines.extend([f"<section><h2>{name}</h2><div class='overflow'><table><caption>Perbandingan {name}</caption>",
                      "<thead><tr><th scope='col'>Kelompok</th><th scope='col'>Periode ini</th>",
                      "<th scope='col'>Pembanding</th><th scope='col'>Selisih</th></tr></thead><tbody>"])
        for row in metric["groups"]:
            current = row["target"] if row["target"] is not None else "TIDAK TAHU"
            previous = row["baseline"] if row["baseline"] is not None else "TIDAK TAHU"
            delta = f"{row['delta']:+d}" if row["delta"] is not None else "TIDAK TAHU"
            label = escape(row["group_label"])
            bar = (f"<meter aria-label='{label} periode ini' min='0' max='{metric['scale']}' value='{current}'>{current}</meter>"
                   if row["target"] is not None and metric["scale"] > 0 else "")
            lines.append(f"<tr><th scope='row'>{label}</th><td>{current}{bar}</td><td>{previous}</td><td>{delta}</td></tr>")
        lines.append(f"</tbody></table></div><p class='paths'>Definisi {escape(metric['source_ref'])}.</p></section>")
    lines.extend([f"<p class='paths'>Sumber snapshot {escape(report['source_ref'])} · "
                  f"<code>{report['snapshot_sha256']}</code>.</p></main></body></html>"])
    return ("\n".join(lines)+"\n").encode()


def build(plan, snapshot, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-dashboard-plan.v1", ("title", "snapshot_sha256", "target", "baseline", "metrics", "groups"))
    checked(snapshot, plan["snapshot_sha256"])
    schema(snapshot, "ace.factory-dashboard-snapshot.v1", ("source_ref", "observations"))
    title = text(plan["title"], "Judul dasbor", 110)
    source = text(snapshot["source_ref"], "Rujukan snapshot", 200)
    start, end = _period(plan["target"])
    base_start, base_end = _period(plan["baseline"])
    if base_end >= start:
        raise ContractError("Periode pembanding harus selesai sebelum periode target.")
    metrics, groups = _labels(plan["metrics"], "Metrik"), _labels(plan["groups"], "Kelompok")
    partitions = defaultdict(list)
    visited = set()
    for row in entries(snapshot["observations"], 10_000):
        obj(row, ("id", "metric", "group", "date", "value", "source_ref"))
        key = identifier(row["id"], "ID observasi")
        metric, group = identifier(row["metric"], "Metrik"), identifier(row["group"], "Kelompok")
        if key in visited or metric not in metrics or group not in groups:
            raise ContractError("Observasi ganda, atau kelompok dan metrik tidak dikenal.")
        visited.add(key)
        day = _date(row["date"], "Tanggal observasi")
        value = integer(row["value"], "Nilai observasi", 0, 10**9)
        ref = text(row["source_ref"], "Rujukan observasi", 220)
        if start <= day <= end:
            partitions[(metric, group, "target")].append((key, value, ref))
        elif base_start <= day <= base_end:
            partitions[(metric, group, "baseline")].append((key, value, ref))

    computed = []
    for metric, (label, ref) in sorted(metrics.items()):
        items = []
        peak = 0
        for group, (group_label, _) in sorted(groups.items()):
            values = {"group": group, "group_label": group_label, "evidence": {}}
            for period in ("target", "baseline"):
                observed = sorted(partitions[(metric, group, period)])
                total = sum(entry[1] for entry in observed) if observed else None
                values[period] = total
                values["evidence"][period] = [{"id": entry[0], "source_ref": entry[2]} for entry in observed]
                if total is not None:
                    peak = max(peak, total)
            values["delta"] = (values["target"] - values["baseline"]) if (
                values["target"] is not None and values["baseline"] is not None) else None
            items.append(values)
        computed.append({"id": metric, "label": label, "source_ref": ref, "scale": peak, "groups": items})
    report = {"schema": "ace.factory-dashboard-report.v1", "title": title, "plan_sha256": expected,
              "snapshot_sha256": plan["snapshot_sha256"], "source_ref": source, "observations": len(visited),
              "periods": {key: plan[key] for key in ("target", "baseline")}, "metrics": computed}
    page = _render(report)
    report["html_sha256"] = sha256(page).hexdigest()
    return {"index.html": page, "dashboard.css": (CSS+"\n").encode(),
            "dashboard_data.json": canonical(report)+b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("plan", "snapshot", "output"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        output, report = build(decode(read(args.plan)), decode(read(args.snapshot)), args.expect_sha256)
        materialize(args.output, output)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
