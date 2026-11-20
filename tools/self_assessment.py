"""Penyusun & pemverifikasi berkas penilaian-diri bersegel rantai hash (AG101).

Menyusun berkas penilaian-diri terstruktur per kemampuan
(``capability_id``, ``status_claim``, ``predicted_measurement_score``,
``evidence_pointer``) dalam format yang sebanding untuk penilai independen,
lalu menyegel tiap versi berantai SHA-256 (``prev_version_hash`` ->
``version_hash``) sehingga mutasi diam-diam pasca-segel pada versi mana pun
langsung terdeteksi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.self-assessment-chain.v1"
COMPARE_SCHEMA = "ace.self-assessment-comparison.v1"
VALID_STATUS_CLAIMS = frozenset({"terbukti", "sebagian", "belum", "gagal"})
GENESIS_HASH = "GENESIS"


class SelfAssessmentTamperError(ValueError):
    """Galat ketika segel atau rantai versi penilaian-diri gagal verifikasi."""


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_capability(item: Mapping[str, Any]) -> dict[str, Any]:
    cid = str(item.get("capability_id") or "").strip()
    status_claim = str(item.get("status_claim") or "").strip().lower()
    raw_score = item.get("predicted_measurement_score")
    evidence = str(item.get("evidence_pointer") or "").strip()

    if not cid:
        raise SelfAssessmentTamperError("Setiap kemampuan wajib memiliki capability_id.")
    if status_claim not in VALID_STATUS_CLAIMS:
        raise SelfAssessmentTamperError(
            f"status_claim tidak valid untuk {cid!r}: {status_claim!r}; pilih dari {sorted(VALID_STATUS_CLAIMS)}."
        )
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise SelfAssessmentTamperError(f"predicted_measurement_score {cid!r} wajib angka di [0.0, 1.0].")
    fscore = float(raw_score)
    if not (0.0 <= fscore <= 1.0):
        raise SelfAssessmentTamperError(f"predicted_measurement_score {cid!r} di luar [0.0, 1.0]: {fscore!r}.")
    if not evidence:
        raise SelfAssessmentTamperError(f"evidence_pointer wajib diisi untuk kemampuan {cid!r}.")

    return {
        "capability_id": cid,
        "status_claim": status_claim,
        "predicted_measurement_score": round(fscore, 6),
        "evidence_pointer": evidence,
    }


def append_sealed_assessment(
    chain_path: str | Path,
    *,
    assessment_id: str,
    created_at: str,
    capabilities: Sequence[Mapping[str, Any]],
    notes: str = "",
) -> dict[str, Any]:
    """Tambahkan versi penilaian-diri baru tersegel SHA-256 ke rantai berkas."""
    aid = assessment_id.strip()
    if not aid or not created_at.strip():
        raise SelfAssessmentTamperError("assessment_id dan created_at wajib tidak kosong.")
    if not capabilities:
        raise SelfAssessmentTamperError("Daftar capabilities tidak boleh kosong.")

    norm_caps = sorted(
        [_normalize_capability(c) for c in capabilities],
        key=lambda x: x["capability_id"],
    )
    seen_ids = [c["capability_id"] for c in norm_caps]
    if len(set(seen_ids)) != len(seen_ids):
        raise SelfAssessmentTamperError("capability_id duplikat dalam satu versi penilaian-diri.")

    path = Path(chain_path)
    existing_versions: list[dict[str, Any]] = []
    if path.exists() and path.read_text(encoding="utf-8").strip():
        existing_versions = load_assessment_chain(path)
        ver_report = verify_assessment_chain(existing_versions, strict=True)
        prev_hash = str(ver_report["head_hash"])
        next_version = len(existing_versions) + 1
    else:
        prev_hash = GENESIS_HASH
        next_version = 1

    body = {
        "schema": SCHEMA,
        "version": next_version,
        "assessment_id": aid,
        "created_at": created_at.strip(),
        "prev_version_hash": prev_hash,
        "notes": notes.strip(),
        "capabilities": norm_caps,
    }
    sealed = dict(body)
    sealed["version_hash"] = _canonical_hash(body)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sealed, ensure_ascii=False, sort_keys=True) + "\n")
    return sealed


def load_assessment_chain(chain_path: str | Path) -> list[dict[str, Any]]:
    path = Path(chain_path)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SelfAssessmentTamperError(f"Baris {lineno} pada {path} bukan objek JSON.")
        records.append(row)
    return records


def verify_assessment_chain(
    versions: Sequence[Mapping[str, Any]],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Periksa integritas tiap versi & tautan ``prev_version_hash -> version_hash``."""
    errors: list[str] = []
    expected_prev = GENESIS_HASH
    head_hash = GENESIS_HASH

    for idx, ver in enumerate(versions, start=1):
        if ver.get("schema") != SCHEMA:
            errors.append(f"Versi {idx}: schema tidak cocok ({ver.get('schema')!r}).")
        if ver.get("version") != idx:
            errors.append(f"Versi {idx}: nomor versi tidak berurutan ({ver.get('version')!r}).")
        if ver.get("prev_version_hash") != expected_prev:
            errors.append(
                f"Versi {idx}: prev_version_hash putus (tercatat {ver.get('prev_version_hash')!r}, harusnya {expected_prev!r})."
            )
        recompute_body = {
            "schema": ver.get("schema"),
            "version": ver.get("version"),
            "assessment_id": ver.get("assessment_id"),
            "created_at": ver.get("created_at"),
            "prev_version_hash": ver.get("prev_version_hash"),
            "notes": ver.get("notes", ""),
            "capabilities": ver.get("capabilities"),
        }
        computed_hash = _canonical_hash(recompute_body)
        recorded_hash = ver.get("version_hash")
        if recorded_hash != computed_hash:
            errors.append(
                f"Versi {idx}: mutasi diam-diam terdeteksi (version_hash tidak cocok dengan isi)."
            )
        head_hash = str(recorded_hash or computed_hash)
        expected_prev = str(recorded_hash or "")

    valid = len(errors) == 0
    report = {
        "schema": SCHEMA,
        "version_count": len(versions),
        "head_hash": head_hash if versions else GENESIS_HASH,
        "valid": valid,
        "errors": errors,
    }
    if strict and not valid:
        raise SelfAssessmentTamperError("; ".join(errors))
    return report


