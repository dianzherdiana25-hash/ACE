"""Pelari probe regresi atas paket tersegel berformat AG29 + deteksi penurunan (AG78).

Menjalankan paket tugas probe tersegel terhadap ``solver`` callable, menambahkan
skor hasilnya secara atomik ke berkas deret JSON, dan menerbitkan berkas insiden
terpisah apabila skor turun melampaui ambang ``drop_threshold``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "ace.regression-probe.v1"
SERIES_SCHEMA = "ace.regression-series.v1"
INCIDENT_SCHEMA = "ace.regression-incident.v1"
DEFAULT_DROP_THRESHOLD = 0.10


def load_sealed_probe_pack(pack_path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Muat paket probe tersegel JSON/JSONL beserta SHA-256 berkas aslinya."""
    path = Path(pack_path)
    raw_bytes = path.read_bytes()
    pack_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8").strip()
    if not text:
        raise ValueError(f"Paket probe kosong: {path}")
    if text.startswith("["):
        tasks = [dict(x) for x in json.loads(text)]
    else:
        tasks = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not tasks:
        raise ValueError(f"Paket probe tidak memuat tugas: {path}")
    for idx, t in enumerate(tasks, 1):
        if not isinstance(t, Mapping) or not str(t.get("id") or "").strip():
            raise ValueError(f"Tugas probe ke-{idx} wajib memiliki 'id' tak-kosong")
    return pack_sha256, tasks


def _score_task_response(task: Mapping[str, Any], response: Any) -> bool:
    if "evaluator" in task and isinstance(task["evaluator"], Mapping):
        ev = task["evaluator"]
        kind = ev.get("kind")
        if kind == "exact_match":
            return str(response or "").strip() == str(ev.get("expected") or "").strip()
        if kind == "json_equal":
            return response == ev.get("expected")
        if kind == "numeric_tolerance":
            return abs(float(response) - float(ev["expected"])) <= float(ev.get("tolerance", 1e-6))
    if "expected" in task:
        return response == task["expected"]
    if "expected_zero_record_flagged" in task:
        return bool(response) is bool(task["expected_zero_record_flagged"])
    if "delivered" in task:
        return bool(response) is bool(task["delivered"])
    return bool(response)


def run_probe_and_append_series(
    pack_path: Path,
    series_path: Path,
    solver: Callable[[Mapping[str, Any]], Any],
    *,
    incident_path: Path | None = None,
    drop_threshold: float = DEFAULT_DROP_THRESHOLD,
    run_id: str | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    """Jalankan paket probe, perbarui deret JSON, dan terbitkan insiden bila turun."""
    if not callable(solver):
        raise ValueError("solver wajib berupa callable")
    if drop_threshold < 0 or drop_threshold > 1:
        raise ValueError("drop_threshold wajib di rentang [0, 1]")

    pack_sha256, tasks = load_sealed_probe_pack(Path(pack_path))
    stamp = ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    passed_ids: list[str] = []
    failing_ids: list[str] = []
    for task in tasks:
        tid = str(task["id"])
        ok = _score_task_response(task, solver(task))
        if ok:
            passed_ids.append(tid)
        else:
            failing_ids.append(tid)

    total = len(tasks)
    score = round(len(passed_ids) / total, 6)

    s_path = Path(series_path)
    if s_path.is_file():
        series_doc = json.loads(s_path.read_text(encoding="utf-8"))
        if not isinstance(series_doc, dict) or not isinstance(series_doc.get("runs"), list):
            raise ValueError(f"Format berkas deret tidak sah: {s_path}")
    else:
        series_doc = {"schema": SERIES_SCHEMA, "pack_sha256": pack_sha256, "runs": []}

    prior_runs = list(series_doc["runs"])
    baseline_score: float | None = (
        max(float(r["score"]) for r in prior_runs) if prior_runs else None
    )
    drop = round(baseline_score - score, 6) if baseline_score is not None else 0.0
    regression_detected = bool(baseline_score is not None and drop > drop_threshold)

    entry = {
        "run_id": run_id or f"run-{len(prior_runs) + 1}",
        "ts": stamp,
        "pack_sha256": pack_sha256,
        "score": score,
        "passed": len(passed_ids),
        "total": total,
        "failing_task_ids": failing_ids,
    }
    series_doc["runs"].append(entry)

    s_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_s = s_path.parent / f".{s_path.name}.tmp"
    tmp_s.write_text(json.dumps(series_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_s, s_path)

    written_incident: str | None = None
    if regression_detected and incident_path is not None:
        inc_target = Path(incident_path)
        if inc_target.suffix != ".json":
            inc_target.mkdir(parents=True, exist_ok=True)
            inc_target = inc_target / f"incident_{entry['run_id']}.json"
        else:
            inc_target.parent.mkdir(parents=True, exist_ok=True)
        incident_doc = {
            "schema": INCIDENT_SCHEMA,
            "run_id": entry["run_id"],
            "ts": stamp,
            "pack_path": str(pack_path),
            "pack_sha256": pack_sha256,
            "baseline_score": baseline_score,
            "current_score": score,
            "drop": drop,
            "drop_threshold": drop_threshold,
            "failing_task_ids": failing_ids,
        }
        tmp_inc = inc_target.parent / f".{inc_target.name}.tmp"
        tmp_inc.write_text(
            json.dumps(incident_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(tmp_inc, inc_target)
        written_incident = str(inc_target)

    return {
        "schema": SCHEMA,
        "run_id": entry["run_id"],
        "pack_sha256": pack_sha256,
        "score": score,
        "passed": len(passed_ids),
        "total": total,
        "baseline_score": baseline_score,
        "drop": drop,
        "drop_threshold": drop_threshold,
        "regression_detected": regression_detected,
        "series_length": len(series_doc["runs"]),
        "incident_file": written_incident,
    }


def _fixture_pass_solver(task: Mapping[str, Any]) -> Any:
    if "expected" in task:
        return task["expected"]
    if "expected_zero_record_flagged" in task:
        return task["expected_zero_record_flagged"]
    if "delivered" in task:
        return task["delivered"]
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jalankan paket probe tersegel ke solver dan catat deret skor + insiden regresi."
    )
    parser.add_argument("--pack", required=True, help="Path paket probe JSONL/JSON.")
    parser.add_argument("--series", required=True, help="Path berkas deret skor JSON.")
    parser.add_argument("--incident-out", help="Path file atau direktori untuk berkas insiden jika turun.")
    parser.add_argument("--drop-threshold", type=float, default=DEFAULT_DROP_THRESHOLD)
    parser.add_argument("--run-id")
    parser.add_argument("--out", help="Path output ringkasan JSON opsional.")
    args = parser.parse_args(argv)

    try:
        report = run_probe_and_append_series(
            Path(args.pack),
            Path(args.series),
            _fixture_pass_solver,
            incident_path=Path(args.incident_out) if args.incident_out else None,
            drop_threshold=args.drop_threshold,
            run_id=args.run_id,
        )
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
