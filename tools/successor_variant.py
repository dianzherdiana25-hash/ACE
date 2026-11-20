"""Pengemas & pemverifikasi arsip kelahiran varian penerus berdiff-tunggal (AG99).

Mengemas kelahiran varian penerus ke direktori arsip kustodi yang berisi:
1. Manifes diff-tunggal (``variant_manifest.json``): hanya tepat 1 berkas/diff target
   per kelahiran varian agar eksperimen penerus terisolasi dan dapat diatribusikan.
2. Catatan prediksi keunggulan pra-jalan (``pre_run_prediction.json``) tersegel SHA-256.
3. Berkas ``changes.diff`` serta salinan berkas/artefak dalam ``payload/`` beserta
   daftar hash SHA-256 per berkas dan ``archive_hash`` manifes kanonik.

Verifikator memeriksa integritas penuh round-trip dan menolak bila terjadi
mutasi diam-diam pada berkas apa pun maupun penyusupan multi-diff (>1 berkas diff).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


SCHEMA = "ace.successor-variant.v1"
PREDICTION_SCHEMA = "ace.successor-pre-run-prediction.v1"
MANIFEST_FILENAME = "variant_manifest.json"
PREDICTION_FILENAME = "pre_run_prediction.json"
DIFF_FILENAME = "changes.diff"


class VariantCustodyError(ValueError):
    """Galat validasi arsip kelahiran varian penerus (tampering atau multi-diff)."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(raw)


def _count_diff_targets(diff_text: str) -> list[str]:
    """Deteksi target berkas unik pada unified diff (``diff --git`` atau pasangan ``+++ ``)."""
    targets: list[str] = []
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ "):
            path_part = raw_line[4:].strip().split("\t", 1)[0]
            if path_part.startswith("b/"):
                path_part = path_part[2:]
            if path_part and path_part != "/dev/null" and path_part not in targets:
                targets.append(path_part)
    if not targets:
        # Fallback: cari header diff --git a/X b/Y jika tidak ada +++
        for raw_line in diff_text.splitlines():
            if raw_line.startswith("diff --git "):
                parts = raw_line.split()
                if len(parts) >= 4:
                    b_path = parts[3][2:] if parts[3].startswith("b/") else parts[3]
                    if b_path not in targets:
                        targets.append(b_path)
    return targets


def _validate_single_diff(diff_text: str, declared_target: str) -> str:
    target = declared_target.strip()
    if not target:
        raise VariantCustodyError("target_file diff tunggal wajib tidak kosong.")
    if not diff_text.strip():
        raise VariantCustodyError("Isi diff tidak boleh kosong.")
    detected = _count_diff_targets(diff_text)
    if len(detected) > 1:
        raise VariantCustodyError(
            f"Pelanggaran aturan diff-tunggal: diff menyentuh lebih dari 1 berkas ({detected})."
        )
    if detected and detected[0] != target:
        raise VariantCustodyError(
            f"Target di header diff ({detected[0]!r}) tidak cocok dengan target_file ({target!r})."
        )
    return target


