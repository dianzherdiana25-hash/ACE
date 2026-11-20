"""Audit kelengkapan rentang EVO (dokumen desain & file bukti tonggak) (AG57).

Memindai pohon direktori repositori atau fixture secara read-only untuk rentang
nomor EVO (mis. ``0017`` s.d. ``0029``), memeriksa keberadaan dokumen desain,
mengecek referensi file bukti di bawah ``evidence/`` yang disebut di dalam
dokumen desain, lalu merakit tabel kelengkapan ``complete`` / ``partial`` / ``missing``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.evo-range-audit.v1"
_EVIDENCE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(evidence/[A-Za-z0-9_./-]+\.(?:json|jsonl|md|txt|log|csv|py))"
)


def _match_design_docs(docs_dir: Path, code4: str) -> list[Path]:
    if not docs_dir.is_dir():
        return []
    code_re = re.compile(rf"(?<!\d){re.escape(code4)}(?!\d)")
    matched: list[Path] = []
    for child in sorted(docs_dir.rglob("*.md")):
        if not child.is_file():
            continue
        stem_upper = child.stem.upper()
        if code_re.search(child.stem) and (
            "EVO" in stem_upper
            or "RANCANGAN" in stem_upper
            or "DESAIN" in stem_upper
            or "PREREGISTRASI" in stem_upper
            or "PRAREGISTRASI" in stem_upper
        ):
            matched.append(child)
    return matched


def _extract_referenced_evidence(doc_paths: Sequence[Path]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for doc in doc_paths:
        text = doc.read_text(encoding="utf-8", errors="replace")
        for match in _EVIDENCE_REF_RE.finditer(text):
            rel = match.group(1).strip()
            if rel not in seen:
                seen.add(rel)
                refs.append(rel)
    return refs


def audit_evo_range(
    root_dir: Path,
    start_num: int,
    end_num: int,
    *,
    docs_subdir: str = "handover",
) -> dict[str, Any]:
    """Audit keberadaan dokumen desain dan file bukti tereferensi pada rentang EVO."""
    if start_num < 0 or end_num < start_num:
        raise ValueError(f"Rentang EVO tidak sah: {start_num}..{end_num}")

    root = Path(root_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Direktori root tidak ditemukan: {root}")
    docs_dir = root / docs_subdir if (root / docs_subdir).is_dir() else root

    rows: list[dict[str, Any]] = []
    complete_evos: list[str] = []
    partial_evos: list[str] = []
    missing_evos: list[str] = []

    for num in range(start_num, end_num + 1):
        code4 = f"{num:04d}"
        evo_label = f"EVO-{code4}"
        docs = _match_design_docs(docs_dir, code4)
        rel_docs = [doc.relative_to(root).as_posix() for doc in docs]

        if not docs:
            status = "missing"
            referenced: list[str] = []
            present_refs: list[str] = []
            missing_refs: list[str] = []
            missing_evos.append(evo_label)
        else:
            referenced = _extract_referenced_evidence(docs)
            present_refs = [rel for rel in referenced if (root / rel).is_file()]
            missing_refs = [rel for rel in referenced if not (root / rel).is_file()]
            if referenced and not missing_refs:
                status = "complete"
                complete_evos.append(evo_label)
            else:
                status = "partial"
                partial_evos.append(evo_label)

        rows.append(
            {
                "evo": evo_label,
                "number": num,
                "status": status,
                "design_docs": rel_docs,
                "referenced_evidence": referenced,
                "existing_evidence": present_refs,
                "missing_evidence": missing_refs,
            }
        )

    return {
        "schema": SCHEMA,
        "root": str(root),
        "range": {"start": f"{start_num:04d}", "end": f"{end_num:04d}"},
        "summary": {
            "total_evos": len(rows),
            "complete_count": len(complete_evos),
            "partial_count": len(partial_evos),
            "missing_count": len(missing_evos),
            "complete_evos": complete_evos,
            "partial_evos": partial_evos,
            "missing_evos": missing_evos,
        },
        "rows": rows,
    }


def render_markdown_table(report: Mapping[str, Any]) -> str:
    """Render tabel kelengkapan rentang EVO dalam format Markdown."""
    rng = report["range"]
    summary = report["summary"]
    lines = [
        f"# Audit Kelengkapan Rentang EVO {rng['start']}–{rng['end']}",
        "",
        f"- Total EVO: {summary['total_evos']}",
        f"- Complete: {summary['complete_count']} | Partial: {summary['partial_count']} | Missing: {summary['missing_count']}",
        "",
        "| EVO | Status | Dokumen Desain | Bukti Ada | Bukti Hilang |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        docs = ", ".join(row["design_docs"]) if row["design_docs"] else "-"
        ok_cnt = f"{len(row['existing_evidence'])}/{len(row['referenced_evidence'])}"
        miss = ", ".join(row["missing_evidence"]) if row["missing_evidence"] else "-"
        lines.append(
            f"| {row['evo']} | {row['status']} | {docs} | {ok_cnt} | {miss} |"
        )
    return "\n".join(lines) + "\n"


def _parse_evo_num(raw: str) -> int:
    cleaned = raw.strip().upper().replace("EVO-", "").replace("EVO_", "").replace("EVO", "")
    val = int(cleaned)
    if val < 0:
        raise ValueError(f"Nomor EVO tidak boleh negatif: {raw!r}")
    return val


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit kelengkapan dokumen desain dan bukti tonggak dalam rentang EVO."
    )
    parser.add_argument("--root", required=True, help="Direktori root repo/fixture.")
    parser.add_argument("--start", required=True, help="Nomor EVO awal (mis. 0017).")
    parser.add_argument("--end", required=True, help="Nomor EVO akhir (mis. 0029).")
    parser.add_argument("--docs-subdir", default="handover", help="Subdirektori dokumen desain.")
    parser.add_argument("--out-json", help="Tulis output JSON ke path ini.")
    parser.add_argument("--out-md", help="Tulis tabel Markdown ke path ini.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format stdout jika --out-json/--out-md tidak dipakai.",
    )
    args = parser.parse_args(argv)

    try:
        start_num = _parse_evo_num(args.start)
        end_num = _parse_evo_num(args.end)
        report = audit_evo_range(
            Path(args.root),
            start_num,
            end_num,
            docs_subdir=args.docs_subdir,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown_table(report)

    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_text, encoding="utf-8")
    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md_text, encoding="utf-8")
    if not args.out_json and not args.out_md:
        sys.stdout.write(json_text if args.format == "json" else md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
