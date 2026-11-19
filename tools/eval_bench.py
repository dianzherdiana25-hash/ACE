#!/usr/bin/env python3
"""Bench evaluasi berdiri (Garis B4).

Menyediakan tiga bench evaluasi offline dalam satu harness:
(a) Bench tanya-jawab introspektif atas fakta `handover/` — setiap jawaban
    WAJIB membawa pointer berkas sumber yang sah; jawaban tanpa pointer atau
    pointer tidak ada ditolak.
(b) Bench konsistensi lintas organ atas berkas hasil yang ada (offline) —
    menghasilkan laporan ketidaksepakatan antar-organ/arm/run beserta tingkat
    kesepakatan berpasangan.
(c) Bench regresi format — mendeteksi perubahan bentuk keluaran perkakas
    program yang tidak disengaja terhadap kontrak skema/kunci/tipe/tabel.

Perkakas ini baca-saja terhadap arsip repo dan BUKAN instrumen verdict EVO.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable

from tools import bench_table, corpus_lint, corpus_registry, opportunity_register, ruleset_readiness, screen_census

EVAL_BENCH_SCHEMA = "ace.standalone-eval-bench.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]

_WORD_RE = re.compile(r"[0-9a-zA-ZÀ-ÖØ-öø-ÿ_#.-]{2,}")
_PATH_PTR_RE = re.compile(r"([A-Za-z0-9_./-]+\.md)")


class EvalBenchError(ValueError):
    """Kesalahan argumen, berkas masukan, atau fixture bench evaluasi."""


# ---------------------------------------------------------------------------
# (a) Bench Tanya-Jawab Introspektif atas Fakta Handover
# ---------------------------------------------------------------------------

DEFAULT_HANDOVER_QA_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "id": "qa-evo0006-verdict",
        "question": "Apa vonis pada konsolidasi EVO 0006 2026-11-17 dan apa penyebabnya?",
        "expected_sources": ["handover/EVO_0006_KONSOLIDASI_20261117.md"],
        "expected_terms": ["INSTRUMEN_TIDAK_CUKUP", "probe set"],
    },
    {
        "id": "qa-evo0005-prereg",
        "question": "PR berapa preregistrasi dan mesin untuk EVO 0005 konsolidasi?",
        "expected_sources": ["handover/EVO_0005_KONSOLIDASI_20261116.md"],
        "expected_terms": ["#247", "#246"],
    },
    {
        "id": "qa-governance-rules",
        "question": "Kapan aturan tata kelola tetap ACE dicatat dan berapa jumlah aturan tetap programnya?",
        "expected_sources": ["handover/GOVERNANCE_RULES_20261115.md"],
        "expected_terms": ["15 November 2026", "Dua aturan tetap"],
    },
)


_QA_STOPWORDS = frozenset({"apa", "siapa", "kapan", "berapa", "bagaimana", "mana", "yang", "dan", "atau", "untuk", "dengan", "pada", "dari", "di", "ke", "ace", "ini", "itu", "program", "programnya", "penyebabnya", "jumlah"})


def solve_introspective_question(
    question: str,
    handover_dir: Path,
    *,
    rel_prefix: str = "handover",
) -> dict[str, Any]:
    """Solver ekstraktif deterministik baca-saja atas berkas Markdown `handover/`."""
    if not handover_dir.is_dir():
        raise EvalBenchError(f"Direktori handover tidak ditemukan: {handover_dir}")
    docs = sorted(p for p in handover_dir.glob("*.md") if p.is_file())
    if not docs:
        raise EvalBenchError(f"Tidak ada berkas .md di '{handover_dir}'.")

    raw_tokens = {t.lower().rstrip("nya") if len(t) > 5 and t.lower().endswith("nya") else t.lower() for t in _WORD_RE.findall(question)}
    q_tokens = {t for t in raw_tokens if len(t) >= 2 and t not in _QA_STOPWORDS}
    if not q_tokens:
        q_tokens = raw_tokens

    best_score = -1.0
    best_doc: Path | None = None
    best_snippet = ""

    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        title_line = lines[0] if lines else ""
        head_block = "\n".join(lines[:12]).lower()
        name_tokens = {t.lower() for t in _WORD_RE.findall(doc.stem.replace("_", " "))}
        doc_tokens = set(_WORD_RE.findall(text.lower()))

        doc_distinct_hits = len(q_tokens & doc_tokens)
        head_distinct_hits = sum(1 for tok in q_tokens if tok in head_block)
        name_hits = len(q_tokens & name_tokens)

        best_ln = title_line
        best_ln_hits = -1
        for i, _ in enumerate(lines[:40]):
            window_text = " ".join(lines[max(0, i - 1) : min(len(lines), i + 4)])
            w_low = window_text.lower()
            whits = sum(1 for tok in q_tokens if tok in w_low)
            if whits > best_ln_hits:
                best_ln_hits = whits
                best_ln = window_text

        total_score = (doc_distinct_hits * 4.0) + (head_distinct_hits * 6.0) + (name_hits * 8.0) + (best_ln_hits * 3.0)
        if total_score > best_score:
            best_score = total_score
            best_doc = doc
            best_snippet = f"{title_line} | {best_ln}"[:650]

    assert best_doc is not None
    pointer = f"{rel_prefix.rstrip('/')}/{best_doc.name}" if rel_prefix else best_doc.name
    return {
        "answer": f"{best_snippet} (Sumber: `{pointer}`)",
        "source_pointers": [pointer],
    }


def evaluate_introspective_qa(
    qa_items: list[dict[str, Any]],
    handover_dir: Path,
    *,
    answers_by_id: dict[str, dict[str, Any]] | None = None,
    base_root: Path | None = None,
) -> dict[str, Any]:
    """Nilai jawaban QA introspektif dengan syarat wajib pointer berkas sumber sah."""
    if not handover_dir.is_dir():
        raise EvalBenchError(f"Direktori handover tidak ditemukan: {handover_dir}")
    root_for_pointers = (base_root or handover_dir.parent).resolve()

    results: list[dict[str, Any]] = []
    passed_count = 0
    pointer_compliant = 0

    for item in qa_items:
        qid = str(item.get("id", "")).strip()
        question = str(item.get("question", "")).strip()
        expected_sources = [str(s) for s in (item.get("expected_sources") or [])]
        expected_terms = [str(t) for t in (item.get("expected_terms") or [])]

        if answers_by_id is not None:
            cand = answers_by_id.get(qid) or {}
        else:
            cand = solve_introspective_question(
                question,
                handover_dir,
                rel_prefix=handover_dir.resolve().relative_to(root_for_pointers).as_posix()
                if handover_dir.resolve() != root_for_pointers
                else "",
            )

        ans_text = str(cand.get("answer", ""))
        raw_pointers = [str(p).strip() for p in (cand.get("source_pointers") or []) if str(p).strip()]
        if not raw_pointers:
            # Cari pointer inline *.md hanya jika dicantumkan sebagai jalur berkas valid
            raw_pointers = _PATH_PTR_RE.findall(ans_text)

        valid_pointers: list[str] = []
        broken_pointers: list[str] = []
        for ptr in raw_pointers:
            resolved = (root_for_pointers / ptr).resolve()
            try:
                resolved.relative_to(root_for_pointers)
                exists = resolved.is_file()
            except ValueError:
                exists = False
            if exists:
                valid_pointers.append(ptr)
            else:
                broken_pointers.append(ptr)

        reasons: list[str] = []
        if not raw_pointers:
            reasons.append("MISSING_SOURCE_POINTER")
        elif broken_pointers and not valid_pointers:
            reasons.append("BROKEN_SOURCE_POINTER")
        elif expected_sources:
            norm_valid = {Path(p).name for p in valid_pointers}
            norm_expected = {Path(p).name for p in expected_sources}
            if not (norm_valid & norm_expected):
                reasons.append("WRONG_SOURCE_POINTER")

        has_valid_pointer = len(reasons) == 0
        if has_valid_pointer:
            pointer_compliant += 1

        missing_terms = [t for t in expected_terms if t.lower() not in ans_text.lower()]
        if missing_terms:
            reasons.append("MISSING_FACT_TERMS")

        item_passed = len(reasons) == 0
        if item_passed:
            passed_count += 1
        results.append(
            {
                "id": qid,
                "passed": item_passed,
                "has_valid_pointer": has_valid_pointer,
                "valid_pointers": valid_pointers,
                "broken_pointers": broken_pointers,
                "missing_terms": missing_terms,
                "reasons": reasons,
            }
        )

    total = len(qa_items)
    return {
        "bench": "introspective_qa",
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pointer_compliant": pointer_compliant,
        "pointer_compliance_rate": round(pointer_compliant / total, 4) if total else 0.0,
        "accuracy": round(passed_count / total, 4) if total else 0.0,
        "results": results,
    }


# ---------------------------------------------------------------------------
# (b) Bench Konsistensi Lintas Organ (Offline)
# ---------------------------------------------------------------------------

def _extract_organ_label(rec: dict[str, Any]) -> str:
    for key in ("organ", "model", "arm", "run", "validator"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    pair = rec.get("pair")
    if isinstance(pair, dict):
        proposer = str(pair.get("proposer", "")).strip()
        validator = str(pair.get("validator", "")).strip()
        if proposer or validator:
            return f"{proposer}->{validator}".strip("->")
    return "unknown_organ"


def _extract_verdict_and_score(rec: dict[str, Any], threshold: float = 70.0) -> tuple[bool | None, float | None]:
    score: float | None = None
    for sk in ("score", "judge_score"):
        val = rec.get(sk)
        if not isinstance(val, bool) and isinstance(val, (int, float)):
            score = float(val)
            break
    if isinstance(rec.get("ratified"), bool):
        return rec["ratified"], score
    val_block = rec.get("validator")
    if isinstance(val_block, dict):
        parsed = val_block.get("parsed")
        if isinstance(parsed, dict):
            if score is None and not isinstance(parsed.get("score"), bool) and isinstance(parsed.get("score"), (int, float)):
                score = float(parsed["score"])
            if isinstance(parsed.get("accept"), bool):
                return parsed["accept"], score
    for key in ("status", "verdict", "decision"):
        v = rec.get(key)
        if isinstance(v, str):
            u = v.strip().upper()
            if u in {"RATIFY", "RATIFIED", "PASS", "PASSED", "ACCEPT", "ACCEPTED"}:
                return True, score
            if u in {"REJECT", "REJECTED", "FAIL", "FAILED"}:
                return False, score
    if score is not None:
        return score >= threshold, score
    return None, None


def evaluate_cross_organ_consistency(
    result_paths: list[Path],
    *,
    score_delta_threshold: float = 15.0,
) -> dict[str, Any]:
    """Bandingkan kesepakatan putusan dan selisih skor lintas organ pada arsip hasil."""
    if not result_paths:
        raise EvalBenchError("Minimal satu berkas hasil lintas organ harus diberikan.")

    by_task: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    total_rows = 0
    invalid_rows = 0

    for path in result_paths:
        if not path.is_file():
            raise EvalBenchError(f"Berkas hasil organ tidak ditemukan: {path}")
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            total_rows += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                invalid_rows += 1
                continue
            if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not obj["id"].strip():
                invalid_rows += 1
                continue
            if obj.get("error"):
                invalid_rows += 1
                continue
            verdict, score = _extract_verdict_and_score(obj)
            if verdict is None:
                invalid_rows += 1
                continue
            tk = str(obj.get("task_kind", "unknown")).strip() or "unknown"
            organ = _extract_organ_label(obj)
            by_task[(tk, obj["id"].strip())].append(
                {
                    "organ": organ,
                    "verdict": verdict,
                    "score": score,
                    "file": path.name,
                    "line": line_no,
                }
            )

    comparable_tasks = 0
    verdict_disagreements: list[dict[str, Any]] = []
    score_disagreements: list[dict[str, Any]] = []
    pair_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"agreed": 0, "total": 0})

    for (tk, tid) in sorted(by_task):
        obs = by_task[(tk, tid)]
        # Deduplikasi menurut organ jika ada banyak; ambil per organ urut deterministik
        per_organ: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for o in obs:
            per_organ[o["organ"]].append(o)
        if len(per_organ) < 2:
            continue
        comparable_tasks += 1
        organs = sorted(per_organ)
        verdicts = {org: per_organ[org][0]["verdict"] for org in organs}
        scores = {org: per_organ[org][0]["score"] for org in organs if per_organ[org][0]["score"] is not None}

        for i in range(len(organs)):
            for j in range(i + 1, len(organs)):
                oa, ob = organs[i], organs[j]
                pk = f"{oa} vs {ob}"
                pair_stats[pk]["total"] += 1
                if verdicts[oa] == verdicts[ob]:
                    pair_stats[pk]["agreed"] += 1

        if len(set(verdicts.values())) > 1:
            verdict_disagreements.append(
                {
                    "task_kind": tk,
                    "id": tid,
                    "verdicts_by_organ": verdicts,
                    "scores_by_organ": scores,
                }
            )
        if len(scores) >= 2:
            s_vals = list(scores.values())
            delta = round(max(s_vals) - min(s_vals), 2)
            if delta > score_delta_threshold:
                score_disagreements.append(
                    {
                        "task_kind": tk,
                        "id": tid,
                        "score_delta": delta,
                        "scores_by_organ": scores,
                    }
                )

    pair_agreement_rates = {
        pk: {
            "agreed": st["agreed"],
            "total": st["total"],
            "agreement_rate": round(st["agreed"] / st["total"], 4) if st["total"] else 0.0,
        }
        for pk, st in sorted(pair_stats.items())
    }
    agreed_tasks = comparable_tasks - len(verdict_disagreements)
    return {
        "bench": "cross_organ_consistency",
        "files_scanned": [str(p) for p in result_paths],
        "total_rows": total_rows,
        "invalid_rows": invalid_rows,
        "comparable_tasks": comparable_tasks,
        "verdict_agreed_tasks": agreed_tasks,
        "verdict_disagreement_count": len(verdict_disagreements),
        "score_disagreement_count": len(score_disagreements),
        "overall_verdict_agreement_rate": round(agreed_tasks / comparable_tasks, 4) if comparable_tasks else 0.0,
        "pairwise_agreement": pair_agreement_rates,
        "verdict_disagreements": verdict_disagreements,
        "score_disagreements": score_disagreements,
    }


# ---------------------------------------------------------------------------
# (c) Bench Regresi Format Keluaran Perkakas Program
# ---------------------------------------------------------------------------

def default_tool_format_probes() -> list[dict[str, Any]]:
    """Daftar probe kontrak format keluaran perkakas program pada `main`."""
    def _probe_corpus_lint() -> Any:
        line = json.dumps(
            {
                "id": "fmt_001",
                "kind": "episode",
                "task_kind": "code",
                "instruction": "Tulis `f(x)` sederhana. Sertakan docstring Bahasa Indonesia.",
            }
        )
        return corpus_lint.lint_lines([line], prefixes=["fmt_"])

    def _probe_corpus_registry() -> Any:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample_corpus.jsonl").write_text(
                json.dumps({"id": "s1", "kind": "episode", "task_kind": "language", "instruction": "Uji satu kalimat."}) + "\n",
                encoding="utf-8",
            )
            return corpus_registry.scan_corpora(root)

    def _probe_screen_census() -> Any:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "screen.jsonl"
            p.write_text(
                json.dumps({"id": "s1", "task_kind": "language", "ratified": True, "score": 65}) + "\n",
                encoding="utf-8",
            )
            return screen_census.compute_census([p])

    def _probe_bench_table() -> Any:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bench.jsonl"
            p.write_text('{"label":"A","score":61.5}\n{"label":"B","score":70.0}\n', encoding="utf-8")
            summary = bench_table.summarize_bench(p)
            return {"summary": summary, "markdown": bench_table.render_markdown_table(summary)}

    def _probe_ruleset_readiness() -> Any:
        return ruleset_readiness.evaluate_readiness(
            repo="fixture/ACE",
            branch="main",
            protection={"required_status_checks": {"contexts": ["ci"]}},
            branch_rules=[],
        )

    def _probe_opportunity_register() -> Any:
        assets = {
            "a1": {"kind": "venue", "path": "tools/a1.py", "summary": "fixture a1"},
            "a2": {"kind": "tool", "path": "tools/a2.py", "summary": "fixture a2"},
        }
        proposals = opportunity_register.generate_proposals(assets=assets, existing_entries=[])
        return opportunity_register.summarize_register(proposals, [])

    return [
        {
            "tool": "tools.corpus_lint",
            "fn": _probe_corpus_lint,
            "required_keys": {"corpus": "str", "summary": "dict", "total_lines": "int", "valid": "bool", "violation_count": "int", "violations": "list"},
        },
        {
            "tool": "tools.corpus_registry",
            "fn": _probe_corpus_registry,
            "required_keys": {"schema": "str", "source_dir": "str", "corpus_count": "int", "corpora": "list"},
            "schema_value": "ace.frozen-corpus-registry.v1",
        },
        {
            "tool": "tools.screen_census",
            "fn": _probe_screen_census,
            "required_keys": {"by_task_kind": "dict", "files": "list", "invalid_details": "list", "overall": "dict", "split_episodes": "list", "total_lines": "int"},
        },
        {
            "tool": "tools.bench_table",
            "fn": lambda: _probe_bench_table()["summary"],
            "required_keys": {"label_key": "str", "metrics": "list", "rows": "list", "schema": "str", "source": "str", "total_rows": "int"},
            "schema_value": "ace.bench-table.v1",
            "markdown_fn": lambda: _probe_bench_table()["markdown"],
            "markdown_contains": ["| label |", "| A |"],
        },
        {
            "tool": "tools.ruleset_readiness",
            "fn": _probe_ruleset_readiness,
            "required_keys": {"schema": "str", "read_only": "bool", "mutated_github_settings": "bool", "repo": "str", "branch": "str", "ready": "bool", "summary": "dict", "checks": "list", "notes": "list"},
            "schema_value": "ace.ruleset-readiness.v1",
        },
        {
            "tool": "tools.opportunity_register",
            "fn": _probe_opportunity_register,
            "required_keys": {"schema": "str", "claim_made": "bool", "requires_human_validation": "bool", "existing_count": "int", "proposal_count": "int", "proposal_by_origin": "dict"},
        },
    ]


def evaluate_format_regression(probes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Periksa apakah keluaran tiap perkakas program memenuhi kontrak bentuk terpin."""
    active_probes = default_tool_format_probes() if probes is None else probes
    type_map = {
        "str": str,
        "int": int,
        "float": (int, float),
        "bool": bool,
        "dict": dict,
        "list": list,
    }
    results: list[dict[str, Any]] = []
    drift_count = 0

    for probe in active_probes:
        tool_name = str(probe.get("tool", "unknown"))
        req_keys: dict[str, str] = dict(probe.get("required_keys") or {})
        drifts: list[str] = []
        fn: Callable[[], Any] | None = probe.get("fn")
        payload = fn() if fn is not None else probe.get("payload")

        if not isinstance(payload, dict):
            drifts.append(f"NON_DICT_PAYLOAD:{type(payload).__name__}")
        else:
            for key, expected_type_name in sorted(req_keys.items()):
                if key not in payload:
                    drifts.append(f"MISSING_KEY:{key}")
                    continue
                val = payload[key]
                expected_cls = type_map.get(expected_type_name)
                if expected_cls is not None:
                    # Tolak bool saat mengharapkan int/float
                    if expected_type_name in {"int", "float"} and isinstance(val, bool):
                        drifts.append(f"TYPE_MISMATCH:{key}:expected_{expected_type_name}_got_bool")
                    elif not isinstance(val, expected_cls):
                        drifts.append(f"TYPE_MISMATCH:{key}:expected_{expected_type_name}_got_{type(val).__name__}")
            expected_schema = probe.get("schema_value")
            if expected_schema is not None and payload.get("schema") != expected_schema:
                drifts.append(f"SCHEMA_MISMATCH:expected_{expected_schema}_got_{payload.get('schema')}")

        md_anchors = list(probe.get("markdown_contains") or [])
        if md_anchors:
            md_fn = probe.get("markdown_fn")
            md_text = md_fn() if md_fn is not None else str(probe.get("markdown", ""))
            for anchor in md_anchors:
                if anchor not in md_text:
                    drifts.append(f"MARKDOWN_ANCHOR_MISSING:{anchor}")

        if drifts:
            drift_count += 1
        results.append(
            {
                "tool": tool_name,
                "status": "CLEAN" if not drifts else "FORMAT_DRIFT",
                "drifts": drifts,
            }
        )

    return {
        "bench": "format_regression",
        "tools_checked": len(results),
        "clean_count": len(results) - drift_count,
        "drift_count": drift_count,
        "all_clean": drift_count == 0,
        "results": results,
    }


