"""Susun dataset dari contoh yang payload-nya dicocokkan ke indeks verifikasi.

Indeks verifikasi diterbitkan terpisah oleh pemanggil. Status verified
harus menunjuk hash payload, lisensi, dan rujukan verifier. Modul
menjaga keluarga yang sama dalam satu partisi dan menahan duplikat
prompt sebelum membagi dataset, sehingga duplikat persis tidak memberi
kebocoran ke held-out. Keluaran JSONL kanonis ditulis ke stdout.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string


MAX_ROWS = 25_000
MAX_BYTES = 32_000_000
FIELDS = ("event_id", "family_id", "task_kind", "language", "prompt", "target")
PROOF_FIELDS = ("event_id", "status", "payload_sha256", "evidence_ref", "license")


@dataclass(frozen=True, slots=True)
class Source:
    event_id: str
    family: str
    task_kind: str
    language: str
    prompt: str
    target: str

    @classmethod
    def read(cls, raw):
        object_fields(raw, FIELDS)
        identifiers = [string(raw[key], key, preserve=True) for key in FIELDS[:4]]
        if any(value.strip() != value for value in identifiers):
            raise InputError("ID, task_kind dan bahasa harus sudah dirapikan.")
        return cls(*identifiers, string(raw["prompt"], "prompt", max_chars=16_000, preserve=True),
                   string(raw["target"], "target", max_chars=16_000, preserve=True))

    def export(self):
        return dict(zip(FIELDS, (self.event_id, self.family, self.task_kind, self.language, self.prompt, self.target)))

    @property
    def prompt_identity(self):
        # Identitas hanya untuk pemeriksaan kebocoran, sehingga byte asli
        # konten dalam keluaran tetap sama dengan byte yang diverifikasi.
        return " ".join(unicodedata.normalize("NFC", self.prompt).split())


@dataclass(frozen=True, slots=True)
class Proof:
    event_id: str
    state: str
    payload_sha: str
    ref: str
    license_id: str

    @classmethod
    def read(cls, raw):
        object_fields(raw, PROOF_FIELDS)
        status = string(raw["status"], "status")
        if status not in {"verified", "rejected", "pending"}:
            raise InputError("Status verifikasi tidak dikenal.")
        return cls(string(raw["event_id"], "ID peristiwa"), status, digest(raw["payload_sha256"]),
                   string(raw["evidence_ref"], "sumber verifier"), string(raw["license"], "lisensi"))


def _by_event(raw, read):
    events = {}
    for value in entries(raw, MAX_ROWS):
        item = read(value)
        if item.event_id in events:
            raise InputError(f"ID peristiwa ganda {item.event_id}.")
        events[item.event_id] = item
    return events


def _partition(seed, family, basis_points):
    # Ambang eksak dalam basis point dengan urutan byte yang tetap.
    raw = canonical([seed, family])
    bucket = int.from_bytes(hashlib.sha256(raw).digest(), "big")
    return "held_out" if bucket * 10_000 < basis_points * 2**256 else "train"


def _record(candidate, verified, split, index_ref):
    payload = candidate.export()
    return {
        "schema": "ace.forge-example.v1", "example_id": "forge-" + identity(payload),
        "split": split, "payload": payload,
        "provenance": {"evidence_ref": verified.ref, "index_ref": index_ref,
                       "payload_sha256": verified.payload_sha, "license": verified.license_id},
    }


def forge(raw, verification):
    object_fields(raw, ("examples", "seed", "held_out_basis_points", "allowed_licenses"))
    object_fields(verification, ("index_ref", "records"))
    index_ref = string(verification["index_ref"], "rujukan katalog verifier")
    seed = integer(raw["seed"], 0, 2**64 - 1)
    basis_points = integer(raw["held_out_basis_points"], 0, 10_000)
    allowed = [string(value, "lisensi diizinkan") for value in entries(raw["allowed_licenses"], 100)]
    if not allowed or len(set(allowed)) != len(allowed):
        raise InputError("Deklarasikan lisensi unik yang diizinkan.")
    sources = _by_event(raw["examples"], Source.read)
    verifications = _by_event(verification["records"], Proof.read)
    evidence_refs = {proof.ref for proof in verifications.values()}
    if len(evidence_refs) != len(verifications) or index_ref in evidence_refs:
        raise InputError("Rujukan verifier harus unik serta terpisah dari rujukan indeks.")

    rejected = []
    eligible = defaultdict(list)
    for key, row in sorted(sources.items()):
        proof = verifications.get(key)
        if proof is None:
            reason = "verification_missing"
        elif proof.state != "verified":
            reason = f"verification_{proof.state}"
        elif proof.payload_sha != identity(row.export()):
            reason = "payload_changed"
        elif proof.license_id not in allowed:
            reason = "license_not_allowed"
        else:
            eligible[row.prompt_identity].append(row)
            continue
        item = {"event_id": key, "reason": reason}
        if proof is not None:
            item["evidence_ref"] = proof.ref
        rejected.append(item)
    records = []
    for group in eligible.values():
        if len({candidate.target for candidate in group}) > 1:
            rejected.extend({"event_id": candidate.event_id, "reason": "conflicting_prompt",
                             "evidence_ref": verifications[candidate.event_id].ref} for candidate in group)
            continue
        one, *copies = group
        records.append(_record(one, verifications[one.event_id], _partition(seed, one.family, basis_points), index_ref))
        rejected.extend({"event_id": copy.event_id, "reason": "duplicate_prompt", "retained_event": one.event_id,
                         "evidence_ref": verifications[copy.event_id].ref} for copy in copies)
    records.sort(key=lambda item: item["payload"]["event_id"])
    if sum(len(canonical(record)) + 1 for record in records) > MAX_BYTES:
        raise InputError("Dataset hasil melebihi batas byte.")
    partitions = Counter(row["split"] for row in records)
    coverage = Counter(row["payload"]["task_kind"] for row in records)
    report = {
        "schema": "ace.dataset-forge-report.v1", "verification_index_ref": index_ref,
        "seed": seed, "held_out_basis_points": basis_points, "sources": len(sources), "examples": len(records),
        "train": partitions["train"], "held_out": partitions["held_out"], "task_kind": dict(sorted(coverage.items())),
        "rejected": sorted(rejected, key=lambda item: item["event_id"]),
        "unused_verifications": sorted(verifications.keys() - sources.keys()),
    }
    return records, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--verified-index", required=True, type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        raw = decode(read_bytes(args.input, MAX_BYTES))
        verified = decode(read_bytes(args.verified_index, MAX_BYTES))
        records, report = forge(raw, verified)
        if args.report_only:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for record in records:
                sys.stdout.write(canonical(record).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
