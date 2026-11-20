"""Harness uji smoke multi-peran antar organ via transport terinjeksi (AG83).

Menjalankan paket tugas mencakup empat peran (``director``, ``praktik``,
``bahasa``, ``penilai``) terhadap endpoint organ tiruan melalui fungsi
``transport`` dan ``clock`` yang diinjeksi (zero jaringan live), lalu
menghitung latensi rata-rata/maksimum, laju gagal, dan skor kualitas per
organ maupun per ``(organ, role)``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "ace.organ-smoke.v1"
ROLES: tuple[str, ...] = ("director", "praktik", "bahasa", "penilai")


def default_smoke_pack() -> list[dict[str, Any]]:
    """Paket tugas smoke ringkas mencakup keempat peran standar."""
    return [
        {
            "id": "smk-dir-1",
            "role": "director",
            "prompt": "Klasifikasikan usulan yang menyentuh uang.",
            "expected": "C",
        },
        {
            "id": "smk-pra-1",
            "role": "praktik",
            "prompt": "Normalisasi kunci CSV ['A', ' a '].",
            "expected": "['a']",
        },
        {
            "id": "smk-bhs-1",
            "role": "bahasa",
            "prompt": "Ringkas temuan audit dalam satu kalimat baku.",
            "expected": "audit_baku_ok",
        },
        {
            "id": "smk-pen-1",
            "role": "penilai",
            "prompt": "Beri vonis pasangan teks cocok persis.",
            "expected": "PASS",
        },
    ]


def _score_output(task: Mapping[str, Any], output: Any) -> float:
    if "expected" in task:
        return 1.0 if str(output or "").strip() == str(task["expected"]).strip() else 0.0
    ev = task.get("evaluator")
    if isinstance(ev, Mapping) and ev.get("kind") == "contains_all":
        tokens = [str(t) for t in ev.get("tokens") or []]
        text = str(output or "")
        return round(sum(1 for t in tokens if t in text) / max(1, len(tokens)), 6)
    return 1.0 if output else 0.0


def run_organ_smoke(
    organs: Sequence[str],
    tasks: Sequence[Mapping[str, Any]],
    transport: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    *,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Jalankan smoke pack ke daftar organ tiruan lewat transport & clock terinjeksi."""
    if not organs:
        raise ValueError("Daftar organ tidak boleh kosong.")
    if not tasks:
        raise ValueError("Paket tugas smoke tidak boleh kosong.")
    if not callable(transport):
        raise ValueError("transport wajib berupa callable.")

    for t in tasks:
        if t.get("role") not in ROLES:
            raise ValueError(f"Peran tugas smoke tidak dikenal: {t.get('role')!r}")

    by_organ_out: dict[str, Any] = {}

    for organ in organs:
        role_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_rows: list[dict[str, Any]] = []

        for task in tasks:
            role = str(task["role"])
            t0 = clock()
            try:
                resp = transport(organ, task)
                t1 = clock()
                measured_ms = round((t1 - t0) * 1000.0, 3)
                latency_ms = float(resp.get("latency_ms", measured_ms))
                ok = bool(resp.get("ok", True))
                output = resp.get("output", resp.get("content", ""))
                q_score = _score_output(task, output) if ok else 0.0
            except Exception:
                t1 = clock()
                latency_ms = round(max(0.0, (t1 - t0) * 1000.0), 3)
                ok = False
                q_score = 0.0

            row = {
                "task_id": str(task["id"]),
                "role": role,
                "ok": ok,
                "latency_ms": round(latency_ms, 3),
                "quality_score": round(q_score, 6),
            }
            role_buckets[role].append(row)
            all_rows.append(row)

        def _agg(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
            n = len(rows)
            fails = sum(1 for r in rows if not r["ok"])
            lats = [float(r["latency_ms"]) for r in rows]
            quals = [float(r["quality_score"]) for r in rows]
            return {
                "attempts": n,
                "failures": fails,
                "failure_rate": round(fails / n, 6) if n else 0.0,
                "avg_latency_ms": round(sum(lats) / n, 3) if n else 0.0,
                "max_latency_ms": round(max(lats), 3) if lats else 0.0,
                "quality_score": round(sum(quals) / n, 6) if n else 0.0,
            }

        per_role = {
            role: _agg(role_buckets[role])
            for role in sorted(role_buckets)
        }
        overall = _agg(all_rows)
        by_organ_out[organ] = {
            "organ": organ,
            "overall": overall,
            "by_role": per_role,
            "results": all_rows,
        }

    ranked = sorted(
        by_organ_out.keys(),
        key=lambda o: (
            -by_organ_out[o]["overall"]["quality_score"],
            by_organ_out[o]["overall"]["failure_rate"],
            by_organ_out[o]["overall"]["avg_latency_ms"],
            o,
        ),
    )

    return {
        "schema": SCHEMA,
        "roles_tested": sorted({str(t["role"]) for t in tasks}),
        "summary": {
            "organ_count": len(by_organ_out),
            "task_count": len(tasks),
            "ranking_best_to_worst": ranked,
        },
        "by_organ": by_organ_out,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jalankan smoke pack 4 peran atas organ tiruan secara offline."
    )
    parser.add_argument("--pack", help="Path JSON/JSONL paket tugas opsional (default: bawaan).")
    parser.add_argument("--out", help="Path output JSON opsional.")
    args = parser.parse_args(argv)

    try:
        tasks = (
            json.loads(Path(args.pack).read_text(encoding="utf-8"))
            if args.pack
            else default_smoke_pack()
        )
        # Mode CLI bawaan membandingkan dua profil tiruan offline.
        def _builtin_mock_transport(organ: str, task: Mapping[str, Any]) -> Mapping[str, Any]:
            if organ == "organ-prima":
                return {"ok": True, "output": task.get("expected", "PASS"), "latency_ms": 15.0}
            return {"ok": False, "output": "", "latency_ms": 400.0}

        report = run_organ_smoke(["organ-prima", "organ-lambat-gagal"], tasks, _builtin_mock_transport)
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