def run_standalone_eval_bench(
    *,
    handover_dir: Path | None = None,
    qa_items: list[dict[str, Any]] | None = None,
    cross_organ_paths: list[Path] | None = None,
    score_delta_threshold: float = 15.0,
    format_probes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Jalankan ketiga bench evaluasi berdiri dalam satu laporan terpadu."""
    active_handover = handover_dir or (REPO_ROOT / "handover")
    qa_res = evaluate_introspective_qa(
        list(DEFAULT_HANDOVER_QA_ITEMS) if qa_items is None else qa_items,
        active_handover,
    )
    if cross_organ_paths:
        co_res = evaluate_cross_organ_consistency(cross_organ_paths, score_delta_threshold=score_delta_threshold)
    else:
        co_res = {
            "bench": "cross_organ_consistency",
            "skipped": True,
            "reason": "Tidak ada berkas hasil lintas organ yang diberikan.",
        }
    fmt_res = evaluate_format_regression(format_probes)

    overall_passed = (qa_res["failed"] == 0) and fmt_res["all_clean"]
    return {
        "schema": EVAL_BENCH_SCHEMA,
        "overall_passed": overall_passed,
        "introspective_qa": qa_res,
        "cross_organ_consistency": co_res,
        "format_regression": fmt_res,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bench evaluasi berdiri ACE (QA handover, konsistensi lintas organ, regresi format).")
    parser.add_argument("--handover-dir", type=Path, default=REPO_ROOT / "handover", help="Direktori dokumen handover.")
    parser.add_argument("--cross-organ-results", nargs="*", type=Path, default=[], help="Berkas JSONL hasil lintas organ offline.")
    parser.add_argument("--score-delta-threshold", type=float, default=15.0, help="Ambang selisih skor lintas organ.")
    parser.add_argument("--output", type=Path, help="Tulis laporan JSON secara atomik.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = run_standalone_eval_bench(
            handover_dir=args.handover_dir,
            cross_organ_paths=args.cross_organ_results or None,
            score_delta_threshold=args.score_delta_threshold,
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            _atomic_write_text(args.output, rendered)
        print(rendered, end="")
        return 0 if report["overall_passed"] else 1
    except EvalBenchError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
