#!/usr/bin/env python3
"""Buku anggaran kuota organ multi-rute & perencana rotasi/kontingensi EVO 0009 (offline).

Mengelola pembukuan jatah harian Groq/Gemini (termasuk multi-bucket kunci Gemini)
serta saldo token bulanan Gonka, plus aturan rotasi dan pemicu rantai kontingensi
pemilik (NVIDIA -> Cloudflare -> Z.ai -> CometAPI) selaras Rancangan EVO 0009 §2.3-2.4.

Sepenuhnya lokal & deterministik (0 panggilan HTTP/jaringan).
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import sys
from typing import Any

LEDGER_SCHEMA = "ace.organ-quota-ledger.v1"
CONTINGENCY_ORDER = ("nvidia", "cloudflare", "zai", "cometapi")

DEFAULT_ROLE_BUDGETS: dict[str, int] = {
    "front": 200,
    "coder": 200,
    "validator": 100,
    "embedding": 200,
    "judge": 20,
}

DEFAULT_ROUTE_MODELS: dict[str, dict[str, str]] = {
    "groq": {
        "front": "openai/gpt-oss-120b",
        "coder": "qwen/qwen3.8-27b",
        "validator": "openai/gpt-oss-120b",
    },
    "gemini": {
        "front": "gemini-3-flash-preview",
        "coder": "gemini-3-flash-preview",
        "validator": "gemini-3-flash-preview",
        "embedding": "gemini-embedding-001",
    },
    "gonka": {
        "judge": "deepseek-ai/DeepSeek-V4-Flash-0731",
    },
    "nvidia": {"front": "nvidia/fallback-chat", "coder": "nvidia/fallback-coder", "validator": "nvidia/fallback-chat"},
    "cloudflare": {"front": "cf/fallback-chat", "coder": "cf/fallback-coder", "validator": "cf/fallback-chat"},
    "zai": {"front": "zai/fallback-chat", "coder": "zai/fallback-coder", "validator": "zai/fallback-chat"},
    "cometapi": {"front": "comet/fallback-chat", "coder": "comet/fallback-coder", "validator": "comet/fallback-chat"},
}

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _require_nonneg_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} wajib bilangan bulat >= 0, diterima: {value!r}")
    return value


def _require_pos_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} wajib bilangan bulat > 0, diterima: {value!r}")
    return value


def create_ledger(
    day: str = "2026-11-19",
    *,
    groq_daily_cap: int = 450,
    gemini_bucket_caps: dict[str, int] | None = None,
    gonka_monthly_token_cap: int = 100_000,
    gonka_daily_cap: int = 20,
    role_budgets: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Buat struktur awal buku kuota multi-rute EVO 0009."""
    if not isinstance(day, str) or not _DAY_RE.fullmatch(day):
        raise ValueError(f"day wajib berbentuk YYYY-MM-DD, diterima: {day!r}")
    _require_pos_int(groq_daily_cap, "groq_daily_cap")
    _require_pos_int(gonka_monthly_token_cap, "gonka_monthly_token_cap")
    _require_pos_int(gonka_daily_cap, "gonka_daily_cap")

    buckets = dict(
        gemini_bucket_caps
        if gemini_bucket_caps is not None
        else {"custom.gemini": 100, "custom.gemini2": 100, "custom.gemini3": 100}
    )
    if not buckets:
        raise ValueError("gemini_bucket_caps minimal memuat satu bucket")
    for bname, bcap in buckets.items():
        if not isinstance(bname, str) or not bname.strip():
            raise ValueError("Nama bucket Gemini wajib string non-kosong")
        _require_pos_int(bcap, f"gemini_bucket_caps[{bname}]")

    budgets = dict(DEFAULT_ROLE_BUDGETS)
    if role_budgets is not None:
        for rname, rcap in role_budgets.items():
            _require_pos_int(rcap, f"role_budgets[{rname}]")
            budgets[rname] = rcap

    return {
        "schema": LEDGER_SCHEMA,
        "day": day,
        "month": day[:7],
        "role_budgets": budgets,
        "role_used": {r: 0 for r in budgets},
        "routes": {
            "groq": {
                "daily_call_cap": groq_daily_cap,
                "calls_used": 0,
                "tokens_used": 0,
            },
            "gemini": {
                "daily_call_cap": sum(buckets.values()),
                "calls_used": 0,
                "tokens_used": 0,
                "buckets": {b: {"daily_cap": c, "used": 0} for b, c in sorted(buckets.items())},
            },
            "gonka": {
                "daily_call_cap": gonka_daily_cap,
                "calls_used": 0,
                "monthly_token_cap": gonka_monthly_token_cap,
                "monthly_tokens_used": 0,
            },
        },
        "contingency": {
            "order": list(CONTINGENCY_ORDER),
            "active_providers": {},
            "events": [],
        },
    }


