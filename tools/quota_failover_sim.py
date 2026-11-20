"""Simulator keputusan kuota dan failover peran bridge (AG49).

Diberikan state anggaran awal per peran serta daftar langkah eksekusi dengan
flag ``critical``, simulator menentukan untuk tiap langkah apakah memakai:
- ``"primary"``: saat kuota peran utama mencukupi (untuk kritis maupun non-kritis),
- ``"fallback"``: HANYA untuk langkah non-kritis saat kuota utama habis dan
  peran cadangan tersedia serta mencukupi,
- ``"wait"``: saat langkah kritis kehabisan kuota utama (dilarang fallback), atau
  langkah non-kritis kehabisan kuota utama dan tidak punya fallback mencukupi.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.quota-failover-sim.v1"


def _normalize_budgets(raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    src = raw.get("roles") if isinstance(raw.get("roles"), Mapping) else raw
    if not isinstance(src, Mapping) or not src:
        raise ValueError("State anggaran peran tidak boleh kosong")

    out: dict[str, dict[str, Any]] = {}
    for role, info in src.items():
        if not isinstance(info, Mapping):
            raise ValueError(f"Konfigurasi peran '{role}' wajib berupa objek")
        remaining = info.get("remaining")
        if not isinstance(remaining, int) or isinstance(remaining, bool) or remaining < 0:
            raise ValueError(f"remaining peran '{role}' wajib integer >= 0")
        entry: dict[str, Any] = {"remaining": remaining}
        fb = info.get("fallback_role") or info.get("fallback")
        if isinstance(fb, str) and fb.strip():
            entry["fallback_role"] = fb.strip()
        out[str(role)] = entry
    return out


def simulate_failover(
    budget_state: Mapping[str, Any],
    steps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Jalankan simulasi keputusan primary/fallback/wait secara deterministik."""
    budgets = _normalize_budgets(budget_state)
    initial_budgets = deepcopy(budgets)

    if not steps:
        raise ValueError("Daftar langkah simulasi tidak boleh kosong")

    decisions: list[dict[str, Any]] = []
    primary_count = 0
    fallback_count = 0
    wait_count = 0
    critical_fallback_count = 0

    for idx, step in enumerate(steps, 1):
        if not isinstance(step, Mapping):
            raise ValueError(f"Langkah ke-{idx} wajib berupa objek")
        step_id = str(step.get("step_id") or step.get("id") or f"step-{idx}")
        role = step.get("role")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"Langkah '{step_id}' wajib memiliki 'role'")
        role = role.strip()

        if "critical" not in step or not isinstance(step["critical"], bool):
            raise ValueError(f"Langkah '{step_id}' wajib memiliki 'critical' bertipe bool")
        critical = step["critical"]

        cost = step.get("cost", 1)
        if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
            raise ValueError(f"Langkah '{step_id}' memiliki cost tidak sah: {cost!r}")

        if role not in budgets:
            raise ValueError(f"Peran '{role}' pada langkah '{step_id}' tidak terdaftar di budget")

        primary_rem = budgets[role]["remaining"]
        step_fb = step.get("fallback_role") or step.get("fallback")
        fb_role = (
            step_fb.strip()
            if isinstance(step_fb, str) and step_fb.strip()
            else budgets[role].get("fallback_role")
        )

        if primary_rem >= cost:
            budgets[role]["remaining"] = primary_rem - cost
            decision = "primary"
            chosen_role: str | None = role
            reason = "primary_budget_available"
            primary_count += 1
        elif critical:
            decision = "wait"
            chosen_role = None
            reason = "critical_primary_exhausted_no_fallback"
            wait_count += 1
        elif fb_role and fb_role in budgets and budgets[fb_role]["remaining"] >= cost:
            budgets[fb_role]["remaining"] -= cost
            decision = "fallback"
            chosen_role = fb_role
            reason = "non_critical_primary_exhausted_used_fallback"
            fallback_count += 1
        elif fb_role:
            decision = "wait"
            chosen_role = None
            reason = "non_critical_primary_and_fallback_exhausted"
            wait_count += 1
        else:
            decision = "wait"
            chosen_role = None
            reason = "non_critical_primary_exhausted_no_fallback_configured"
            wait_count += 1

        if critical and decision == "fallback":
            critical_fallback_count += 1

        decisions.append(
            {
                "step_id": step_id,
                "role": role,
                "critical": critical,
                "cost": cost,
                "decision": decision,
                "chosen_role": chosen_role,
                "reason": reason,
                "primary_remaining_after": budgets[role]["remaining"],
                "fallback_role": fb_role,
                "fallback_remaining_after": (
                    budgets[fb_role]["remaining"] if fb_role and fb_role in budgets else None
                ),
            }
        )

    return {
        "schema": SCHEMA,
        "initial_budgets": initial_budgets,
        "final_budgets": budgets,
        "summary": {
            "total_steps": len(decisions),
            "primary_count": primary_count,
            "fallback_count": fallback_count,
            "wait_count": wait_count,
            "critical_fallback_count": critical_fallback_count,
        },
        "decisions": decisions,
    }


def _load_steps(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas langkah kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Berkas langkah JSON harus berupa list")
        return [dict(item) for item in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, dict) and isinstance(obj.get("steps"), list):
            return [dict(item) for item in obj["steps"]]
        return [dict(obj)]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulasikan keputusan kuota & failover (primary/fallback/wait) per langkah."
    )
    parser.add_argument("--budgets", required=True, help="Path JSON state anggaran peran awal.")
    parser.add_argument("--steps", required=True, help="Path JSON/JSONL daftar langkah simulasi.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        budgets_raw = json.loads(Path(args.budgets).read_text(encoding="utf-8"))
        if not isinstance(budgets_raw, dict):
            raise ValueError("Berkas budgets wajib berupa objek JSON")
        steps = _load_steps(Path(args.steps))
        report = simulate_failover(budgets_raw, steps)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
