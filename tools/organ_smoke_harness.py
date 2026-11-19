#!/usr/bin/env python3
"""Protokol & adapter smoke-harness organ offline/dry-run EVO 0009 (0 panggilan HTTP).

Menguji kontrak endpoints organ multi-brain (/health, /v1/models, /v1/chat/completions,
/v1/embeddings), provenans `brain_of_origin`, pembatasan channel reasoning, serta
semantik fail-closed (timeout, 429, 502, payload korup, embedding NaN/kosong,
dan penolakan `a3b` pada mode bridge) tanpa pernah membuka soket jaringan.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

SMOKE_SCHEMA = "ace.organ-smoke-harness.v1"

BRIDGE_CHAT_ROLES = ("front", "coder", "validator", "judge")
BRIDGE_EMBED_ROLE = "embedding"

DEFAULT_DRYRUN_ORIGINS: dict[str, str] = {
    "front": "groq/openai/gpt-oss-120b",
    "coder": "groq/qwen/qwen3.8-27b",
    "validator": "groq/openai/gpt-oss-120b",
    "judge": "gonka/deepseek-ai/DeepSeek-V4-Flash-0731",
    "embedding": "gemini/gemini-embedding-001",
}


class LiveNetworkDisallowedError(ValueError):
    """Dilemparkan bila ada upaya memicu transportasi jaringan live pada mode offline."""


class SmokeContractError(ValueError):
    """Kegagalan fail-closed saat respons organ tidak memenuhi kontrak ACE."""


@dataclass(frozen=True)
class SmokeAdapterSpec:
    """Konfigurasi adapter dry-run/mock lokal (tanpa URL jaringan)."""

    adapter_kind: str = "dry-run"
    embedding_dim: int = 8
    origin_overrides: dict[str, str] | None = None


def assert_offline_transport(endpoint_hint: str | None) -> None:
    """Tolak secara keras segala petunjuk URL jaringan (`http://`, `https://`, `ws://`, dst.)."""
    if endpoint_hint is None:
        return
    cleaned = str(endpoint_hint).strip().lower()
    if not cleaned or cleaned in ("dry-run", "mock", "offline", "in-memory"):
        return
    raise LiveNetworkDisallowedError(
        f"Panggilan jaringan live dilarang keras pada smoke-harness offline: {endpoint_hint!r}"
    )


class DryRunOrganAdapter:
    """Adapter simulasi deterministik dalam memori untuk protokol smoke EVO 0009."""

    def __init__(self, spec: SmokeAdapterSpec | None = None) -> None:
        self.spec = spec or SmokeAdapterSpec()
        assert_offline_transport(self.spec.adapter_kind)
        if isinstance(self.spec.embedding_dim, bool) or self.spec.embedding_dim < 1:
            raise ValueError("embedding_dim wajib integer >= 1")
        self.origins = dict(DEFAULT_DRYRUN_ORIGINS)
        if self.spec.origin_overrides:
            self.origins.update(self.spec.origin_overrides)

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        req = payload or {}
        if method == "GET" and path == "/health":
            return 200, {"ok": True, "status": "ok", "roles": sorted(self.origins)}

        if method == "GET" and path == "/v1/models":
            return 200, {
                "object": "list",
                "data": [
                    {
                        "id": f"{role}:{origin.split('/', 1)[1]}",
                        "object": "model",
                        "owned_by": origin.split("/", 1)[0],
                    }
                    for role, origin in sorted(self.origins.items())
                ],
            }

        if method == "POST" and path == "/v1/chat/completions":
            role = req.get("role", "front")
            if role == "a3b":
                return 400, {"error": {"message": "a3b has no bridge role", "type": "invalid_role"}}
            if role not in self.origins or role == "embedding":
                return 404, {"error": {"message": f"unknown chat role: {role}", "type": "unknown_role"}}
            origin = self.origins[role]
            model = origin.split("/", 1)[1] if "/" in origin else origin
            bounded = bool((req.get("chat_template_kwargs") or {}).get("enable_thinking") is False)
            content = '{"status": "smoke_ok", "mode": "dry_run"}' if bounded else "smoke_ok"
            return 200, {
                "id": f"dryrun-{role}",
                "object": "chat.completion",
                "model": model,
                "brain_of_origin": origin,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content, "reasoning_content": ""},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            }

        if method == "POST" and path == "/v1/embeddings":
            role = req.get("role", "embedding")
            if role != "embedding":
                return 400, {"error": {"message": f"unsupported embed role: {role}", "type": "invalid_role"}}
            raw_in = str(req.get("input", ""))
            dim = self.spec.embedding_dim
            base = [round(((idx + 1) + (len(raw_in) % 5)) / 10.0, 6) for idx in range(dim)]
            norm = math.sqrt(sum(v * v for v in base)) or 1.0
            vec = [round(v / norm, 6) for v in base]
            return 200, {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": vec}],
                "model": "gemini-embedding-001",
                "brain_of_origin": self.origins["embedding"],
            }

        return 404, {"error": {"message": f"route not found: {method} {path}", "type": "not_found"}}


def verify_health_response(status: int, body: Any) -> dict[str, Any]:
    if status != 200 or not isinstance(body, dict):
        raise SmokeContractError(f"health_unhealthy:status={status}")
    ok = body.get("ok") is True or body.get("status") == "ok"
    if not ok:
        raise SmokeContractError("health_missing_ok_status")
    return {"passed": True, "roles_advertised": body.get("roles", [])}


def verify_models_response(status: int, body: Any) -> dict[str, Any]:
    if status != 200 or not isinstance(body, dict) or body.get("object") != "list":
        raise SmokeContractError(f"models_malformed_envelope:status={status}")
    items = body.get("data")
    if not isinstance(items, list) or not items:
        raise SmokeContractError("models_empty_list")
    ids = [str(item.get("id", "")) for item in items if isinstance(item, dict) and item.get("id")]
    if len(ids) != len(items):
        raise SmokeContractError("models_item_missing_id")
    return {"passed": True, "model_count": len(ids), "model_ids": ids}


def verify_chat_response(role: str, status: int, body: Any) -> dict[str, Any]:
    if status == 429:
        raise SmokeContractError("budget_exhausted:429")
    if status >= 500 or status == 0:
        raise SmokeContractError(f"organ_unavailable:http_{status}")
    if status != 200 or not isinstance(body, dict):
        raise SmokeContractError(f"unexpected_http_status:{status}")

    origin = body.get("brain_of_origin")
    if not isinstance(origin, str) or "/" not in origin.strip():
        raise SmokeContractError("missing_or_invalid_brain_of_origin")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise SmokeContractError("malformed_choices")
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise SmokeContractError("malformed_message")

    content = str(msg.get("content") or "").strip()
    reasoning = str(msg.get("reasoning_content") or "").strip()
    if not content:
        if reasoning:
            raise SmokeContractError("empty_content_reasoning_overflow")
        raise SmokeContractError("empty_content")

    return {
        "passed": True,
        "role": role,
        "brain_of_origin": origin.strip(),
        "content_len": len(content),
    }


def verify_embedding_response(status: int, body: Any) -> dict[str, Any]:
    if status == 429:
        raise SmokeContractError("budget_exhausted:429")
    if status >= 500:
        raise SmokeContractError(f"organ_unavailable:http_{status}")
    if status != 200 or not isinstance(body, dict):
        raise SmokeContractError(f"unexpected_http_status:{status}")

    origin = body.get("brain_of_origin")
    if not isinstance(origin, str) or "/" not in origin.strip():
        raise SmokeContractError("missing_or_invalid_brain_of_origin")

    data = body.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise SmokeContractError("malformed_embedding_data")
    vec = data[0].get("embedding")
    if not isinstance(vec, list) or not vec:
        raise SmokeContractError("empty_embedding_vector")
    for idx, val in enumerate(vec):
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(float(val)):
            raise SmokeContractError(f"non_finite_embedding_value:idx={idx}")

    norm = round(math.sqrt(sum(float(v) * float(v) for v in vec)), 6)
    return {
        "passed": True,
        "role": "embedding",
        "brain_of_origin": origin.strip(),
        "dim": len(vec),
        "l2_norm": norm,
    }


def run_smoke_protocol(
    handler: Callable[[str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]] | None = None,
    *,
    endpoint_hint: str = "dry-run",
    include_fault_drills: bool = True,
) -> dict[str, Any]:
    """Jalankan rangkaian smoke-check kontrak EVO 0009 secara offline penuh."""
    assert_offline_transport(endpoint_hint)
    call = handler if handler is not None else DryRunOrganAdapter().handle

    checks: list[dict[str, Any]] = []
    observed_origins: dict[str, str] = {}

    # 1. /health & /v1/models
    for name, fn, args in (
        ("health", verify_health_response, ("GET", "/health", None)),
        ("models", verify_models_response, ("GET", "/v1/models", None)),
    ):
        try:
            st, body = call(*args)
            meta = fn(st, body)
            checks.append({"check": name, "passed": True, "detail": meta})
        except (SmokeContractError, TimeoutError, ValueError, TypeError) as exc:
            checks.append({"check": name, "passed": False, "error": str(exc)})

    # 2. Chat roles (bounded thinking)
    for role in BRIDGE_CHAT_ROLES:
        try:
            st, body = call(
                "POST",
                "/v1/chat/completions",
                {
                    "role": role,
                    "messages": [{"role": "user", "content": f"Uji smoke peran {role}"}],
                    "max_tokens": 64,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            meta = verify_chat_response(role, st, body)
            observed_origins[role] = meta["brain_of_origin"]
            checks.append({"check": f"chat:{role}", "passed": True, "detail": meta})
        except (SmokeContractError, TimeoutError, ValueError, TypeError) as exc:
            checks.append({"check": f"chat:{role}", "passed": False, "error": str(exc)})

    # 3. Embedding role
    try:
        st, body = call(
            "POST",
            "/v1/embeddings",
            {"role": BRIDGE_EMBED_ROLE, "input": "Kalimat uji semantik Indonesia."},
        )
        meta = verify_embedding_response(st, body)
        observed_origins[BRIDGE_EMBED_ROLE] = meta["brain_of_origin"]
        checks.append({"check": "embed:embedding", "passed": True, "detail": meta})
    except (SmokeContractError, TimeoutError, ValueError, TypeError) as exc:
        checks.append({"check": "embed:embedding", "passed": False, "error": str(exc)})

    # 4. A3B menolak bridge routing secara eksplisit
    try:
        st, body = call(
            "POST",
            "/v1/chat/completions",
            {"role": "a3b", "messages": [{"role": "user", "content": "probe"}]},
        )
        rejected = st in (400, 404, 502) and isinstance(body, dict) and "error" in body
        checks.append({"check": "bridge_rejects_a3b", "passed": rejected, "status": st})
    except (SmokeContractError, ValueError) as exc:
        checks.append({"check": "bridge_rejects_a3b", "passed": True, "error": str(exc)})

    # 5. Fault injection fail-closed verification (selalu berjalan di memori)
    fault_drills: list[dict[str, Any]] = []
    if include_fault_drills:
        drills = (
            ("fault_429_budget", lambda: verify_chat_response("front", 429, {"error": {"type": "budget_exhausted"}}), "budget_exhausted:429"),
            ("fault_502_unavailable", lambda: verify_chat_response("coder", 502, {"error": {"type": "organ_unavailable"}}), "organ_unavailable:http_502"),
            ("fault_200_missing_origin", lambda: verify_chat_response("front", 200, {"choices": [{"message": {"content": "hi"}}]}), "missing_or_invalid_brain_of_origin"),
            ("fault_200_reasoning_overflow", lambda: verify_chat_response("front", 200, {"brain_of_origin": "local/front", "choices": [{"message": {"content": "", "reasoning_content": "long chain"}}]}), "empty_content_reasoning_overflow"),
            ("fault_embed_nan", lambda: verify_embedding_response(200, {"brain_of_origin": "gemini/gemini-embedding-001", "data": [{"embedding": [0.1, float("nan")]}]}), "non_finite_embedding_value"),
        )
        for dname, fn, expected_frag in drills:
            try:
                fn()
                fault_drills.append({"drill": dname, "passed": False, "error": "did_not_fail_closed"})
            except SmokeContractError as exc:
                fault_drills.append(
                    {
                        "drill": dname,
                        "passed": expected_frag in str(exc),
                        "caught_code": str(exc),
                    }
                )

    checks_ok = all(c["passed"] for c in checks)
    drills_ok = all(d["passed"] for d in fault_drills)
    return {
        "schema": SMOKE_SCHEMA,
        "transport": "offline_dry_run",
        "network_calls": 0,
        "passed": checks_ok and drills_ok,
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks_total": len(checks),
        "fault_drills_passed": sum(1 for d in fault_drills if d["passed"]),
        "fault_drills_total": len(fault_drills),
        "observed_brain_of_origin": observed_origins,
        "checks": checks,
        "fault_drills": fault_drills,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Protokol Smoke Harness Organ EVO 0009 (Offline Dry-Run)",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Transport: `{report['transport']}` (network_calls={report['network_calls']})",
        f"- Status keseluruhan: `{'PASS' if report['passed'] else 'FAIL'}`",
        f"- Cek kontrak: {report['checks_passed']} / {report['checks_total']}",
        f"- Latihan fail-closed injeksi gangguan: {report['fault_drills_passed']} / {report['fault_drills_total']}",
        "",
        "## Hasil Cek Peran & Endpoint",
        "",
        "| Check | Status | Brain of Origin / Detail |",
        "| --- | --- | --- |",
    ]
    for c in report["checks"]:
        detail = c.get("detail") or {}
        info = detail.get("brain_of_origin") or c.get("error") or f"status={c.get('status', 'ok')}"
        lines.append(f"| `{c['check']}` | `{'PASS' if c['passed'] else 'FAIL'}` | `{info}` |")
    if report["fault_drills"]:
        lines.extend(["", "## Injeksi Gangguan Fail-Closed", ""])
        for d in report["fault_drills"]:
            lines.append(f"- `{d['drill']}`: `{'PASS' if d['passed'] else 'FAIL'}` (`{d.get('caught_code', d.get('error'))}`)")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke harness kontrak organ EVO 0009 (strictly offline, 0 HTTP).")
    parser.add_argument("--endpoint", type=str, default="dry-run", help="Hanya menerima 'dry-run'/'mock'/'offline'.")
    parser.add_argument("--no-fault-drills", action="store_true", help="Lewati latihan injeksi gangguan.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = run_smoke_protocol(
            endpoint_hint=args.endpoint,
            include_fault_drills=not args.no_fault_drills,
        )
        rendered = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.format == "json"
            else render_markdown(report)
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
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