def rollover_period(ledger: dict[str, Any], new_day: str) -> dict[str, Any]:
    """Gulung buku kuota ke tanggal baru (mereset jatah harian; menjaga kuota bulanan bila bulan sama)."""
    if not isinstance(new_day, str) or not _DAY_RE.fullmatch(new_day):
        raise ValueError(f"new_day wajib berbentuk YYYY-MM-DD, diterima: {new_day!r}")
    out = copy.deepcopy(ledger)
    new_month = new_day[:7]
    old_month = out.get("month", "")

    out["day"] = new_day
    out["month"] = new_month
    for r in list(out["role_used"].keys()):
        out["role_used"][r] = 0

    out["routes"]["groq"]["calls_used"] = 0
    out["routes"]["groq"]["tokens_used"] = 0
    out["routes"]["gemini"]["calls_used"] = 0
    out["routes"]["gemini"]["tokens_used"] = 0
    for bdata in out["routes"]["gemini"]["buckets"].values():
        bdata["used"] = 0

    out["routes"]["gonka"]["calls_used"] = 0
    if new_month != old_month:
        out["routes"]["gonka"]["monthly_tokens_used"] = 0

    for cdata in out["contingency"]["active_providers"].values():
        cdata["calls_used"] = 0

    return out


def _gemini_next_bucket(gemini_route: dict[str, Any]) -> tuple[str | None, int]:
    buckets = gemini_route.get("buckets", {})
    total_rem = 0
    best_name: str | None = None
    best_rem = -1
    for bname in sorted(buckets):
        b = buckets[bname]
        rem = max(0, int(b["daily_cap"]) - int(b["used"]))
        total_rem += rem
        if rem > best_rem and rem > 0:
            best_rem = rem
            best_name = bname
    overall_rem = max(0, int(gemini_route["daily_call_cap"]) - int(gemini_route["calls_used"]))
    return best_name, min(total_rem, overall_rem)


def route_snapshot(ledger: dict[str, Any]) -> dict[str, Any]:
    """Kembalikan ringkasan sisa jatah tiap rute primer, bulanan, dan kontingensi."""
    groq = ledger["routes"]["groq"]
    gemini = ledger["routes"]["gemini"]
    gonka = ledger["routes"]["gonka"]
    groq_rem = max(0, groq["daily_call_cap"] - groq["calls_used"])
    gem_bucket, gem_rem = _gemini_next_bucket(gemini)
    gonka_calls_rem = max(0, gonka["daily_call_cap"] - gonka["calls_used"])
    gonka_tokens_rem = max(0, gonka["monthly_token_cap"] - gonka["monthly_tokens_used"])

    active_cont = {}
    for prov, cdata in sorted(ledger["contingency"]["active_providers"].items()):
        active_cont[prov] = {
            "daily_cap": cdata["daily_call_cap"],
            "calls_used": cdata["calls_used"],
            "remaining": max(0, cdata["daily_call_cap"] - cdata["calls_used"]),
        }

    registered_set = set(ledger["contingency"]["active_providers"])
    next_cont = next((p for p in CONTINGENCY_ORDER if p not in registered_set), None)

    return {
        "day": ledger["day"],
        "month": ledger["month"],
        "groq_remaining": groq_rem,
        "groq_ratio": round(groq_rem / groq["daily_call_cap"], 4) if groq["daily_call_cap"] else 0.0,
        "gemini_remaining": gem_rem,
        "gemini_ratio": round(gem_rem / gemini["daily_call_cap"], 4) if gemini["daily_call_cap"] else 0.0,
        "gemini_next_bucket": gem_bucket,
        "gonka_daily_remaining": gonka_calls_rem,
        "gonka_monthly_tokens_remaining": gonka_tokens_rem,
        "active_contingency": active_cont,
        "next_contingency_candidate": next_cont,
    }


