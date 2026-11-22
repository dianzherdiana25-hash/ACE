"""Arsipkan debat sebagai paket preseden yang bisa diperiksa byte demi byte.

Paket memuat transcript, bahan ajar yang dibangun dari giliran tercatat,
dan manifest. Verifier membuka tepat tiga anggota yang diizinkan, tanpa
ekstraksi. SHA-256 dari luar paket dapat dipakai sebagai jangkar kustodi.
"""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZIP_STORED, ZipFile, ZipInfo

from .debate_protocol import MAX_INPUT_BYTES, verify_report


MAX_ARCHIVE = 12_000_000
MAX_MEMBER = 6_000_000
_FILES = ("lesson.json", "manifest.json", "transcript.json")


class ArchiveError(ValueError):
    """Paket preseden tidak lengkap, kanonis, atau dapat diverifikasi."""


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise ArchiveError("Field arsip tidak sesuai skema.")


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise ArchiveError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ArchiveError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _lesson(transcript, case_ref, tags):
    turns = {item["turn_id"]: item for item in transcript["turns"]}
    decision = transcript["decision"]
    digest = transcript["sha256"]
    return {
        "schema": "ace.debate-lesson.v1", "case_ref": case_ref, "tags": tags,
        "question": transcript["plan"]["question"], "debate_id": transcript["plan"]["debate_id"],
        "debate_sha256": digest, "outcome_recorded": decision["outcome"],
        "decision_rationale": decision["rationale"],
        "decision_basis": [turns[key] for key in decision["basis_turns"]],
        "dissent": [turns[key] for key in transcript["dissent_turns"]],
    }


def _members(raw):
    _shape(raw, ("case_ref", "tags", "transcript"))
    case_ref = _text(raw["case_ref"], "rujukan kasus", 512)
    tags = raw["tags"]
    if not isinstance(tags, list) or not 1 <= len(tags) <= 64:
        raise ArchiveError("Arsip perlu daftar topik berbatas.")
    labels = sorted(_text(value, "topik", 96) for value in tags)
    if len(labels) != len(set(labels)):
        raise ArchiveError("Tag arsip ganda.")
    transcript = raw["transcript"]
    if not verify_report(transcript) or transcript["decision"] is None:
        raise ArchiveError("Arsip memerlukan transcript putusan yang bisa diputar ulang.")
    payloads = {"transcript.json": _canonical(transcript),
                "lesson.json": _canonical(_lesson(transcript, case_ref, labels))}
    manifest = {
        "schema": "ace.debate-archive.v1",
        "case_ref": case_ref, "tags": labels, "debate_sha256": transcript["sha256"],
        "members": [{"name": key, "size": len(blob), "sha256": _sha(blob)}
                    for key, blob in sorted(payloads.items())],
    }
    payloads["manifest.json"] = _canonical(manifest)
    if any(len(blob) > MAX_MEMBER for blob in payloads.values()):
        raise ArchiveError("Anggota arsip melampaui batas.")
    return payloads


def build_archive(raw):
    files = _members(raw)
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_STORED) as archive:
        for name in _FILES:
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, files[name])
    data = output.getvalue()
    if len(data) > MAX_ARCHIVE:
        raise ArchiveError("Arsip melampaui batas ukuran.")
    return data


def verify_archive(data, *, expected_sha256=None):
    if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE:
        raise ArchiveError("Arsip bukan bytes berbatas.")
    actual = _sha(data)
    if expected_sha256 is not None and actual != expected_sha256:
        raise ArchiveError("Arsip berbeda dari hash eksternal.")
    with ZipFile(BytesIO(data)) as source:
        items = source.infolist()
        if sorted(item.filename for item in items) != list(_FILES):
            raise ArchiveError("Anggota arsip asing, ganda, atau hilang.")
        if any(item.file_size > MAX_MEMBER or item.compress_type != ZIP_STORED
               or item.compress_size != item.file_size or item.flag_bits & 1
               or not stat.S_ISREG(item.external_attr >> 16) for item in items):
            raise ArchiveError("Anggota arsip bukan blob reguler yang diizinkan.")
        raw = {item.filename: json.loads(source.read(item)) for item in items}
    manifest = raw["manifest.json"]
    _shape(manifest, ("schema", "case_ref", "tags", "debate_sha256", "members"))
    request = {"case_ref": manifest["case_ref"], "tags": manifest["tags"], "transcript": raw["transcript.json"]}
    regenerated = build_archive(request)
    if regenerated != data:
        raise ArchiveError("Isi atau serialisasi arsip tidak cocok dengan replay.")
    return {"schema": "ace.debate-archive-verification.v1", "archive_sha256": actual,
            "external_digest_checked": expected_sha256 is not None, "manifest": manifest,
            "lesson": raw["lesson.json"]}


def _read(path, limit):
    with path.open("rb") as handle:
        blob = handle.read(limit + 1)
    if len(blob) > limit:
        raise ArchiveError("Berkas masukan melampaui batas.")
    return blob


def _save_new(path, data):
    temporary = None
    try:
        with NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # Publikasikan keluaran lokal secara atomik dengan syarat path masih kosong.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    build = commands.add_parser("build")
    build.add_argument("input", type=Path)
    build.add_argument("output", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("archive", type=Path)
    verify.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    try:
        if args.operation == "build":
            data = build_archive(json.loads(_read(args.input, MAX_INPUT_BYTES)))
            report = verify_archive(data)
            _save_new(args.output, data)
        else:
            data = _read(args.archive, MAX_ARCHIVE)
            report = verify_archive(data, expected_sha256=args.expected_sha256)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, BadZipFile, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
