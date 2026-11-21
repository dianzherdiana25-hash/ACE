"""Tambatkan setiap contoh dataset ke rujukan verifikasi dalam rantai hash.

Manifest berisi hash byte dataset dan rantai menurut urutan baris.
Verifier memerlukan head SHA-256 dari saluran tepercaya pemanggil,
sehingga mengganti dataset dan manifest sekaligus tetap terdeteksi.
Hash membuktikan perubahan byte relatif terhadap anchor atas bukti
yang diberikan. Keabsahan substantif atau lisensi sumber memerlukan
verifier asal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, identity, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES, MAX_ROWS, Source


SCHEMA = "ace.dataset-custody.v1"
EXAMPLE_LIMIT = 200_000
MAX_MANIFEST_BYTES = 4 * MAX_BYTES


def _entry(raw):
    object_fields(raw, ("schema", "example_id", "split", "payload", "provenance"))
    if raw["schema"] != "ace.forge-example.v1" or raw["split"] not in ("train", "held_out"):
        raise InputError("Skema atau partisi contoh tidak dikenal.")
    example = Source.read(raw["payload"])
    provenance = raw["provenance"]
    object_fields(provenance, ("index_ref", "evidence_ref", "payload_sha256", "license"))
    pointers = {key: string(provenance[key], key) for key in ("index_ref", "evidence_ref", "license")}
    if pointers["index_ref"] == pointers["evidence_ref"]:
        raise InputError("Indeks dan rujukan bukti harus berbeda.")
    payload_hash = digest(provenance["payload_sha256"])
    if identity(example.export()) != payload_hash or raw["example_id"] != f"forge-{payload_hash}":
        raise InputError("ID atau hash payload tidak cocok dengan isi contoh.")
    return example, pointers, payload_hash


def _collect(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise InputError("Dataset harus byte dan berada di bawah batas ukuran.")
    if data and not data.endswith(b"\n"):
        raise InputError("Dataset perlu LF pada akhir setiap baris.")
    if not data:
        return []
    lines = data[:-1].split(b"\n")
    if len(lines) > MAX_ROWS:
        raise InputError("Terlalu banyak baris dataset.")
    found = []
    ids, events, prompts, evidence, families = set(), set(), set(), set(), {}
    for number, line in enumerate(lines, 1):
        if len(line) > EXAMPLE_LIMIT:
            raise InputError(f"Baris {number} melebihi batas byte.")
        try:
            raw = decode(line)
            if canonical(raw) != line:
                raise InputError("Baris wajib memakai JSON kanonis.")
            example, pointers, payload_hash = _entry(raw)
            split = raw["split"]
            index_ref, evidence_ref = pointers["index_ref"], pointers["evidence_ref"]
            example_id = raw["example_id"]
            if example_id in ids or example.event_id in events or evidence_ref in evidence:
                raise InputError("ID contoh, event, atau bukti ganda.")
            if example.prompt_identity in prompts:
                raise InputError("Prompt ganda di dataset yang sama.")
            if example.family in families and families[example.family] != split:
                raise InputError("Satu keluarga berada di dua partisi.")
        except (ValueError, RecursionError) as exc:
            raise InputError(f"Baris dataset {number} tidak sah.") from exc
        ids.add(example_id)
        events.add(example.event_id)
        prompts.add(example.prompt_identity)
        evidence.add(evidence_ref)
        families[example.family] = split
        found.append({
            "line": number, "example_id": example_id, "event_id": example.event_id,
            "split": split, "entry_sha256": hashlib.sha256(line).hexdigest(),
            "payload_sha256": payload_hash, "evidence_ref": evidence_ref, "index_ref": index_ref,
            "license": pointers["license"],
        })
    return found


def seal(data, dataset_ref):
    dataset_ref = string(dataset_ref, "rujukan dataset")
    records = _collect(data)
    header = {
        "schema": SCHEMA, "dataset_ref": dataset_ref, "byte_count": len(data),
        "record_count": len(records), "dataset_sha256": hashlib.sha256(data).hexdigest(),
    }
    first = previous = identity(header)
    indexed = []
    for row in records:
        entry = {**row, "previous_sha256": previous}
        previous = identity(entry)
        indexed.append({**entry, "chain_sha256": previous})
    return {**header, "genesis_sha256": first, "head_sha256": previous, "records": indexed}


def _record_view(row, *, compare_chain):
    if compare_chain or not isinstance(row, dict):
        return row
    return {key: value for key, value in row.items() if key not in ("previous_sha256", "chain_sha256")}


def verify(data, manifest, expected_head):
    digest(expected_head)
    object_fields(manifest, ("schema", "dataset_ref", "byte_count", "record_count",
                             "dataset_sha256", "genesis_sha256", "head_sha256", "records"))
    if manifest["schema"] != SCHEMA:
        raise InputError("Skema manifest tidak dikenal.")
    blockers = []
    if manifest["head_sha256"] != expected_head:
        blockers.append("expected_head_mismatch")
    actual = None
    try:
        actual = seal(data, manifest["dataset_ref"])
    except InputError as exc:
        blockers.append(str(exc))
    mismatch = None
    if actual is not None:
        for key in ("byte_count", "record_count", "dataset_sha256", "genesis_sha256", "head_sha256"):
            # Boolean tidak menyamai jumlah 0 atau 1.
            if type(manifest[key]) is not type(actual[key]) or manifest[key] != actual[key]:
                blockers.append(f"{key}_mismatch")
        if not isinstance(manifest["records"], list) or len(manifest["records"]) > MAX_ROWS:
            blockers.append("records_invalid")
        else:
            # Header yang berubah mengubah seluruh rantai. Pada kondisi itu,
            # lokalisasikan perbedaan data per baris. Pemeriksaan head tetap
            # menahan perubahan rantai maupun data.
            compare_chain = manifest["dataset_sha256"] == actual["dataset_sha256"]
            for index, (given, observed) in enumerate(zip(manifest["records"], actual["records"]), 1):
                expected = _record_view(given, compare_chain=compare_chain)
                outcome = _record_view(observed, compare_chain=compare_chain)
                if canonical(expected) != canonical(outcome):
                    mismatch = index
                    break
            if mismatch is None and len(manifest["records"]) != len(actual["records"]):
                mismatch = min(len(manifest["records"]), len(actual["records"])) + 1
            if mismatch is not None:
                blockers.append("records_mismatch")
    return {
        "schema": "ace.dataset-custody-verification.v1", "valid": not blockers, "expected_head_sha256": expected_head,
        "observed_head_sha256": actual["head_sha256"] if actual is not None else None,
        "first_record_mismatch": mismatch, "blockers": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seal_parser = sub.add_parser("seal", help="Cetak manifest dari dataset JSONL.")
    seal_parser.add_argument("dataset", type=Path)
    seal_parser.add_argument("--dataset-ref", required=True)
    verify_parser = sub.add_parser("verify", help="Periksa dataset terhadap manifest dan head eksternal.")
    verify_parser.add_argument("dataset", type=Path)
    verify_parser.add_argument("manifest", type=Path)
    verify_parser.add_argument("--expect-head", required=True)
    args = parser.parse_args(argv)
    try:
        data = read_bytes(args.dataset, MAX_BYTES)
        if args.command == "seal":
            result = seal(data, args.dataset_ref)
            code = 0
        else:
            manifest = decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES))
            result = verify(data, manifest, args.expect_head)
            code = 0 if result["valid"] else 1
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
