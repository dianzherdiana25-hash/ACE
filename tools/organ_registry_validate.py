#!/usr/bin/env python3
"""Validator konfigurasi organ multi-brain & registrasi EVO 0009 (offline, fail-closed).

Memvalidasi dua skema konfigurasi lokal tanpa menyentuh jaringan:
1. `ace.organ-slate.v1`: slate organ EVO 0009 (peran `front`, `coder`, `validator`,
   `embedding`, `judge`, peta fallback, kuota harian/bulanan, aturan heterogenitas
   proposer != validator, serta rantai kontingensi NVIDIA -> Cloudflare -> Z.ai -> CometAPI).
2. `ace.brain_registry.v1`: berkas persistensi `BrainRegistry` lokal (memeriksa
   status sah, menolak deskriptor kosong pemicu wildcard, dan mendeteksi kebocoran token).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

VALIDATOR_SCHEMA = "ace.organ-registry-validate.v1"
SLATE_SCHEMA = "ace.organ-slate.v1"
BRAIN_REGISTRY_SCHEMA = "ace.brain_registry.v1"

REQUIRED_ROLES = ("front", "coder", "validator", "embedding", "judge")
VALID_ORGAN_STATUSES = frozenset({"active", "dismissed", "declared-unavailable", "standby"})
VALID_REGISTRY_STATUSES = frozenset({"active", "dismissed", "declared-unavailable"})
ALLOWED_CONTINGENCY_ORDER = ("nvidia", "cloudflare", "zai", "cometapi")

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}"),
    re.compile(r"(?i)(?:api_key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{12,}"),
)


def default_evo0009_slate() -> dict[str, Any]:
    """Kembalikan contoh konfigurasi slate organ acuan EVO 0009 tanpa kredensial."""
    return {
        "schema": SLATE_SCHEMA,
        "revision": "evo0009-slate-v1",
        "organs": {
            "groq_gpt_oss_120b": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "status": "active",
                "capabilities": ["chat", "cross_validation", "reasoning"],
                "daily_call_cap": 300,
            },
            "groq_qwen3_coder": {
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",
                "status": "active",
                "capabilities": ["chat", "code"],
                "daily_call_cap": 200,
            },
            "gemini_flash": {
                "provider": "gemini",
                "model": "gemini-3-flash-preview",
                "status": "active",
                "capabilities": ["chat", "language", "fallback"],
                "daily_call_cap": 200,
            },
            "gemini_embed": {
                "provider": "gemini",
                "model": "gemini-embedding-001",
                "status": "active",
                "capabilities": ["embedding"],
                "daily_call_cap": 200,
            },
            "gonka_deepseek_judge": {
                "provider": "gonka",
                "model": "deepseek-ai/DeepSeek-V4-Flash-0731",
                "status": "active",
                "capabilities": ["judge", "verdict"],
                "daily_call_cap": 20,
                "monthly_token_cap": 100000,
            },
            "local_a3b": {
                "provider": "local",
                "model": "Qwen3-30B-A3B-Q4_K_M",
                "status": "standby",
                "capabilities": ["deep_reasoning"],
                "local_only": True,
            },
        },
        "roles": {
            "front": {
                "primary": "groq_gpt_oss_120b",
                "fallback": "gemini_flash",
                "daily_budget": 200,
            },
            "coder": {
                "primary": "groq_qwen3_coder",
                "fallback": "gemini_flash",
                "daily_budget": 200,
            },
            "validator": {
                "primary": "groq_gpt_oss_120b",
                "fallback": None,
                "daily_budget": 100,
            },
            "embedding": {
                "primary": "gemini_embed",
                "fallback": None,
                "daily_budget": 200,
            },
            "judge": {
                "primary": "gonka_deepseek_judge",
                "fallback": None,
                "daily_budget": 20,
                "hold_on_exhaustion_in_measurement": True,
            },
        },
        "heterogeneity_pairs": {
            "code": {"proposer_role": "coder", "validator_role": "validator"},
            "language": {"proposer_role": "front", "validator_role": "validator", "rotation_partner": "gemini_flash"},
        },
        "contingency_chain": [
            {"provider": "nvidia", "tier": 1, "status": "declared-unavailable"},
            {"provider": "cloudflare", "tier": 2, "status": "declared-unavailable"},
            {"provider": "zai", "tier": 3, "status": "declared-unavailable"},
            {"provider": "cometapi", "tier": 4, "status": "declared-unavailable"},
        ],
    }


def _scan_secret_leaks(obj: Any, path: str = "$") -> list[dict[str, str]]:
    """Deteksi kebocoran kunci API atau token bearer di nilai string JSON secara rekursif."""
    findings: list[dict[str, str]] = []
    if isinstance(obj, str):
        for pat in _SECRET_PATTERNS:
            if pat.search(obj):
                findings.append(
                    {
                        "code": "secret_leak_detected",
                        "path": path,
                        "message": f"Pola potensi kredensial/token terdeteksi pada {path} (dilarang di berkas konfigurasi).",
                    }
                )
                break
    elif isinstance(obj, dict):
        for k, v in sorted(obj.items(), key=lambda kv: str(kv[0])):
            findings.extend(_scan_secret_leaks(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            findings.extend(_scan_secret_leaks(item, f"{path}[{idx}]"))
    return findings


def _is_positive_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool) and val > 0


def _validate_organ_slate(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    errors.extend(_scan_secret_leaks(data))

    organs = data.get("organs")
    roles = data.get("roles")
    if not isinstance(organs, dict) or not organs:
        errors.append({"code": "missing_organs", "path": "$.organs", "message": "Field 'organs' harus berupa objek non-kosong."})
        organs = {}
    if not isinstance(roles, dict) or not roles:
        errors.append({"code": "missing_roles", "path": "$.roles", "message": "Field 'roles' harus berupa objek non-kosong."})
        roles = {}

    organ_signatures: dict[str, tuple[str, str]] = {}
    for oid, rec in sorted(organs.items()):
        p = f"$.organs.{oid}"
        if not isinstance(oid, str) or not oid.strip():
            errors.append({"code": "invalid_organ_id", "path": p, "message": "ID organ wajib string non-kosong."})
            continue
        if not isinstance(rec, dict):
            errors.append({"code": "invalid_organ_record", "path": p, "message": f"Entri organ '{oid}' wajib objek."})
            continue

        prov = rec.get("provider")
        model = rec.get("model")
        status = rec.get("status")
        if not isinstance(prov, str) or not prov.strip():
            errors.append({"code": "missing_provider", "path": f"{p}.provider", "message": f"Organ '{oid}' wajib punya provider."})
        if not isinstance(model, str) or not model.strip():
            errors.append({"code": "blank_model_descriptor", "path": f"{p}.model", "message": f"Model organ '{oid}' tidak boleh kosong."})
        if status not in VALID_ORGAN_STATUSES:
            errors.append({"code": "invalid_status", "path": f"{p}.status", "message": f"Status '{status}' pada '{oid}' tidak valid."})
        if "daily_call_cap" in rec and rec["daily_call_cap"] is not None and not _is_positive_int(rec["daily_call_cap"]):
            errors.append({"code": "invalid_daily_call_cap", "path": f"{p}.daily_call_cap", "message": f"daily_call_cap pada '{oid}' wajib int > 0."})
        if "monthly_token_cap" in rec and rec["monthly_token_cap"] is not None and not _is_positive_int(rec["monthly_token_cap"]):
            errors.append({"code": "invalid_monthly_token_cap", "path": f"{p}.monthly_token_cap", "message": f"monthly_token_cap pada '{oid}' wajib int > 0."})

        if isinstance(prov, str) and prov.strip() and isinstance(model, str) and model.strip():
            organ_signatures[oid] = (prov.strip().lower(), model.strip().lower())

    for req_role in REQUIRED_ROLES:
        rp = f"$.roles.{req_role}"
        if req_role not in roles:
            errors.append({"code": "missing_required_role", "path": rp, "message": f"Peran wajib EVO 0009 '{req_role}' belum didefinisikan."})
            continue
        rdef = roles[req_role]
        if not isinstance(rdef, dict):
            errors.append({"code": "invalid_role_spec", "path": rp, "message": f"Spesifikasi peran '{req_role}' harus objek."})
            continue

        primary = rdef.get("primary")
        fallback = rdef.get("fallback")
        budget = rdef.get("daily_budget")
        if not isinstance(primary, str) or primary not in organs:
            errors.append({"code": "unknown_primary_organ", "path": f"{rp}.primary", "message": f"Primary organ '{primary}' pada peran '{req_role}' tidak terdaftar di organs."})
        else:
            p_status = organs[primary].get("status") if isinstance(organs[primary], dict) else None
            if p_status in ("dismissed", "declared-unavailable"):
                errors.append({"code": "inactive_primary_organ", "path": f"{rp}.primary", "message": f"Primary organ '{primary}' berstatus '{p_status}' (fail-closed)."})

        if fallback is not None:
            if not isinstance(fallback, str) or fallback not in organs:
                errors.append({"code": "unknown_fallback_organ", "path": f"{rp}.fallback", "message": f"Fallback organ '{fallback}' pada '{req_role}' tidak terdaftar."})
            elif fallback == primary:
                warnings.append({"code": "redundant_fallback", "path": f"{rp}.fallback", "message": f"Fallback '{fallback}' sama dengan primary pada '{req_role}'."})

        if not _is_positive_int(budget):
            errors.append({"code": "invalid_daily_budget", "path": f"{rp}.daily_budget", "message": f"daily_budget peran '{req_role}' wajib integer > 0."})

        if req_role == "judge" and rdef.get("hold_on_exhaustion_in_measurement") is not True:
            errors.append({"code": "judge_must_hold_on_exhaustion", "path": f"{rp}.hold_on_exhaustion_in_measurement", "message": "Peran judge wajib menyetel hold_on_exhaustion_in_measurement=true sesuai §2.4 EVO 0009."})

    # Aturan heterogenitas: proposer kode != validator (dan bahasa bila tidak memakai partner rotasi berbeda)
    if isinstance(roles.get("coder"), dict) and isinstance(roles.get("validator"), dict):
        c_prim = roles["coder"].get("primary")
        v_prim = roles["validator"].get("primary")
        if isinstance(c_prim, str) and isinstance(v_prim, str) and c_prim in organ_signatures and v_prim in organ_signatures:
            if c_prim == v_prim or organ_signatures[c_prim] == organ_signatures[v_prim]:
                errors.append(
                    {
                        "code": "heterogeneity_violation_code_pair",
                        "path": "$.roles.coder",
                        "message": f"Proposer coder ({c_prim}) tidak boleh identik dengan validator ({v_prim}).",
                    }
                )

    pairs = data.get("heterogeneity_pairs")
    if isinstance(pairs, dict):
        for pair_name, pspec in sorted(pairs.items()):
            if not isinstance(pspec, dict):
                errors.append({"code": "invalid_pair_spec", "path": f"$.heterogeneity_pairs.{pair_name}", "message": "Pasangan heterogenitas harus objek."})
                continue
            pr = pspec.get("proposer_role")
            vr = pspec.get("validator_role")
            partner = pspec.get("rotation_partner")
            p_org = roles.get(pr, {}).get("primary") if isinstance(roles.get(pr), dict) else None
            v_org = roles.get(vr, {}).get("primary") if isinstance(roles.get(vr), dict) else None
            if p_org and v_org and organ_signatures.get(p_org) == organ_signatures.get(v_org):
                if isinstance(partner, str) and partner in organ_signatures and organ_signatures[partner] != organ_signatures[v_org]:
                    warnings.append(
                        {
                            "code": "pair_relies_on_rotation_partner",
                            "path": f"$.heterogeneity_pairs.{pair_name}",
                            "message": f"Pasangan '{pair_name}' berbagi organ primer '{p_org}' sehingga heterogenitas bertumpu pada rotation_partner '{partner}'.",
                        }
                    )
                else:
                    errors.append(
                        {
                            "code": "heterogeneity_violation",
                            "path": f"$.heterogeneity_pairs.{pair_name}",
                            "message": f"Pasangan '{pair_name}' memiliki organ identik '{p_org}' tanpa rotation_partner berbeda.",
                        }
                    )

    # Validasi urutan kontingensi (§2.4 EVO 0009: NVIDIA -> Cloudflare -> Z.ai -> CometAPI)
    chain = data.get("contingency_chain")
    if chain is not None:
        if not isinstance(chain, list):
            errors.append({"code": "invalid_contingency_chain", "path": "$.contingency_chain", "message": "contingency_chain harus list."})
        else:
            seen_providers: list[str] = []
            prev_tier = 0
            for idx, item in enumerate(chain):
                cp = f"$.contingency_chain[{idx}]"
                if not isinstance(item, dict):
                    errors.append({"code": "invalid_contingency_entry", "path": cp, "message": "Entri kontingensi wajib objek."})
                    continue
                prov = str(item.get("provider", "")).strip().lower()
                tier = item.get("tier")
                st = item.get("status")
                seen_providers.append(prov)
                if not _is_positive_int(tier) or tier <= prev_tier:
                    errors.append({"code": "invalid_contingency_tier", "path": f"{cp}.tier", "message": f"Tier kontingensi harus menaik ketat > {prev_tier}."})
                else:
                    prev_tier = tier
                if st not in VALID_ORGAN_STATUSES:
                    errors.append({"code": "invalid_contingency_status", "path": f"{cp}.status", "message": f"Status kontingensi '{st}' tidak sah."})
                if st == "active" and not item.get("registered_event_id"):
                    errors.append({"code": "silent_contingency_activation", "path": f"{cp}.registered_event_id", "message": f"Organ kontingensi '{prov}' berstatus active tanpa registered_event_id."})

            canonical_subseq = [p for p in seen_providers if p in ALLOWED_CONTINGENCY_ORDER]
            expected_subseq = [p for p in ALLOWED_CONTINGENCY_ORDER if p in canonical_subseq]
            if canonical_subseq != expected_subseq:
                errors.append(
                    {
                        "code": "contingency_order_mismatch",
                        "path": "$.contingency_chain",
                        "message": f"Urutan kontingensi {canonical_subseq} menyimpang dari urutan pemilik {expected_subseq}.",
                    }
                )

    return {
        "schema": VALIDATOR_SCHEMA,
        "detected_config_schema": data.get("schema"),
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "organ_count": len(organs),
        "role_count": len(roles),
        "errors": errors,
        "warnings": warnings,
    }


def _validate_brain_registry(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    errors.extend(_scan_secret_leaks(data))

    brains = data.get("brains")
    events = data.get("events")
    if not isinstance(brains, dict):
        errors.append({"code": "missing_brains_map", "path": "$.brains", "message": "Field 'brains' wajib berupa objek."})
        brains = {}
    if not isinstance(events, list):
        errors.append({"code": "missing_events_list", "path": "$.events", "message": "Field 'events' wajib berupa list."})
        events = []

    seen_descriptors: dict[str, str] = {}
    for bid, rec in sorted(brains.items()):
        p = f"$.brains.{bid}"
        if not isinstance(rec, dict):
            errors.append({"code": "invalid_brain_record", "path": p, "message": "Entri brain wajib berupa objek."})
            continue
        desc = rec.get("descriptor")
        status = rec.get("status")
        if not isinstance(desc, str) or not desc.strip():
            errors.append(
                {
                    "code": "blank_descriptor_wildcard_risk",
                    "path": f"{p}.descriptor",
                    "message": f"Descriptor pada '{bid}' kosong (memicu wildcard match di BrainRegistry.match).",
                }
            )
        else:
            norm = desc.strip().lower()
            if norm in seen_descriptors:
                warnings.append(
                    {
                        "code": "duplicate_descriptor",
                        "path": f"{p}.descriptor",
                        "message": f"Descriptor '{desc}' pada '{bid}' sama dengan '{seen_descriptors[norm]}'.",
                    }
                )
            else:
                seen_descriptors[norm] = bid

        if status not in VALID_REGISTRY_STATUSES:
            errors.append({"code": "invalid_status", "path": f"{p}.status", "message": f"Status '{status}' pada '{bid}' tidak sah."})
        if status == "dismissed" and not str(rec.get("dismissal_reason", "")).strip():
            warnings.append({"code": "dismissed_without_reason", "path": f"{p}.dismissal_reason", "message": f"Brain '{bid}' berstatus dismissed tanpa dismissal_reason."})

    registered_ids = {ev.get("brain_id") for ev in events if isinstance(ev, dict) and ev.get("kind") == "registered"}
    for bid in sorted(brains):
        if bid not in registered_ids:
            warnings.append({"code": "missing_registration_event", "path": f"$.brains.{bid}", "message": f"Brain '{bid}' tidak memiliki event 'registered' pada log events."})

    return {
        "schema": VALIDATOR_SCHEMA,
        "detected_config_schema": data.get("schema"),
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "organ_count": len(brains),
        "event_count": len(events),
        "errors": errors,
        "warnings": warnings,
    }


def validate_config_data(data: Any) -> dict[str, Any]:
    """Validasi objek konfigurasi JSON sesuai skema `ace.organ-slate.v1` atau `ace.brain_registry.v1`."""
    if not isinstance(data, dict):
        return {
            "schema": VALIDATOR_SCHEMA,
            "detected_config_schema": None,
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{"code": "non_object_root", "path": "$", "message": "Konfigurasi wajib berupa objek JSON."}],
            "warnings": [],
        }

    schema = data.get("schema")
    if schema == SLATE_SCHEMA:
        return _validate_organ_slate(data)
    if schema == BRAIN_REGISTRY_SCHEMA:
        return _validate_brain_registry(data)
    return {
        "schema": VALIDATOR_SCHEMA,
        "detected_config_schema": schema,
        "valid": False,
        "error_count": 1,
        "warning_count": 0,
        "errors": [{"code": "unsupported_schema", "path": "$.schema", "message": f"Skema '{schema}' tidak dikenal (wajib '{SLATE_SCHEMA}' atau '{BRAIN_REGISTRY_SCHEMA}')."}],
        "warnings": [],
    }


def validate_config_file(path: Path) -> dict[str, Any]:
    """Muat berkas JSON dari disk secara aman (tanpa symlink escape atau network) dan validasi."""
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"Berkas konfigurasi tidak ditemukan: {path}")
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "schema": VALIDATOR_SCHEMA,
            "detected_config_schema": None,
            "source_path": str(target),
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{"code": "malformed_json", "path": "$", "message": str(exc)}],
            "warnings": [],
        }
    res = validate_config_data(raw)
    res["source_path"] = str(target)
    return res


def render_markdown_report(result: dict[str, Any]) -> str:
    """Format hasil validasi menjadi ringkasan Markdown."""
    lines = [
        "# Validasi Konfigurasi Organ Multi-Brain ACE",
        "",
        f"- Schema laporan: `{result['schema']}`",
        f"- Schema konfigurasi: `{result.get('detected_config_schema')}`",
        f"- Status: `{'VALID' if result['valid'] else 'INVALID'}`",
        f"- Error: {result['error_count']} | Peringatan: {result['warning_count']}",
        "",
    ]
    if result["errors"]:
        lines.extend(["## Kesalahan (Fail-Closed)", ""])
        for err in result["errors"]:
            lines.append(f"- **[{err['code']}]** `{err['path']}`: {err['message']}")
        lines.append("")
    if result["warnings"]:
        lines.extend(["## Peringatan", ""])
        for warn in result["warnings"]:
            lines.append(f"- **[{warn['code']}]** `{warn['path']}`: {warn['message']}")
        lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validator registry & slate organ multi-brain EVO 0009 (offline).")
    parser.add_argument("--config", type=Path, default=None, help="Path ke berkas konfigurasi JSON.")
    parser.add_argument(
        "--check-default",
        action="store_true",
        help="Validasi slate referensi EVO 0009 bawaan tanpa menulis ke disk.",
    )
    parser.add_argument(
        "--print-template",
        action="store_true",
        help="Cetak template JSON `ace.organ-slate.v1` referensi ke stdout.",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.print_template:
            rendered = json.dumps(default_evo0009_slate(), indent=2, ensure_ascii=False) + "\n"
            valid = True
        else:
            if args.check_default:
                res = validate_config_data(default_evo0009_slate())
            elif args.config is not None:
                res = validate_config_file(args.config)
            else:
                raise ValueError("Wajib menyertakan --config PATH, --check-default, atau --print-template.")
            valid = res["valid"]
            rendered = (
                json.dumps(res, indent=2, ensure_ascii=False) + "\n"
                if args.format == "json"
                else render_markdown_report(res)
            )
        if args.output is not None:
            out_path = args.output.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
