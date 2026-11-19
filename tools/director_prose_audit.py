#!/usr/bin/env python3
"""Audit dan petakan bentuk klaim prosa historis pada artefak direktur ACE."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re

if __package__:
    from ._director_sources import GitSnapshot, SourceError, write_json
    from .director_asset_check import verify_assets
else:
    from _director_sources import GitSnapshot, SourceError, write_json
    from director_asset_check import verify_assets


PROSE_AUDIT_SCHEMA = "ace.director.prose-audit.v1"

# Approved structured prose shapes extracted deterministically (outside code blocks):
# 1) key=value numeric assignments (outside URLs/query strings)
_KV_METRIC_RE = re.compile(
    r"(?<![/\w.-])(?P<label>[A-Za-z][A-Za-z0-9_]{0,63})\s*=\s*(?P<value>-?\d+(?:\.\d+)?)(?![\w/-]|\.\d)"
)
# 2) pass/count ratio N/M with optional '= R' or '(P%)'
_RATIO_RE = re.compile(
    r"(?<![/\w.-])(?P<num>\d+)\s*/\s*(?P<den>[1-9]\d*)(?![\w/-]|\.\d)"
    r"(?:\s*=\s*(?P<eq>-?\d+(?:\.\d+)?)(?![\w/-]|\.\d)|\s*\((?P<pct>\d+(?:\.\d+)?)%\))?"
)
# 3) percentage / compression multiplier metrics
_PCT_MULT_RE = re.compile(
    r"(?<![/\w.-])(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>%|x)(?=\s|[.,;)*`]|$)"
)
# 4) Markdown pipe table row separator / data rows
_TABLE_SEP_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
# 5) Backticked SHA digests or ALL_CAPS status constants previously misread as modules
_STATUS_OR_SHA_RE = re.compile(r"`([0-9a-f]{7,64}|[A-Z][A-Z0-9_]{2,})`")

# Exclude pure headings/separators/dates/structured `- claim: {...}` lines from unrecognized numeric noise
_STRUCTURED_CLAIM_RE = re.compile(r"^\s*[-*]\s+claim:\s*\{.*\}\s*$")
_ISO_DATE_OR_PR_RE = re.compile(r"(?:\b20\d{2}-\d{2}-\d{2}\b|#\d+|PR\s*#\d+|\b\d+(?:\.\d+)?s\b)")
_ANY_NUMBER_RE = re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?(?![A-Za-z_])")


def _clean_cell(text: str) -> str:
    return text.strip().strip("*` ")


def audit_historical_prose(markdown: str, *, product_path: str = "historical.md") -> dict:
    """Petakan klaim prosa terstruktur yang disetujui vs baris angka/klaim yang belum dikenali."""
    approved_claims: list[dict] = []
    unrecognized_prose: list[dict] = []
    symbol_tokens: list[dict] = []

    fence = None
    lines = markdown.splitlines()
    for line_no, raw_line in enumerate(lines, 1):
        fence_match = _FENCE_RE.match(raw_line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue

        stripped = raw_line.strip()
        if not stripped or _STRUCTURED_CLAIM_RE.match(raw_line) or _TABLE_SEP_RE.match(raw_line):
            continue

        location = f"L{line_no}"
        for tok in _STATUS_OR_SHA_RE.finditer(raw_line):
            val = tok.group(1)
            kind = "hex_digest" if re.fullmatch(r"[0-9a-f]{7,64}", val) else "status_constant"
            symbol_tokens.append({"location": location, "kind": kind, "token": val})

        # Strip URLs, markdown link targets, filenames, and hex hashes before matching numeric metrics
        scan_line = re.sub(r"https?://\S+", " ", raw_line)
        scan_line = re.sub(r"\]\([^)]+\)", "]()", scan_line)
        scan_line = re.sub(r"\b[0-9a-f]{7,64}\b", " ", scan_line)
        scan_line = re.sub(r"\b[\w./-]+?\.(?:py|md|jsonl?|json\.gz|csv|txt|sh|log|gz)\b", " ", scan_line)

        matched_spans: list[tuple[int, int]] = []
        line_claims: list[dict] = []

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [_clean_cell(c) for c in stripped.strip("|").split("|")]
            if cells and not all(c.lower() in {"subsystem / metric", "measured output", "lengan", "code", "language", "total", "objek"} for c in cells):
                row_label = cells[0]
                for col_idx, cell in enumerate(cells[1:], 1):
                    cell_matched = False
                    for r_m in _RATIO_RE.finditer(cell):
                        cell_matched = True
                        num, den = int(r_m.group("num")), int(r_m.group("den"))
                        item = {
                            "location": f"{location}:C{col_idx + 1}",
                            "shape": "ratio_claim",
                            "label": row_label,
                            "numerator": num,
                            "denominator": den,
                            "value": f"{num}/{den}",
                        }
                        if r_m.group("eq") is not None:
                            item["stated_decimal"] = r_m.group("eq")
                        if r_m.group("pct") is not None:
                            item["stated_percent"] = r_m.group("pct")
                        line_claims.append(item)
                    if not cell_matched and re.fullmatch(r"\d+(?:\.\d+)?(?:\s*(?:Modules?|s|%|x))?", cell):
                        line_claims.append({
                            "location": f"{location}:C{col_idx + 1}",
                            "shape": "table_numeric_cell",
                            "label": row_label,
                            "value": cell,
                        })
                if line_claims:
                    approved_claims.extend(line_claims)
                    continue

        for m in _KV_METRIC_RE.finditer(scan_line):
            matched_spans.append(m.span())
            line_claims.append({
                "location": location,
                "shape": "kv_metric_claim",
                "label": m.group("label"),
                "value": m.group("value"),
            })

        for m in _RATIO_RE.finditer(scan_line):
            matched_spans.append(m.span())
            num, den = int(m.group("num")), int(m.group("den"))
            item = {
                "location": location,
                "shape": "ratio_claim",
                "numerator": num,
                "denominator": den,
                "value": f"{num}/{den}",
            }
            if m.group("eq") is not None:
                item["stated_decimal"] = m.group("eq")
            if m.group("pct") is not None:
                item["stated_percent"] = m.group("pct")
            line_claims.append(item)

        for m in _PCT_MULT_RE.finditer(scan_line):
            # Skip if already inside a matched ratio span
            if any(s <= m.start() and m.end() <= e for s, e in matched_spans):
                continue
            matched_spans.append(m.span())
            line_claims.append({
                "location": location,
                "shape": "percent_or_multiplier_claim",
                "value": m.group("value"),
                "unit": m.group("unit"),
            })

        if line_claims:
            approved_claims.extend(line_claims)
            continue

        # Check whether the remaining free-form prose carries unparsed numeric claims (excluding dates/PRs/headings/lists)
        if not stripped.startswith("#"):
            residue = re.sub(r"^\s*\d+\.\s+", " ", scan_line)
            residue = _ISO_DATE_OR_PR_RE.sub(" ", residue)
            residue = re.sub(r"\b\d{2}:\d{2}(?::\d{2})?\b", " ", residue)
            residue = re.sub(r"\b(?:v\d+|EVO[-_\s]*\d+|Stage[-_\s]*\d+|Phase[-_\s]*\d+|Loop[-_\s]*\d+|WS[-_\s]*\d+|G\d+|E\d+|F\d+|R\d+|§\d+|ho-code-\d+|ep-code-\d+)\b", " ", residue, flags=re.IGNORECASE)
            nums = _ANY_NUMBER_RE.findall(residue)
            if nums:
                unrecognized_prose.append({
                    "location": location,
                    "shape": "unrecognized_prose",
                    "reason": "free_form_prose_numeric_without_approved_shape",
                    "numbers": nums[:6],
                    "excerpt": stripped[:160],
                })

    shape_counts = Counter(item["shape"] for item in approved_claims)
    return {
        "schema": PROSE_AUDIT_SCHEMA,
        "product": product_path,
        "summary": {
            "approved_claims_count": len(approved_claims),
            "unrecognized_prose_count": len(unrecognized_prose),
            "symbol_tokens_count": len(symbol_tokens),
            "counts_by_shape": {k: shape_counts[k] for k in sorted(shape_counts)},
        },
        "approved_claims": approved_claims,
        "unrecognized_prose": unrecognized_prose,
        "symbol_tokens": symbol_tokens,
    }


def audit_historical_artifact(repo: GitSnapshot, product_path: str, *, pr_snapshot_path: str | None = None) -> dict:
    """Jalankan audit prosa + audit aset GitSnapshot pada satu dokumen historis."""
    markdown = repo.read_text(product_path)
    prose = audit_historical_prose(markdown, product_path=product_path)
    assets = verify_assets(repo, product_path, pr_snapshot_path=pr_snapshot_path)
    asset_statuses = Counter(row["status"] for row in assets["assets"])
    return {
        **prose,
        "commit": repo.commit,
        "asset_summary": {
            "total": len(assets["assets"]),
            "counts_by_status": {k: asset_statuses[k] for k in sorted(asset_statuses)},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", help="Path dokumen Markdown historis dalam commit Git.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--pr-snapshot", help="Path snapshot PR offline dalam commit.")
    args = parser.parse_args(argv)
    try:
        result = audit_historical_artifact(
            GitSnapshot(args.repo, args.revision),
            args.product,
            pr_snapshot_path=args.pr_snapshot,
        )
    except SourceError as exc:
        parser.exit(2, f"Error. {exc}\n")
    write_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
