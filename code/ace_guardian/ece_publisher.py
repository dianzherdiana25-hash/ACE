"""Rakit keluaran lokal ECE per domain dari resolusi ledger, termasuk domain tanpa sampel yang cukup."""
from ._contracts import GuardianError, anchor, cli, identifier, identity, items, schema
from .calibration_scorer import score
from .confidence_ledger import ledger

FIELDS = ("id", "domain", "confidence_bp", "observed", "resolved_ref")

def build_report(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.ece-report.v1", ("calibration_ledger", "bins", "minimum", "domains"))
    entries = ledger(plan["calibration_ledger"], identity(plan["calibration_ledger"]))
    requested = {identifier(value, "Domain") for value in items(plan["domains"], 150, 1)}
    unseen = {row["domain"] for row in entries["completed"] + entries["pending"]} - requested
    if unseen:
        raise GuardianError("Ledger ECE berisi domain yang tidak tercatat di permintaan.")
    settings = {"schema": "ace.guardian.calibration.v1", "rows": [
        {name: row[name] for name in FIELDS} for row in entries["completed"]],
        "bins": plan["bins"], "minimum": plan["minimum"]}
    scored = score(settings, identity(settings))
    summaries = []
    for domain in sorted(requested):
        result = scored["domains"].get(domain, {})
        summaries.append({"domain": domain, "samples": result.get("samples", 0), "ece": result.get("ece"),
                          "brier": result.get("brier"), "resolution_refs": result.get("sources", []),
                          "pending": sum(row["domain"] == domain for row in entries["pending"])})
    note = ["# Kalibrasi per domain", "", "| Domain | Sampel | ECE |", "| --- | ---: | ---: |"]
    for item in summaries:
        note.append(f"| {item['domain']} | {item['samples']} | {item['ece'] if item['ece'] is not None else 'belum terukur'} |")
    return {"domains": summaries, "method": scored["method"], "ledger_sha256": entries["head_sha256"],
            "bin_count": scored["bin_count"], "markdown": "\n".join(note) + "\n"}

if __name__ == "__main__":
    raise SystemExit(cli(build_report, __doc__))