def compare_with_evaluator(
    sealed_version: Mapping[str, Any],
    evaluator_scores: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Bandingkan klaim penilaian-diri dengan skor penilai independen."""
    verify_assessment_chain([sealed_version], strict=False)  # Validasi struktur tunggal jika genesis; abaikan jika bukan v1.
    rows: list[dict[str, Any]] = []
    abs_errors: list[float] = []
    agreements = 0

    for cap in sealed_version.get("capabilities", []):
        cid = str(cap["capability_id"])
        pred_score = float(cap["predicted_measurement_score"])
        claimed_status = str(cap["status_claim"])
        ev = evaluator_scores.get(cid, {})
        actual_score = ev.get("measured_score")
        actual_status = ev.get("actual_status")
        if isinstance(actual_score, (int, float)) and not isinstance(actual_score, bool):
            err = round(abs(pred_score - float(actual_score)), 6)
            abs_errors.append(err)
        else:
            err = None
        agreed = (claimed_status == actual_status) if actual_status is not None else None
        if agreed is True:
            agreements += 1
        rows.append(
            {
                "capability_id": cid,
                "status_claim": claimed_status,
                "actual_status": actual_status,
                "predicted_score": pred_score,
                "measured_score": actual_score,
                "abs_calibration_error": err,
                "status_agreed": agreed,
                "evidence_pointer": cap["evidence_pointer"],
            }
        )

    evaluated_status_count = sum(1 for r in rows if r["status_agreed"] is not None)
    return {
        "schema": COMPARE_SCHEMA,
        "assessment_id": sealed_version.get("assessment_id"),
        "version": sealed_version.get("version"),
        "version_hash": sealed_version.get("version_hash"),
        "mean_abs_calibration_error": round(sum(abs_errors) / len(abs_errors), 6) if abs_errors else None,
        "status_agreement_rate": round(agreements / evaluated_status_count, 6) if evaluated_status_count else None,
        "capabilities": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifikator rantai penilaian-diri tersegel (AG101)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_verify = sub.add_parser("verify", help="Verifikasi rantai penilaian-diri JSONL")
    p_verify.add_argument("--chain", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "verify":
        versions = load_assessment_chain(args.chain)
        report = verify_assessment_chain(versions)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