def activate_contingency(
    ledger: dict[str, Any],
    provider: str,
    *,
    daily_call_cap: int = 100,
    reason: str = "primary_exhausted_owner_contingency",
    event_id: str | None = None,
) -> dict[str, Any]:
    """Aktifkan kandidat kontingensi berikutnya sesuai urutan §2.4 EVO 0009 (terlog eksplisit)."""
    prov = provider.strip().lower()
    if prov not in CONTINGENCY_ORDER:
        raise ValueError(f"Provider kontingensi tidak dikenal: {provider!r} (harus salah satu {CONTINGENCY_ORDER})")
    _require_pos_int(daily_call_cap, "daily_call_cap")

    out = copy.deepcopy(ledger)
    active = out["contingency"]["active_providers"]
    expected_idx = CONTINGENCY_ORDER.index(prov)
    for earlier in CONTINGENCY_ORDER[:expected_idx]:
        if earlier not in active:
            raise ValueError(
                f"Aktivasi '{prov}' melompati urutan kontingensi pemilik: '{earlier}' belum terdaftar/habis."
            )

    if prov in active:
        raise ValueError(f"Provider kontingensi '{prov}' sudah aktif di ledger.")

    ev_id = event_id or f"cont-{out['day']}-{len(out['contingency']['events']) + 1:03d}"
    active[prov] = {
        "daily_call_cap": daily_call_cap,
        "calls_used": 0,
        "activated_day": out["day"],
        "event_id": ev_id,
    }
    out["contingency"]["events"].append(
        {
            "event_id": ev_id,
            "day": out["day"],
            "provider": prov,
            "daily_call_cap": daily_call_cap,
            "reason": reason,
        }
    )
    return out


def select_route_for_role(
    ledger: dict[str, Any],
    role: str,
    *,
    mode: str = "engine",
    estimated_tokens: int = 0,
) -> dict[str, Any]:
    """Pilih rute/organ untuk peran sesuai kebijakan anggaran & rotasi EVO 0009 §2.3-2.4."""
    if role not in ledger["role_budgets"]:
        raise ValueError(f"Peran tidak dikenal di buku anggaran: {role!r}")
    if mode not in ("engine", "measurement"):
        raise ValueError(f"mode harus 'engine' atau 'measurement', diterima: {mode!r}")
    _require_nonneg_int(estimated_tokens, "estimated_tokens")

    role_cap = ledger["role_budgets"][role]
    role_used = ledger["role_used"].get(role, 0)
    if role_used >= role_cap:
        return {
            "decision": "BRAIN_UNAVAILABLE",
            "role": role,
            "route": None,
            "provider": None,
            "model": None,
            "key_bucket": None,
            "reason": f"role_daily_budget_exhausted:{role}",
            "contingency_candidate": None,
        }

    snap = route_snapshot(ledger)

    # Judge -> Gonka bulanan terukur; paket ukur beku wajib hold + amendemen bila habis
    if role == "judge":
        tok_need = max(1, estimated_tokens) if estimated_tokens > 0 else 1
        if snap["gonka_daily_remaining"] > 0 and snap["gonka_monthly_tokens_remaining"] >= tok_need:
            return {
                "decision": "ROUTE",
                "role": role,
                "route": "gonka",
                "provider": "gonka",
                "model": DEFAULT_ROUTE_MODELS["gonka"]["judge"],
                "key_bucket": None,
                "reason": "judge_primary_gonka",
                "contingency_candidate": None,
            }
        if mode == "measurement":
            return {
                "decision": "HOLD_AND_AMEND",
                "role": role,
                "route": None,
                "provider": None,
                "model": None,
                "key_bucket": None,
                "reason": "measurement_judge_quota_exhausted_hold",
                "contingency_candidate": None,
            }
        return {
            "decision": "BRAIN_UNAVAILABLE",
            "role": role,
            "route": None,
            "provider": None,
            "model": None,
            "key_bucket": None,
            "reason": "engine_judge_gonka_exhausted",
            "contingency_candidate": snap["next_contingency_candidate"],
        }

    # Embedding -> Gemini embedding; cadangan bila habis = recall leksikal write-back
    if role == "embedding":
        if snap["gemini_remaining"] > 0:
            return {
                "decision": "ROUTE",
                "role": role,
                "route": "gemini",
                "provider": "gemini",
                "model": DEFAULT_ROUTE_MODELS["gemini"]["embedding"],
                "key_bucket": snap["gemini_next_bucket"],
                "reason": "embedding_primary_gemini",
                "contingency_candidate": None,
            }
        return {
            "decision": "LEXICAL_FALLBACK",
            "role": role,
            "route": None,
            "provider": None,
            "model": None,
            "key_bucket": None,
            "reason": "embedding_quota_exhausted_lexical_fallback",
            "contingency_candidate": None,
        }

    # Coder -> sticky di Groq hingga benar-benar habis, baru cadangan bernama Gemini flash
    if role == "coder":
        if snap["groq_remaining"] > 0:
            return {
                "decision": "ROUTE",
                "role": role,
                "route": "groq",
                "provider": "groq",
                "model": DEFAULT_ROUTE_MODELS["groq"]["coder"],
                "key_bucket": None,
                "reason": "coder_primary_groq",
                "contingency_candidate": None,
            }
        if snap["gemini_remaining"] > 0:
            return {
                "decision": "ROUTE",
                "role": role,
                "route": "gemini",
                "provider": "gemini",
                "model": DEFAULT_ROUTE_MODELS["gemini"]["coder"],
                "key_bucket": snap["gemini_next_bucket"],
                "reason": "coder_groq_exhausted_named_fallback",
                "contingency_candidate": None,
            }

    # Front & validator -> rotasi seimbang antara Groq dan Gemini mengikuti sisa rasio anggaran
    if role in ("front", "validator"):
        candidates: list[tuple[float, int, str]] = []
        if snap["groq_remaining"] > 0:
            candidates.append((snap["groq_ratio"], 1, "groq"))
        if snap["gemini_remaining"] > 0:
            candidates.append((snap["gemini_ratio"], 0, "gemini"))
        if candidates:
            candidates.sort(reverse=True)
            chosen = candidates[0][2]
            return {
                "decision": "ROUTE",
                "role": role,
                "route": chosen,
                "provider": chosen,
                "model": DEFAULT_ROUTE_MODELS[chosen][role],
                "key_bucket": snap["gemini_next_bucket"] if chosen == "gemini" else None,
                "reason": "rotation_highest_remaining_ratio",
                "contingency_candidate": None,
            }

    # Semua rute primer habis -> cek kontingensi yang SUDAH terdaftar aktif terlebih dahulu
    if mode == "measurement":
        return {
            "decision": "HOLD_AND_AMEND",
            "role": role,
            "route": None,
            "provider": None,
            "model": None,
            "key_bucket": None,
            "reason": "measurement_routes_exhausted_hold",
            "contingency_candidate": None,
        }

    for prov in CONTINGENCY_ORDER:
        c_info = snap["active_contingency"].get(prov)
        if c_info and c_info["remaining"] > 0:
            return {
                "decision": "ROUTE",
                "role": role,
                "route": prov,
                "provider": prov,
                "model": DEFAULT_ROUTE_MODELS[prov][role],
                "key_bucket": None,
                "reason": f"contingency_active:{prov}",
                "contingency_candidate": None,
            }

    return {
        "decision": "TRIGGER_CONTINGENCY_REQUIRED",
        "role": role,
        "route": None,
        "provider": None,
        "model": None,
        "key_bucket": None,
        "reason": "all_primary_routes_exhausted",
        "contingency_candidate": snap["next_contingency_candidate"],
    }


