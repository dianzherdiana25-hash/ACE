"""Jalankan antrean persepsi lokal yang memiliki batas byte dan percobaan.

Operasi dipilih dari daftar tetap dan inputnya ditambatkan sebelum
decoder dipanggil. Jadwal berdasarkan urutan manifest. Kegagalan satu
pekerjaan tercatat dan pekerjaan lain tetap dinilai selama anggaran
masih cukup. Hasil dipublikasikan sebagai JSON tanpa mengubah sumber.
"""
import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

from . import _audio, _perception_io, _raster, _vision, ocr_engine, scene_describer, silence_segmenter
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_JOBS = 128
MAX_TOTAL_BYTES = 128_000_000
OPERATIONS = {
    "ocr": (ocr_engine.recognize, (_raster.MAX_BYTES, ocr_engine.MAX_FONT_BYTES),
            {"light_ink", "limit_bp", "word_gap"}),
    "scene": (scene_describer.describe, (_raster.MAX_BYTES,),
              {"light_ink", "threshold", "minimum_pixels", "maximum_regions"}),
    "silence": (silence_segmenter.split, (_audio.MAX_BYTES,),
                {"frame_ms", "enter_rms", "exit_rms", "minimum_ms"}),
}


def _input(row, cap):
    if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
        raise ValueError("Bentuk sumber batch tidak sah.")
    _perception_io.relative_parts(row["path"])
    return {"path": row["path"], "sha256": _digest(row["sha256"]),
            "bytes": _integer(row["bytes"], 1, cap, "Ukuran sumber")}


def _plan(manifest):
    plan = _vision.spec(manifest, "ace.perception-batch.v1", ("plan_ref", "maximum_bytes", "maximum_attempts", "jobs"))
    pointer = _token(plan["plan_ref"], "Rujukan rencana batch")
    maximum_bytes = _integer(plan["maximum_bytes"], 1, MAX_TOTAL_BYTES, "Anggaran byte")
    maximum_attempts = _integer(plan["maximum_attempts"], 0, MAX_JOBS, "Anggaran percobaan")
    if not isinstance(plan["jobs"], list) or len(plan["jobs"]) > MAX_JOBS:
        raise ValueError("Jumlah pekerjaan batch di luar batas.")
    items = []
    seen = set()
    for job in plan["jobs"]:
        if not isinstance(job, dict) or set(job) != {"id", "operation", "inputs", "parameters"}:
            raise ValueError("Bentuk pekerjaan batch tidak sah.")
        key = _token(job["id"], "ID pekerjaan")
        name = _token(job["operation"], "Operasi batch")
        if key in seen or name not in OPERATIONS:
            raise ValueError("Identitas pekerjaan ganda atau operasi tidak didukung.")
        seen.add(key)
        _, caps, allowed = OPERATIONS[name]
        if not isinstance(job["inputs"], list) or len(job["inputs"]) != len(caps):
            raise ValueError("Jumlah sumber berbeda dari kontrak operasi.")
        inputs = [_input(row, cap) for row, cap in zip(job["inputs"], caps, strict=True)]
        params = job["parameters"]
        if not isinstance(params, dict) or set(params)-allowed:
            raise ValueError("Parameter operasi batch tidak resmi.")
        items.append({"id": key, "operation": name, "inputs": inputs, "parameters": params})
    return pointer, maximum_attempts, maximum_bytes, items


def run(root, manifest):
    pointer, maximum_attempts, maximum_bytes, jobs = _plan(manifest)
    used = attempted = 0
    results = []
    for job in jobs:
        data = {**job, "result": None, "result_sha256": None}
        reserve = sum(row["bytes"] for row in job["inputs"])
        if attempted == maximum_attempts or used+reserve > maximum_bytes:
            reasons = []
            if attempted == maximum_attempts:
                reasons.append("attempt_budget")
            if used+reserve > maximum_bytes:
                reasons.append("byte_budget")
            results.append({**data, "status": "skipped_budget", "reserved_bytes": 0, "reasons": reasons})
            continue
        attempted += 1
        used += reserve
        data["reserved_bytes"] = reserve
        try:
            payloads = []
            for row in job["inputs"]:
                source = _perception_io.read_relative(root, row["path"], row["bytes"], row["sha256"])
                if len(source) != row["bytes"]:
                    raise ValueError("Ukuran sumber batch berbeda dari komitmen.")
                payloads.append(source)
        except (OSError, ValueError):
            results.append({**data, "status": "failed", "reasons": ["source_verification_failed"]})
            continue
        handler = OPERATIONS[job["operation"]][0]
        try:
            report = handler(*payloads, **job["parameters"])
        except (OverflowError, RecursionError, ValueError):
            results.append({**data, "status": "failed", "reasons": ["decoder_or_settings_failed"]})
            continue
        results.append({**data, "status": "reported", "result": report, "result_sha256": _sha(report), "reasons": []})
    return {"schema": "ace.perception-batch-report.v1", "plan_sha256": sha256(manifest).hexdigest(),
            "plan_ref": pointer, "maximum_attempts": maximum_attempts, "maximum_bytes": maximum_bytes,
            "attempted": attempted, "reserved_bytes": used, "counts": dict(sorted(Counter(row["status"] for row in results).items())),
            "jobs": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.root, _raster.read(args.plan, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] != "reported" for row in result["jobs"]))


if __name__ == "__main__":
    raise SystemExit(main())