def build_variant_archive(
    output_dir: str | Path,
    *,
    variant_id: str,
    origin_commit: str,
    target_file: str,
    diff_text: str,
    prediction: Mapping[str, Any],
    extra_files: Mapping[str, bytes | str] | None = None,
) -> dict[str, Any]:
    """Bangun arsip kustodi kelahiran varian dengan aturan diff-tunggal dan hash SHA-256."""
    vid = variant_id.strip()
    origin = origin_commit.strip()
    if not vid or not origin:
        raise VariantCustodyError("variant_id dan origin_commit wajib tidak kosong.")
    target = _validate_single_diff(diff_text, target_file)

    advantage_claim = str(prediction.get("expected_advantage") or "").strip()
    metric = str(prediction.get("success_metric") or "").strip()
    if not advantage_claim or not metric:
        raise VariantCustodyError(
            "Catatan prediksi pra-jalan wajib memuat expected_advantage dan success_metric."
        )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    payload_dir = out_path / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)

    diff_bytes = diff_text.encode("utf-8")
    (out_path / DIFF_FILENAME).write_bytes(diff_bytes)

    pred_payload = {
        "schema": PREDICTION_SCHEMA,
        "variant_id": vid,
        "origin_commit": origin,
        "expected_advantage": advantage_claim,
        "success_metric": metric,
        "stop_condition": str(prediction.get("stop_condition") or "Hentikan bila regresi > 0").strip(),
    }
    pred_bytes = (
        json.dumps(pred_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (out_path / PREDICTION_FILENAME).write_bytes(pred_bytes)

    file_records: list[dict[str, Any]] = [
        {
            "relpath": DIFF_FILENAME,
            "role": "single_diff",
            "bytes": len(diff_bytes),
            "sha256": _sha256_bytes(diff_bytes),
        },
        {
            "relpath": PREDICTION_FILENAME,
            "role": "pre_run_prediction",
            "bytes": len(pred_bytes),
            "sha256": _sha256_bytes(pred_bytes),
        },
    ]

    if extra_files:
        for rel_name, content in sorted(extra_files.items()):
            clean_rel = Path(rel_name).as_posix().lstrip("/")
            if ".." in Path(clean_rel).parts:
                raise VariantCustodyError(f"Jalur relatif tidak aman: {rel_name!r}.")
            member_path = payload_dir / clean_rel
            member_path.parent.mkdir(parents=True, exist_ok=True)
            raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
            member_path.write_bytes(raw_bytes)
            file_records.append(
                {
                    "relpath": f"payload/{clean_rel}",
                    "role": "artifact",
                    "bytes": len(raw_bytes),
                    "sha256": _sha256_bytes(raw_bytes),
                }
            )

    manifest_core = {
        "schema": SCHEMA,
        "variant_id": vid,
        "origin_commit": origin,
        "single_diff": {
            "target_file": target,
            "diff_path": DIFF_FILENAME,
            "diff_count": 1,
        },
        "pre_run_prediction_path": PREDICTION_FILENAME,
        "files": file_records,
    }
    manifest = dict(manifest_core)
    manifest["manifest_hash"] = _canonical_hash(manifest_core)
    (out_path / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_variant_archive(
    archive_dir: str | Path,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Verifikasi integritas SHA-256 penuh dan kepatuhan diff-tunggal atas arsip varian."""
    root = Path(archive_dir)
    errors: list[str] = []
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        errors.append(f"Manifes wajib tidak ditemukan: {MANIFEST_FILENAME}")
        report = {"schema": SCHEMA, "valid": False, "errors": errors, "verified_files": 0}
        if strict:
            raise VariantCustodyError("; ".join(errors))
        return report

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        errors.append(f"Schema manifes tidak cocok: {manifest.get('schema')!r}")

    core_keys = ("schema", "variant_id", "origin_commit", "single_diff", "pre_run_prediction_path", "files")
    manifest_core = {k: manifest.get(k) for k in core_keys}
    if manifest.get("manifest_hash") != _canonical_hash(manifest_core):
        errors.append("manifest_hash tidak cocok (manifes dimodifikasi).")

    single_diff = manifest.get("single_diff", {})
    if not isinstance(single_diff, Mapping) or single_diff.get("diff_count") != 1:
        errors.append("Aturan diff_count == 1 dilanggar pada manifes.")
    target_file = str(single_diff.get("target_file") or "") if isinstance(single_diff, Mapping) else ""
    diff_rel = str(single_diff.get("diff_path") or DIFF_FILENAME) if isinstance(single_diff, Mapping) else DIFF_FILENAME

    # Periksa setiap berkas terdaftar terhadap hash & byte di disk.
    files = manifest.get("files", [])
    declared_paths: set[str] = set()
    verified_count = 0
    for rec in files:
        relpath = str(rec.get("relpath") or "")
        declared_paths.add(relpath)
        fpath = root / relpath
        if not fpath.is_file():
            errors.append(f"Berkas terdeklarasi hilang: {relpath}")
            continue
        actual_bytes = fpath.read_bytes()
        actual_hash = _sha256_bytes(actual_bytes)
        if actual_hash != rec.get("sha256") or len(actual_bytes) != rec.get("bytes"):
            errors.append(f"Hash/ukuran berkas berubah (tampering): {relpath}")
        else:
            verified_count += 1

    # Periksa tidak ada berkas asing/tambahan disisipkan di luar manifes.
    allowed_on_disk = declared_paths | {MANIFEST_FILENAME}
    for disk_file in sorted(root.rglob("*")):
        if disk_file.is_file():
            rel = disk_file.relative_to(root).as_posix()
            if rel not in allowed_on_disk:
                errors.append(f"Berkas tak terdeklarasi ditemukan di arsip: {rel}")

    # Periksa ulang aturan diff-tunggal atas isi diff aktual di disk.
    diff_path = root / diff_rel
    if diff_path.is_file():
        try:
            _validate_single_diff(diff_path.read_text(encoding="utf-8"), target_file)
        except VariantCustodyError as exc:
            errors.append(str(exc))

    valid = len(errors) == 0
    report = {
        "schema": SCHEMA,
        "variant_id": manifest.get("variant_id"),
        "valid": valid,
        "verified_files": verified_count,
        "errors": errors,
    }
    if strict and not valid:
        raise VariantCustodyError("; ".join(errors))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifikator arsip kelahiran varian penerus (AG99)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_verify = sub.add_parser("verify", help="Verifikasi direktori arsip varian")
    p_verify.add_argument("--archive", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "verify":
        report = verify_variant_archive(args.archive)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["valid"] else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