def record_call(
    ledger: dict[str, Any],
    role: str,
    provider: str,
    *,
    tokens_used: int = 0,
    key_bucket: str | None = None,
) -> dict[str, Any]:
    """Catat pemakaian satu panggilan ke buku anggaran secara immutable/bersih."""
    if role not in ledger["role_budgets"]:
        raise ValueError(f"Peran tidak dikenal: {role!r}")
    _require_nonneg_int(tokens_used, "tokens_used")
    prov = provider.strip().lower()

    out = copy.deepcopy(ledger)
    out["role_used"][role] = out["role_used"].get(role, 0) + 1

    if prov == "groq":
        out["routes"]["groq"]["calls_used"] += 1
        out["routes"]["groq"]["tokens_used"] += tokens_used
    elif prov == "gemini":
        out["routes"]["gemini"]["calls_used"] += 1
        out["routes"]["gemini"]["tokens_used"] += tokens_used
        buckets = out["routes"]["gemini"]["buckets"]
        bname = key_bucket if (key_bucket and key_bucket in buckets) else _gemini_next_bucket(out["routes"]["gemini"])[0]
        if bname is not None and bname in buckets:
            buckets[bname]["used"] += 1
    elif prov == "gonka":
        out["routes"]["gonka"]["calls_used"] += 1
        out["routes"]["gonka"]["monthly_tokens_used"] += tokens_used
    elif prov in out["contingency"]["active_providers"]:
        out["contingency"]["active_providers"][prov]["calls_used"] += 1
    else:
        raise ValueError(f"Provider '{prov}' tidak terdaftar pada rute primer ataupun kontingensi aktif.")

    return out


