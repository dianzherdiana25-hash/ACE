"""Simpan hasil persepsi imutabel berdasarkan media, operasi dan pengaturan.

Cache memverifikasi SHA-256 media, kunci permintaan, dan payload
setiap hit. Versi algoritme eksplisit mencegah penggunaan hasil
lama setelah perubahan semantik. Entry dibuat tanpa mengganti
data dan opsi waktu baca memakai cap waktu yang diberikan caller.
"""
import argparse
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from . import _perception_io, _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .ocr_engine import _pairs
from .perceptual_memory import _digest, _utc


MAX_MEDIA_BYTES = 32_000_000
MAX_VALUE_BYTES = 8_000_000
MAX_KEY_BYTES = 64_000


def key_for(media, request):
    if not isinstance(media, bytes) or not 1 <= len(media) <= MAX_MEDIA_BYTES:
        raise ValueError("Ukuran media cache di luar batas.")
    data = _vision.spec(request, "ace.perception-cache-request.v1",
                        ("media_sha256", "operation", "algorithm_revision", "settings"))
    media_sha = sha256(media).hexdigest()
    if _digest(data["media_sha256"]) != media_sha:
        raise ValueError("Media berbeda dari permintaan cache.")
    identity = {"media_sha256": media_sha, "operation": _token(data["operation"], "Operasi"),
                "algorithm_revision": _token(data["algorithm_revision"], "Revisi algoritme"),
                "settings": data["settings"]}
    if not isinstance(identity["settings"], dict) or len(_canonical(identity)) > MAX_KEY_BYTES:
        raise ValueError("Pengaturan cache terlalu besar atau tidak sah.")
    return _sha(identity), identity


def _load(raw, key, identity):
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(result, dict) or set(result) != {
            "schema", "key", "identity", "stored_at", "result", "result_sha256", "entry_sha256"}:
        raise ValueError("Struktur entry cache tidak sah.")
    if (result["schema"] != "ace.perception-cache-entry.v1" or result["key"] != key
            or _canonical(result["identity"]) != _canonical(identity) or not isinstance(result["result"], dict)
            or result["result_sha256"] != _sha(result["result"])):
        raise ValueError("Kunci atau checksum hasil cache tidak cocok.")
    bound = {field: value for field, value in result.items() if field != "entry_sha256"}
    if result["entry_sha256"] != _sha(bound) or raw != _canonical(result)+b"\n":
        raise ValueError("Checksum entry atau representasi cache tidak cocok.")
    _utc(result["stored_at"])
    return result


def lookup(root, media, request, *, as_of=None, max_age_seconds=None):
    key, identity = key_for(media, request)
    latest = _utc(as_of) if as_of is not None else None
    ttl = None
    if max_age_seconds is not None:
        if latest is None:
            raise ValueError("Batas umur membutuhkan cap waktu pemeriksaan.")
        ttl = timedelta(seconds=_integer(max_age_seconds, 0, 31_536_000, "Batas umur"))
    try:
        raw = _perception_io.read_relative(root, key+".json", MAX_VALUE_BYTES+MAX_KEY_BYTES+2048)
    except FileNotFoundError:
        return {"key": key, "status": "miss", "entry": None}
    entry = _load(raw, key, identity)
    age = latest-_utc(entry["stored_at"]) if latest is not None else None
    if age is not None and age < timedelta(0):
        raise ValueError("Entry berasal dari masa depan.")
    if ttl is not None and age > ttl:
        return {"key": key, "status": "stale", "entry": None}
    return {"key": key, "status": "hit", "entry": entry}


def store(root, media, request, value, stored_at):
    key, identity = key_for(media, request)
    stamp = _utc(stored_at).isoformat()
    if not isinstance(value, dict) or len(_canonical(value)) > MAX_VALUE_BYTES:
        raise ValueError("Hasil cache perlu objek JSON dalam batas byte.")
    record = {"schema": "ace.perception-cache-entry.v1", "key": key, "identity": identity,
              "stored_at": stamp, "result": value, "result_sha256": _sha(value)}
    record["entry_sha256"] = _sha(record)
    if root.is_symlink():
        raise ValueError("Root cache tidak boleh berupa symlink.")
    root.mkdir(mode=0o700, exist_ok=True)
    parent = os.open(root, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY)
    temp = ".stage-"+uuid4().hex
    created = False
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=parent)
        created = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical(record)+b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, key+".json", src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        except FileExistsError:
            raw = _perception_io.read_relative(parent, key+".json", MAX_VALUE_BYTES+MAX_KEY_BYTES+2048)
            current = _load(raw, key, identity)
            if current["result_sha256"] != record["result_sha256"]:
                raise ValueError("Kunci cache sudah berisi hasil berbeda.")
            return {"key": key, "status": "reused", "entry": current}
        return {"key": key, "status": "stored", "entry": record}
    finally:
        try:
            if created:
                os.unlink(temp, dir_fd=parent)
        finally:
            os.close(parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("media", type=Path)
    parser.add_argument("request", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lookup", action="store_true")
    group.add_argument("--store", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--max-age-seconds", type=int)
    args = parser.parse_args(argv)
    try:
        media, request = _raster.read(args.media, MAX_MEDIA_BYTES), _raster.read(args.request, _vision.MAX_SPEC_BYTES)
        if args.lookup:
            result = lookup(args.root, media, request, as_of=args.as_of, max_age_seconds=args.max_age_seconds)
        else:
            if args.max_age_seconds is not None or args.as_of is None:
                raise ValueError("Penyimpanan memerlukan cap waktu eksplisit.")
            value = json.loads(_raster.read(args.store, MAX_VALUE_BYTES).decode("utf-8"), object_pairs_hook=_pairs)
            result = store(args.root, media, request, value, args.as_of)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] in ("miss", "stale"))


if __name__ == "__main__":
    raise SystemExit(main())
