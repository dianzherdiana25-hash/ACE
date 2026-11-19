"""Orkestrator saringan direktur (director screen) terpadu berbasis snapshot Git (E2).

Mengapa modul ini dibuat: sebelumnya `director_asset_check`, `director_value_check`,
dan `director_cycle_record` berjalan terpisah sebagai CLI individual tanpa satu
vonis akhir yang teragregasi. Modul ini menyatukan ketiganya pada satu objek
`GitSnapshot` read-only yang dipaku pada revisi commit tertentu agar produk/laporan
mendapat satu verdict deterministik (`LOLOS`, `LOLOS-DENGAN-PERBAIKAN`, atau `TOLAK`)
beserta daftar temuan yang dapat langsung ditindaklanjuti.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools._director_sources import GitSnapshot, SourceError
from tools.director_asset_check import verify_assets
from tools.director_cycle_record import record_cycles
from tools.director_value_check import verify_values


DIRECTOR_SCREEN_SCHEMA = "ace.director-screen.v1"
VERDICT_PASS = "LOLOS"
VERDICT_PASS_WITH_FIXES = "LOLOS-DENGAN-PERBAIKAN"
VERDICT_REJECT = "TOLAK"

_ASSET_BLOCKER_STATUSES = {"not_found"}
_ASSET_REPAIR_STATUSES = {"ambiguous"}
_VALUE_BLOCKER_STATUSES = {"mismatch", "not_found"}
_VALUE_REPAIR_STATUSES = {"ambiguous"}


def _asset_remediation(row: dict[str, Any]) -> str:
    kind = str(row.get("kind", "aset"))
    target = str(row.get("target", ""))
    status = str(row.get("status", ""))
    if status == "not_found":
        return f"Hapus rujukan {kind} `{target}` atau lengkapi berkas/simbol nyata di commit acuan."
    if status == "ambiguous":
        if kind == "pr":
            return f"Lampirkan berkas `--pr-snapshot` atau gunakan URL PR penuh untuk `{target}`."
        return f"Perjelas path penuh untuk target ambigu {kind} `{target}`."
    return "Periksa ulang rujukan aset terkait."


def _value_remediation(row: dict[str, Any]) -> str:
    label = str(row.get("label", "klaim"))
    status = str(row.get("status", ""))
    if status == "mismatch":
        return (
            f"Selaraskan nilai klaim `{label}` dengan bukti sumber "
            f"(terukur={row.get('observed')!r}, tertulis={row.get('claimed', row.get('value'))!r})."
        )
    if status == "not_found":
        return f"Perbaiki path `source` atau `pointer` untuk klaim numerik `{label}` agar menunjuk fakta valid."
    if status == "ambiguous":
        return f"Pastikan tipe nilai pada `source` untuk klaim `{label}` tidak ambigu (mis. bool vs int)."
    return f"Validasi ulang klaim numerik `{label}`."


def _cycle_remediation(issue: str, cycle_id: Any, source: str) -> str:
    if issue == "missing_origin":
        return f"Tambahkan field `origin` eksplisit pada catatan siklus `{cycle_id}` ({source})."
    if issue == "missing_decisions":
        return f"Cantumkan daftar `decisions` eksplisit pada catatan siklus `{cycle_id}` ({source})."
    return f"Lengkapi metadata siklus `{cycle_id}` pada `{source}` untuk temuan `{issue}`."


def screen_product(
    snapshot: GitSnapshot,
    product_path: str,
    *,
    pr_snapshot_path: str | None = None,
    cycle_paths: Sequence[str] | None = None,
    allow_empty: bool = False,
) -> dict[str, Any]:
    """Jalankan saringan aset, nilai numerik, dan catatan siklus dalam satu verdict."""
    try:
        asset_report = verify_assets(snapshot, product_path, pr_snapshot_path=pr_snapshot_path)
    except SourceError as exc:
        if product_path.lower().endswith(".json") and "perlu daftar assets" in str(exc):
            asset_report = {"commit": snapshot.commit, "assets": [], "skipped": "no_assets_field"}
        else:
            raise

    try:
        value_report = verify_values(snapshot, product_path)
    except SourceError as exc:
        if product_path.lower().endswith(".json") and "perlu daftar numeric_claims" in str(exc):
            value_report = {"commit": snapshot.commit, "claims": [], "skipped": "no_numeric_claims_field"}
        else:
            raise

    cycle_report = record_cycles(snapshot, list(cycle_paths)) if cycle_paths else None

    findings: list[dict[str, Any]] = []
    blockers = 0
    improvements = 0

    asset_rows = asset_report.get("assets", [])
    for row in asset_rows:
        status = str(row.get("status", ""))
        if status == "verified":
            continue
        severity = "blocker" if status in _ASSET_BLOCKER_STATUSES else "improvement"
        if severity == "blocker":
            blockers += 1
        else:
            improvements += 1
        findings.append(
            {
                "check": "asset",
                "severity": severity,
                "location": row.get("location", ""),
                "target": f"{row.get('kind', '')}:{row.get('target', '')}",
                "status": status,
                "remediation": _asset_remediation(row),
            }
        )

    claim_rows = value_report.get("claims", [])
    for row in claim_rows:
        status = str(row.get("status", ""))
        if status == "verified":
            continue
        severity = "blocker" if status in _VALUE_BLOCKER_STATUSES else "improvement"
        if severity == "blocker":
            blockers += 1
        else:
            improvements += 1
        findings.append(
            {
                "check": "value",
                "severity": severity,
                "location": row.get("location", ""),
                "target": str(row.get("label", "")),
                "status": status,
                "observed": row.get("observed"),
                "remediation": _value_remediation(row),
            }
        )

    cycle_rows = cycle_report.get("cycles", []) if cycle_report is not None else []
    for cyc in cycle_rows:
        issues = cyc.get("issues") or []
        source = str(cyc.get("source", ""))
        cid = cyc.get("cycle")
        for issue in issues:
            improvements += 1
            findings.append(
                {
                    "check": "cycle",
                    "severity": "improvement",
                    "location": source,
                    "target": f"cycle:{cid}",
                    "status": str(issue),
                    "remediation": _cycle_remediation(str(issue), cid, source),
                }
            )

    total_checked = len(asset_rows) + len(claim_rows) + len(cycle_rows)
    if total_checked == 0 and not allow_empty:
        blockers += 1
        findings.append(
            {
                "check": "screen",
                "severity": "blocker",
                "location": product_path,
                "target": "verifiable_claims",
                "status": "empty_screen_no_verifiable_items",
                "remediation": "Tambahkan rujukan aset, klaim numerik, atau catatan siklus agar produk dapat diverifikasi.",
            }
        )

    if blockers > 0:
        verdict = VERDICT_REJECT
    elif improvements > 0:
        verdict = VERDICT_PASS_WITH_FIXES
    else:
        verdict = VERDICT_PASS

    return {
        "schema": DIRECTOR_SCREEN_SCHEMA,
        "commit": snapshot.commit,
        "product": product_path,
        "verdict": verdict,
        "summary": {
            "assets_checked": len(asset_rows),
            "assets_verified": sum(1 for r in asset_rows if r.get("status") == "verified"),
            "claims_checked": len(claim_rows),
            "claims_verified": sum(1 for r in claim_rows if r.get("status") == "verified"),
            "cycles_checked": len(cycle_rows),
            "cycles_clean": sum(1 for c in cycle_rows if not c.get("issues")),
            "blocker_count": blockers,
            "improvement_count": improvements,
            "total_findings": len(findings),
        },
        "findings": findings,
        "asset_report": asset_report,
        "value_report": value_report,
        "cycle_report": cycle_report,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Saringan Direktur ACE",
        "",
        f"- Produk: `{report['product']}`",
        f"- Commit Git: `{report['commit']}`",
        f"- Verdict: **{report['verdict']}**",
        f"- Ringkasan: aset {s['assets_verified']}/{s['assets_checked']}, "
        f"klaim numerik {s['claims_verified']}/{s['claims_checked']}, "
        f"siklus bersih {s['cycles_clean']}/{s['cycles_checked']} "
        f"(blocker={s['blocker_count']}, perbaikan={s['improvement_count']})",
        "",
    ]
    if report["findings"]:
        lines.extend(
            [
                "## Temuan & Tindak Lanjut",
                "",
                "| Pemeriksaan | Tingkat | Lokasi | Target | Status | Tindakan |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in report["findings"]:
            lines.append(
                f"| `{item['check']}` | `{item['severity']}` | `{item['location']}` | "
                f"`{item['target']}` | `{item['status']}` | {item['remediation']} |"
            )
    else:
        lines.append("Semua rujukan aset, klaim numerik, dan catatan siklus terverifikasi bersih.")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Saringan direktur terpadu terhadap snapshot Git: aset, nilai numerik, dan siklus."
    )
    parser.add_argument("product", help="Path relatif produk (.json atau .md) di dalam repo Git.")
    parser.add_argument("--repo", type=Path, default=Path("."), help="Direktori repo Git (default: .)")
    parser.add_argument("--revision", default="HEAD", help="Revisi Git acuan (default: HEAD)")
    parser.add_argument("--pr-snapshot", default=None, help="Path relatif JSON snapshot PR opsional")
    parser.add_argument("--cycle", dest="cycles", action="append", default=None, help="Path relatif JSON catatan siklus (dapat diulang)")
    parser.add_argument("--allow-empty", action="store_true", help="Izinkan produk tanpa satupun rujukan/klaim/siklus")
    parser.add_argument("--strict", action="store_true", help="Kembalikan exit code 1 juga untuk verdict LOLOS-DENGAN-PERBAIKAN")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        snapshot = GitSnapshot(args.repo, revision=args.revision)
        report = screen_product(
            snapshot,
            args.product,
            pr_snapshot_path=args.pr_snapshot,
            cycle_paths=args.cycles,
            allow_empty=bool(args.allow_empty),
        )
    except (SourceError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    verdict = report["verdict"]
    if verdict == VERDICT_REJECT:
        return 1
    if verdict == VERDICT_PASS_WITH_FIXES and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
