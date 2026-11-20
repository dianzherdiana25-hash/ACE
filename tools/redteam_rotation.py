"""Pelari rotasi red team terhadap classify_proposal + check_anchors (AG73).

Menjalankan paket serangan adversarial berformat AG52 secara rotasi bernama
atas ``director_classes.classify_proposal`` dan ``memory_anchor.check_anchors``.
Menghasilkan laporan penahanan per serangan dan mendaftarkan setiap serangan
yang lolos menjadi Class A tertambat ke dalam ``regression_gate_candidates``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational.director_classes import classify_proposal
from ace_operational.memory_anchor import check_anchors


SCHEMA = "ace.redteam-rotation.v1"


class _RotationRefStore:
    def __init__(self, verified_refs: Sequence[str]) -> None:
        self._refs = frozenset(str(r) for r in verified_refs)

    def verify_ref(self, ref: str) -> bool:
        return ref in self._refs


def _check_anchor_field(raw_refs: Any, store: _RotationRefStore) -> str:
    if not isinstance(raw_refs, list) or not raw_refs:
        return "missing"
    try:
        return str(check_anchors(raw_refs, store)["status"])
    except ValueError:
        return "invalid"


def run_redteam_rotations(rotations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Jalankan semua rotasi red team bernama dan kumpulkan serangan yang lolos."""
    if not rotations:
        raise ValueError("Daftar rotasi red team tidak boleh kosong.")

    rotation_reports: list[dict[str, Any]] = []
    regression_candidates: list[dict[str, Any]] = []
    total_attacks = 0
    total_held = 0

    for idx, rot in enumerate(rotations, 1):
        if not isinstance(rot, Mapping):
            raise ValueError(f"Rotasi[{idx}] wajib berupa objek JSON.")
        rot_id = str(rot.get("rotation_id") or rot.get("name") or f"rotation-{idx}").strip()
        store = _RotationRefStore(rot.get("verified_refs") or ())
        attacks = rot.get("attacks") or rot.get("proposals") or []
        if not isinstance(attacks, list) or not attacks:
            raise ValueError(f"Rotasi '{rot_id}' wajib memiliki daftar 'attacks' tak-kosong.")

        attack_results: list[dict[str, Any]] = []
        rot_held = 0

        for a_idx, attack in enumerate(attacks, 1):
            aid = str(attack.get("id") or f"{rot_id}-atk-{a_idx}")
            vector = str(attack.get("attack_vector") or "unknown")
            task = attack.get("task") if isinstance(attack.get("task"), Mapping) else attack
            cp = task.get("checkpoint") if isinstance(task, Mapping) else {}
            cp = cp if isinstance(cp, Mapping) else {}

            cls_out = classify_proposal(task)
            ev_status = _check_anchor_field(cp.get("evidence_refs"), store)
            base_status = _check_anchor_field(cp.get("based_on"), store)

            stopped_by: list[str] = []
            if cls_out["class"] != "A":
                stopped_by.extend(f"director_classes:{r}" for r in cls_out["reasons"])
            if ev_status != "anchored":
                stopped_by.append(f"memory_anchor(evidence_refs):{ev_status}")
            if base_status != "anchored":
                stopped_by.append(f"memory_anchor(based_on):{base_status}")

            held = len(stopped_by) > 0
            if held:
                rot_held += 1
                total_held += 1
            else:
                regression_candidates.append(
                    {
                        "rotation_id": rot_id,
                        "attack_id": aid,
                        "attack_vector": vector,
                        "classified_as": cls_out["class"],
                        "evidence_anchor_status": ev_status,
                        "based_on_anchor_status": base_status,
                        "recommended_gate": f"regression_gate:{vector}:{aid}",
                    }
                )

            total_attacks += 1
            attack_results.append(
                {
                    "id": aid,
                    "attack_vector": vector,
                    "held": held,
                    "bypassed": not held,
                    "director_class": cls_out["class"],
                    "director_reasons": cls_out["reasons"],
                    "evidence_anchor_status": ev_status,
                    "based_on_anchor_status": base_status,
                    "stopped_by": stopped_by,
                }
            )

        rotation_reports.append(
            {
                "rotation_id": rot_id,
                "attack_count": len(attack_results),
                "held_count": rot_held,
                "bypass_count": len(attack_results) - rot_held,
                "attacks": attack_results,
            }
        )

    return {
        "schema": SCHEMA,
        "summary": {
            "rotation_count": len(rotation_reports),
            "total_attacks": total_attacks,
            "held_count": total_held,
            "bypass_count": len(regression_candidates),
            "hold_rate": round(total_held / total_attacks, 6) if total_attacks else 0.0,
            "all_held": len(regression_candidates) == 0,
        },
        "rotations": rotation_reports,
        "regression_gate_candidates": regression_candidates,
    }


def _load_rotations(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, list):
        return [dict(x) for x in obj]
    if isinstance(obj, Mapping) and isinstance(obj.get("rotations"), list):
        return [dict(x) for x in obj["rotations"]]
    raise ValueError(f"Format JSON rotasi red team tidak sah: {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jalankan rotasi red team atas classify_proposal + check_anchors."
    )
    parser.add_argument("--rotations", required=True, help="Path berkas JSON daftar rotasi serangan.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        rotations = _load_rotations(Path(args.rotations))
        report = run_redteam_rotations(rotations)
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
    return 0 if report["summary"]["all_held"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
