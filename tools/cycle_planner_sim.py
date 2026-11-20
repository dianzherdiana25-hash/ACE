"""Simulator kebijakan perencana siklus di atas model dunia rumah AG76 (AG77).

Menerima snapshot model rumah (``ace.house-world-model.v1``) serta daftar langkah
berkritikalitas dan berbobot untuk memutuskan urutan eksekusi dan penundaan
per langkah beserta alasan eksplisit:
- Saat rumah sehat & bridge siap: langkah kritis dan langkah berat (``cost``/bobot
  tinggi) didahulukan sebelum sisa kuota terpecah habis oleh langkah ringan;
- Saat rumah sakit atau telemetri basi (``house_state in {"sick", "stale"}``):
  hanya langkah kritis yang didahulukan; langkah non-kritis ditunda.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.cycle-planner-sim.v1"


def plan_cycle_steps(
    world_model: Mapping[str, Any],
    steps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rencanakan urutan eksekusi & penundaan langkah berdasarkan keadaan model rumah."""
    if not isinstance(world_model, Mapping):
        raise ValueError("world_model wajib berupa mapping JSON")
    if not steps:
        raise ValueError("Daftar langkah simulasi tidak boleh kosong")

    house_state = str(world_model.get("house_state") or "stale").lower()
    is_sick = bool(world_model.get("is_sick", house_state != "healthy"))
    bridge_ok = bool((world_model.get("bridge_health") or {}).get("ok", True))

    budgets_block = (world_model.get("budgets") or {}).get("roles") or {}
    remaining = {
        str(role): max(0, int((info or {}).get("remaining", 0)))
        for role, info in budgets_block.items()
    }
    initial_remaining = deepcopy(remaining)

    normalized: list[dict[str, Any]] = []
    for idx, step in enumerate(steps, 1):
        sid = str(step.get("step_id") or step.get("id") or f"step-{idx}")
        role = str(step.get("role") or "").strip()
        if not role:
            raise ValueError(f"Langkah '{sid}' wajib memiliki 'role'")
        if "critical" not in step or not isinstance(step["critical"], bool):
            raise ValueError(f"Langkah '{sid}' wajib memiliki 'critical' bertipe bool")
        cost = int(step.get("cost", 1))
        weight = int(step.get("weight", cost))
        if cost < 1:
            raise ValueError(f"Langkah '{sid}' memiliki cost < 1")
        normalized.append(
            {
                "step_id": sid,
                "role": role,
                "critical": step["critical"],
                "cost": cost,
                "weight": weight,
                "local_only": bool(step.get("local_only", False)),
            }
        )

    # Prioritas antrean: kritis dulu, lalu langkah berat (cost tinggi, weight tinggi) sebelum kuota habis.
    prioritized = sorted(
        normalized,
        key=lambda s: (not s["critical"], -s["cost"], -s["weight"], s["step_id"]),
    )

    decisions: list[dict[str, Any]] = []
    scheduled_order: list[str] = []
    deferred_ids: list[str] = []

    for s in prioritized:
        sid = s["step_id"]
        role = s["role"]
        cost = s["cost"]
        critical = s["critical"]
        reasons: list[str] = []
        avail = remaining.get(role, 0)

        if (not bridge_ok) and (not s["local_only"]):
            decision = "defer"
            reasons.append("bridge_unavailable_defer")
        elif is_sick and not critical:
            decision = "defer"
            reasons.append(f"deferred_non_critical_while_house_{house_state}")
        elif avail < cost:
            decision = "defer"
            reasons.append(f"insufficient_role_budget:remaining={avail}<cost={cost}")
        else:
            remaining[role] = avail - cost
            decision = "run"
            if is_sick:
                reasons.append(f"critical_first_while_house_{house_state}")
            elif s["cost"] > 1 or s["weight"] > 1:
                reasons.append("heavy_step_scheduled_before_quota_fragmented")
            else:
                reasons.append("healthy_within_budget")
            scheduled_order.append(sid)

        if decision == "defer":
            deferred_ids.append(sid)

        decisions.append(
            {
                "step_id": sid,
                "role": role,
                "critical": critical,
                "cost": cost,
                "weight": s["weight"],
                "decision": decision,
                "order_rank": len(scheduled_order) if decision == "run" else None,
                "remaining_after": remaining.get(role, 0),
                "reasons": reasons,
            }
        )

    return {
        "schema": SCHEMA,
        "house_state": house_state,
        "is_sick": is_sick,
        "bridge_ok": bridge_ok,
        "initial_remaining": initial_remaining,
        "final_remaining": remaining,
        "summary": {
            "total_steps": len(decisions),
            "run_count": len(scheduled_order),
            "defer_count": len(deferred_ids),
            "scheduled_order": scheduled_order,
            "deferred_steps": deferred_ids,
        },
        "decisions": decisions,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulasikan urutan & penundaan siklus dari model rumah AG76 + daftar langkah."
    )
    parser.add_argument("--world-model", required=True, help="Path JSON model dunia rumah (AG76).")
    parser.add_argument("--steps", required=True, help="Path JSON daftar langkah berkritikalitas & bobot.")
    parser.add_argument("--out", help="Path output JSON opsional.")
    args = parser.parse_args(argv)

    try:
        world = json.loads(Path(args.world_model).read_text(encoding="utf-8"))
        steps_raw = json.loads(Path(args.steps).read_text(encoding="utf-8"))
        if isinstance(steps_raw, Mapping) and isinstance(steps_raw.get("steps"), list):
            steps_list = steps_raw["steps"]
        elif isinstance(steps_raw, list):
            steps_list = steps_raw
        else:
            raise ValueError("Berkas steps wajib berupa list JSON")
        report = plan_cycle_steps(world, steps_list)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
