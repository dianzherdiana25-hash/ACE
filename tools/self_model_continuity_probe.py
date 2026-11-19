#!/usr/bin/env python3
"""C2 — Probe Kontinuitas Model-Diri Lintas Label Organ (Lapis 3).

Menjalankan generator model-diri naratif (``tools/narrative_self_model.py``
atau callable uji pengganti) di atas **sumber yang sama persis** pada beberapa
konfigurasi label organ yang berbeda, lalu membandingkan **fakta yang
terekstrak** (bukan gaya penulisan atau redaksi kalimat).

Invarian yang diuji:
1. Pergantian organ (mis. ``Qwen3-30B-A3B`` -> ``groq/qwen3.8-27b`` ->
   ``gemini-3-flash-preview``) dan variasi redaksi narasi tidak boleh mengubah
   satu pun fakta terekstrak (``section``, ``fact_key``, ``fact_value``,
   ``source_paths``).
2. Jika suatu konfigurasi organ membocorkan label organ ke dalam fakta atau
   menghasilkan klaim tanpa sumber, probe menandainya sebagai kegagalan
   kontinuitas (``FACT_DRIFT_DETECTED``).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

if __package__:
    from .narrative_self_model import (
        SourcelessClaimError,
        assert_no_sourceless_claims,
        build_narrative_self_model,
        extract_facts,
    )
else:
    from narrative_self_model import (  # type: ignore[import-not-found]
        SourcelessClaimError,
        assert_no_sourceless_claims,
        build_narrative_self_model,
        extract_facts,
    )


SCHEMA = "ace.self-model-continuity-probe.v1"

DEFAULT_ORGAN_SLATES: list[dict[str, Any]] = [
    {
        "slate_id": "local_a3b_baseline",
        "organ_context": {
            "front": "local/Qwen3.5-4B-MTP",
            "coder": "local/Qwen2.5-Coder-7B",
            "director": "local/Qwen3-30B-A3B",
        },
        "narrative_style": "standard",
    },
    {
        "slate_id": "api_groq_qwen38",
        "organ_context": {
            "front": "gemini/gemini-3-flash-preview",
            "coder": "groq/qwen/qwen3.8-27b",
            "validator": "groq/openai/gpt-oss-120b",
        },
        "narrative_style": "concise_en",
    },
    {
        "slate_id": "api_contingency_cloudflare",
        "organ_context": {
            "front": "cloudflare/llama-3.3-70b",
            "coder": "nvidia/deepseek-r1",
            "judge": "gonka/DeepSeek-V4-Flash-0731",
        },
        "narrative_style": "standard",
    },
]

GeneratorFn = Callable[[Path, Path | None, dict[str, Any], str], dict[str, Any]]


def _canonical(val: Any) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _index_facts(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts = model.get("facts")
    if not isinstance(facts, list):
        facts = extract_facts(model)
    indexed: dict[str, dict[str, Any]] = {}
    for f in facts:
        key = f"{f['section']}::{f['fact_key']}"
        indexed[key] = {
            "section": f["section"],
            "fact_key": f["fact_key"],
            "fact_value": f["fact_value"],
            "source_paths": sorted(set(f.get("source_paths") or [])),
        }
    return indexed


def _detect_organ_leakage(
    baseline_model: dict[str, Any],
    variant_model: dict[str, Any],
    organ_context: dict[str, Any],
) -> list[dict[str, str]]:
    """Deteksi bila label organ dari organ_context bocor ke klaim varian tetapi absen di baseline."""
    tokens = {
        str(v).strip().lower()
        for v in organ_context.values()
        if isinstance(v, str) and len(str(v).strip()) >= 4
    }
    base_blob = _canonical(baseline_model.get("sections") or {}).lower()
    leaks: list[dict[str, str]] = []
    for sec in ("identity", "proven", "unproven"):
        for claim in (variant_model.get("sections") or {}).get(sec) or []:
            claim_blob = _canonical(
                {
                    "fact_key": claim.get("fact_key"),
                    "fact_value": claim.get("fact_value"),
                    "statement": claim.get("statement"),
                }
            ).lower()
            for tok in sorted(tokens):
                if tok in claim_blob and tok not in base_blob:
                    leaks.append(
                        {
                            "section": sec,
                            "fact_key": str(claim.get("fact_key") or ""),
                            "leaked_token": tok,
                        }
                    )
    return leaks


def compare_extracted_facts(
    baseline_model: dict[str, Any],
    variant_model: dict[str, Any],
    *,
    variant_id: str,
    organ_context: dict[str, Any],
    allowed_roots: list[Path],
) -> dict[str, Any]:
    """Bandingkan dua keluaran model-diri berdasarkan fakta terekstrak & provenans."""
    sourceless_errors: list[str] = []
    try:
        assert_no_sourceless_claims(variant_model, allowed_roots)
    except SourcelessClaimError as exc:
        sourceless_errors.append(str(exc))

    base_idx = _index_facts(baseline_model)
    var_idx = _index_facts(variant_model)

    missing_keys = sorted(set(base_idx) - set(var_idx))
    added_keys = sorted(set(var_idx) - set(base_idx))
    value_mismatches: list[dict[str, Any]] = []
    source_mismatches: list[dict[str, Any]] = []

    for key in sorted(set(base_idx) & set(var_idx)):
        b = base_idx[key]
        v = var_idx[key]
        if _canonical(b["fact_value"]) != _canonical(v["fact_value"]):
            value_mismatches.append(
                {
                    "key": key,
                    "baseline_value": b["fact_value"],
                    "variant_value": v["fact_value"],
                }
            )
        if b["source_paths"] != v["source_paths"]:
            source_mismatches.append(
                {
                    "key": key,
                    "baseline_sources": b["source_paths"],
                    "variant_sources": v["source_paths"],
                }
            )

    leaks = _detect_organ_leakage(baseline_model, variant_model, organ_context)
    passed = not (missing_keys or added_keys or value_mismatches or source_mismatches or sourceless_errors or leaks)

    return {
        "variant_id": variant_id,
        "organ_context": dict(organ_context),
        "baseline_fact_count": len(base_idx),
        "variant_fact_count": len(var_idx),
        "passed": passed,
        "missing_facts": missing_keys,
        "added_facts": added_keys,
        "value_mismatches": value_mismatches,
        "source_mismatches": source_mismatches,
        "organ_contamination": leaks,
        "sourceless_errors": sourceless_errors,
    }


def _default_generator(
    root: Path,
    memory_path: Path | None,
    organ_context: dict[str, Any],
    narrative_style: str,
) -> dict[str, Any]:
    return build_narrative_self_model(
        root,
        memory_path=memory_path,
        organ_context=organ_context,
        narrative_style=narrative_style,
    )


def run_continuity_probe(
    root: str | Path,
    *,
    memory_path: str | Path | None = None,
    organ_slates: list[dict[str, Any]] | None = None,
    generator: GeneratorFn | None = None,
) -> dict[str, Any]:
    """Jalankan probe kontinuitas lintas konfigurasi label organ di atas sumber sama."""
    repo_root = Path(root).resolve()
    mem_resolved = Path(memory_path).resolve() if memory_path is not None else None
    allowed_roots = [repo_root]
    if mem_resolved is not None:
        allowed_roots.append(mem_resolved if mem_resolved.is_dir() else mem_resolved.parent)

    slates = list(organ_slates or DEFAULT_ORGAN_SLATES)
    if len(slates) < 2:
        raise ValueError("Probe kontinuitas membutuhkan minimal 2 konfigurasi organ untuk dibandingkan.")

    gen_fn = generator or _default_generator
    base_cfg = slates[0]
    baseline_model = gen_fn(
        repo_root,
        mem_resolved,
        dict(base_cfg.get("organ_context") or {}),
        str(base_cfg.get("narrative_style") or "standard"),
    )
    assert_no_sourceless_claims(baseline_model, allowed_roots)
    base_facts = _index_facts(baseline_model)

    comparisons: list[dict[str, Any]] = []
    for cfg in slates[1:]:
        var_id = str(cfg.get("slate_id") or "variant")
        org_ctx = dict(cfg.get("organ_context") or {})
        style = str(cfg.get("narrative_style") or "standard")
        var_model = gen_fn(repo_root, mem_resolved, org_ctx, style)
        comp = compare_extracted_facts(
            baseline_model,
            var_model,
            variant_id=var_id,
            organ_context=org_ctx,
            allowed_roots=allowed_roots,
        )
        comparisons.append(comp)

    all_passed = all(c["passed"] for c in comparisons)
    return {
        "schema": SCHEMA,
        "root": repo_root.as_posix(),
        "memory_path": mem_resolved.as_posix() if mem_resolved else None,
        "baseline_slate": str(base_cfg.get("slate_id") or "baseline"),
        "baseline_organ_context": dict(base_cfg.get("organ_context") or {}),
        "baseline_fact_count": len(base_facts),
        "variants_tested": len(comparisons),
        "continuity_passed": all_passed,
        "verdict": "CONTINUITY_INTACT" if all_passed else "FACT_DRIFT_DETECTED",
        "comparisons": comparisons,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Probe Kontinuitas Model-Diri Lintas Organ (C2)",
        "",
        f"- **Skema**: `{report['schema']}`",
        f"- **Vonis kontinuitas**: `{report['verdict']}` (`continuity_passed={report['continuity_passed']}`)",
        f"- **Baseline**: `{report['baseline_slate']}` ({report['baseline_fact_count']} fakta terekstrak)",
        f"- **Jumlah konfigurasi varian diuji**: `{report['variants_tested']}`",
        "",
        "| Varian Organ | Fakta Baseline | Fakta Varian | Hilang | Tambahan | Beda Nilai | Kontaminasi Organ | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for c in report["comparisons"]:
        status = "PASS" if c["passed"] else "FAIL"
        lines.append(
            f"| `{c['variant_id']}` | {c['baseline_fact_count']} | {c['variant_fact_count']} | "
            f"{len(c['missing_facts'])} | {len(c['added_facts'])} | {len(c['value_mismatches'])} | "
            f"{len(c['organ_contamination'])} | {status} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori ACE")
    parser.add_argument("--memory", default=None, help="Path snapshot memori baca-saja")
    parser.add_argument("--organ-slates-json", default=None, help="Berkas JSON berisi daftar slate organ untuk diuji")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    slates = None
    if args.organ_slates_json:
        slates = json.loads(Path(args.organ_slates_json).read_text(encoding="utf-8"))

    report = run_continuity_probe(args.root, memory_path=args.memory, organ_slates=slates)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["continuity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