def reconcile_bridge_log(ledger: dict[str, Any], log_path: Path) -> dict[str, Any]:
    """Rekonsiliasi file `bridge_calls.jsonl` (format brain_bridge) terhadap buku anggaran."""
    target = Path(log_path)
    if not target.is_file():
        raise ValueError(f"Berkas log jembatan tidak ditemukan: {log_path}")

    updated = copy.deepcopy(ledger)
    parsed_rows = 0
    applied_ok = 0
    over_budget_events = 0
    error_events = 0
    malformed_lines: list[dict[str, Any]] = []

    for lineno, raw_line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            malformed_lines.append({"line": lineno, "error": str(exc)})
            continue
        if not isinstance(row, dict):
            malformed_lines.append({"line": lineno, "error": "baris JSON bukan objek"})
            continue

        parsed_rows += 1
        result = row.get("result")
        if result == "over_budget":
            over_budget_events += 1
            continue
        if result != "ok":
            error_events += 1
            continue

        role = str(row.get("role", "")).strip()
        brain = str(row.get("brain", "")).strip()
        provider = brain.split("/", 1)[0].strip().lower() if "/" in brain else ""
        key_bucket = row.get("key") if isinstance(row.get("key"), str) else None
        toks = row.get("tokens", 0)
        if not isinstance(toks, int) or isinstance(toks, bool) or toks < 0:
            toks = 0

        if role in updated["role_budgets"] and provider:
            try:
                updated = record_call(updated, role, provider, tokens_used=toks, key_bucket=key_bucket)
                applied_ok += 1
            except ValueError as exc:
                malformed_lines.append({"line": lineno, "error": str(exc)})

    return {
        "schema": LEDGER_SCHEMA,
        "parsed_rows": parsed_rows,
        "applied_ok": applied_ok,
        "over_budget_events": over_budget_events,
        "error_events": error_events,
        "malformed_line_count": len(malformed_lines),
        "malformed_lines": malformed_lines,
        "snapshot": route_snapshot(updated),
        "ledger": updated,
    }


def render_markdown(ledger: dict[str, Any]) -> str:
    """Render ringkasan saldo kuota organ dalam format Markdown deterministik."""
    snap = route_snapshot(ledger)
    lines = [
        "# Buku Anggaran Kuota Organ Multi-Rute EVO 0009",
        "",
        f"- Schema: `{ledger['schema']}`",
        f"- Tanggal aktif: `{snap['day']}` (bulan `{snap['month']}`)",
        f"- Sisa Groq harian: {snap['groq_remaining']} ({snap['groq_ratio'] * 100:.1f}%)",
        f"- Sisa Gemini harian: {snap['gemini_remaining']} ({snap['gemini_ratio'] * 100:.1f}%), bucket berikut: `{snap['gemini_next_bucket']}`",
        f"- Sisa Gonka bulanan: {snap['gonka_monthly_tokens_remaining']} token (panggilan judge hari ini tersisa: {snap['gonka_daily_remaining']})",
        f"- Kandidat kontingensi berikutnya: `{snap['next_contingency_candidate']}`",
        "",
        "## Pemakaian per Peran",
        "",
        "| Peran | Terpakai | Batas Harian | Keputusan Berikut | Rute Dipilih | Alasan |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for role in sorted(ledger["role_budgets"]):
        sel = select_route_for_role(ledger, role)
        lines.append(
            f"| `{role}` | {ledger['role_used'].get(role, 0)} | {ledger['role_budgets'][role]} | "
            f"`{sel['decision']}` | `{sel['route'] or '-'}` | `{sel['reason']}` |"
        )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Buku anggaran kuota & penjadwal rotasi organ EVO 0009.")
    parser.add_argument("--ledger", type=Path, default=None, help="Berkas JSON buku kuota; bila absen memakai default baru.")
    parser.add_argument("--reconcile-log", type=Path, default=None, help="Rekonsiliasi log bridge_calls.jsonl.")
    parser.add_argument("--day", type=str, default="2026-11-19", help="Tanggal awal bila membuat ledger default.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis hasil ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.ledger is not None:
            ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        else:
            ledger = create_ledger(day=args.day)

        if args.reconcile_log is not None:
            res = reconcile_bridge_log(ledger, args.reconcile_log)
            payload_out = res if args.format == "json" else render_markdown(res["ledger"])
        else:
            payload_out = (
                {"schema": LEDGER_SCHEMA, "snapshot": route_snapshot(ledger), "ledger": ledger}
                if args.format == "json"
                else render_markdown(ledger)
            )

        rendered = (
            json.dumps(payload_out, indent=2, ensure_ascii=False) + "\n"
            if args.format == "json"
            else payload_out
        )
        if args.output is not None:
            out_path = args.output.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
