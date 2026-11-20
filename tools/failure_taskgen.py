"""Pembangkit definisi tugas praktik dari fingerprint kegagalan + validasi AG46 (AG65).

Membaca daftar fingerprint kegagalan JSON/JSONL, mensintesis tugas praktik
terstruktur sesuai keluarga gagalnya tanpa membocorkan jawaban di prompt, lalu
mengujinya lewat ``tools.practice_task_validator.validate_task`` agar hanya
tugas sah yang masuk ``accepted_tasks`` sementara fingerprint cacat dilaporkan.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__:
    from .practice_task_validator import validate_task
else:
    from practice_task_validator import validate_task


SCHEMA = "ace.failure-taskgen.v1"

_FAMILY_PROMPTS: dict[str, str] = {
    "csv_dedup": "Bersihkan duplikat baris CSV berdasarkan kunci kanonis dengan mempertahankan urutan kemunculan pertama.",
    "progressive_tax": "Hitung nominal pajak progresif tahunan berdasarkan lapisan tarif pada setiap input penghasilan kena pajak.",
    "json_parser": "Ekstrak field terstruktur secara aman dari potongan objek JSON dan tangani payload cacat.",
    "bfs": "Tentukan panjang lintasan terpendek dengan penelusuran BFS dari simpul awal ke simpul target.",
    "backoff": "Hitung urutan jeda backoff eksponensial yang dibatasi nilai maksimum untuk jumlah percobaan tertentu.",
    "lru": "Simulasikan cache LRU berkapasitas tetap dan kembalikan urutan kunci paling baru di akhir operasi.",
}


def _synthesize_task_from_fingerprint(fp: Mapping[str, Any], idx: int) -> dict[str, Any]:
    fp_id = str(fp.get("fingerprint_id") or fp.get("id") or f"fp-{idx}")
    family = str(fp.get("family") or fp.get("error_type") or "").strip()
    symptom = str(fp.get("symptom") or fp.get("failure_mode") or "").strip()
    if not family:
        raise ValueError(f"Fingerprint {fp_id!r} wajib memiliki field 'family' atau 'error_type'")

    base_prompt = str(
        fp.get("prompt")
        or _FAMILY_PROMPTS.get(family)
        or f"Selesaikan kasus perbaikan untuk keluarga kegagalan '{family}'."
    ).strip()
    if symptom and symptom not in base_prompt:
        base_prompt = f"{base_prompt} (Fokus gejala: {symptom})."

    cases = fp.get("cases") or fp.get("test_cases")
    if isinstance(cases, list) and cases:
        if "override_reference_answer" in fp:
            ref_answer = fp["override_reference_answer"]
        else:
            ref_answer = {str(c["input"]): c["expected"] for c in cases}
        evaluator = {
            "kind": "test_cases_exact",
            "cases": [{"input": str(c["input"]), "expected": c["expected"]} for c in cases],
        }
        task: dict[str, Any] = {
            "id": f"gen-{fp_id}",
            "fingerprint_id": fp_id,
            "family": family,
            "prompt": base_prompt,
            "reference_answer": ref_answer,
            "test_cases": list(evaluator["cases"]),
            "evaluator": evaluator,
        }
    else:
        expected = fp.get("expected")
        ref_answer = fp.get("override_reference_answer", expected)
        task = {
            "id": f"gen-{fp_id}",
            "fingerprint_id": fp_id,
            "family": family,
            "prompt": base_prompt,
            "reference_answer": ref_answer,
            "evaluator": {"kind": "exact_match", "expected": "" if expected is None else str(expected)},
        }

    if isinstance(fp.get("evaluator_source"), str):
        task["evaluator_source"] = fp["evaluator_source"]
    return task


def generate_and_validate_tasks(fingerprints: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Bangkitkan tugas praktik dari fingerprint dan saring lewat practice_task_validator."""
    if not fingerprints:
        raise ValueError("Daftar fingerprint kegagalan tidak boleh kosong")

    accepted_tasks: list[dict[str, Any]] = []
    rejected_fingerprints: list[dict[str, Any]] = []

    for idx, fp in enumerate(fingerprints, 1):
        if not isinstance(fp, Mapping):
            rejected_fingerprints.append(
                {
                    "fingerprint_id": f"fp-{idx}",
                    "reason": "fingerprint_not_object",
                    "issues": [{"code": "malformed_fingerprint", "detail": "bukan objek JSON"}],
                }
            )
            continue

        fp_id = str(fp.get("fingerprint_id") or fp.get("id") or f"fp-{idx}")
        try:
            task = _synthesize_task_from_fingerprint(fp, idx)
        except (KeyError, TypeError, ValueError) as exc:
            rejected_fingerprints.append(
                {
                    "fingerprint_id": fp_id,
                    "reason": "synthesis_error",
                    "issues": [{"code": "malformed_fingerprint", "detail": str(exc)}],
                }
            )
            continue

        verdict = validate_task(task)
        if verdict["valid"]:
            accepted_tasks.append(task)
        else:
            rejected_fingerprints.append(
                {
                    "fingerprint_id": fp_id,
                    "task_id": task["id"],
                    "reason": "failed_practice_task_validator",
                    "issue_codes": verdict["issue_codes"],
                    "issues": verdict["issues"],
                }
            )

    return {
        "schema": SCHEMA,
        "summary": {
            "input_fingerprints": len(fingerprints),
            "accepted_count": len(accepted_tasks),
            "rejected_count": len(rejected_fingerprints),
        },
        "accepted_tasks": accepted_tasks,
        "rejected_fingerprints": rejected_fingerprints,
    }


def _load_fingerprints(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas fingerprint kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Berkas JSON fingerprint harus berupa daftar")
        return [dict(item) for item in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, Mapping) and isinstance(obj.get("fingerprints"), list):
            return [dict(item) for item in obj["fingerprints"]]
        return [dict(obj)]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bangkitkan tugas praktik dari fingerprint kegagalan dan validasi via AG46."
    )
    parser.add_argument("--fingerprints", required=True, help="Path berkas fingerprint JSON/JSONL.")
    parser.add_argument("--out-tasks", help="Tulis tugas yang lolos ke JSONL.")
    parser.add_argument("--out", help="Tulis laporan lengkap JSON (default stdout).")
    args = parser.parse_args(argv)

    try:
        fps = _load_fingerprints(Path(args.fingerprints))
        report = generate_and_validate_tasks(fps)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.out_tasks:
        tp = Path(args.out_tasks)
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(
            "\n".join(json.dumps(t, ensure_ascii=False, sort_keys=True) for t in report["accepted_tasks"])
            + ("\n" if report["accepted_tasks"] else ""),
            encoding="utf-8",
        )

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
