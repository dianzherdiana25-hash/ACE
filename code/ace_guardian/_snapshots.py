"""Batasi salinan fixture pada berkas reguler dan pertahankan identitas byte sumber."""
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat

from ._contracts import GuardianError, digest, integer, items, obj, schema

PART = re.compile(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,100}")
PROTECTED = {"evidence", "secrets", "ledger_penghasilan.md", "handover", "story_state", "evo0007"}
LIMIT = 2_000_000
DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def relative(value):
    if not isinstance(value, str) or len(value) > 300:
        raise GuardianError("Path fixture di luar batas.")
    parts = value.split("/")
    if any(not PART.fullmatch(part) or part.casefold() in PROTECTED or part.casefold().startswith(("secret", "story_state"))
           for part in parts):
        raise GuardianError("Path fixture tidak diizinkan.")
    return tuple(parts)


def open_file(root, name):
    parts = relative(name)
    descriptor = os.open(root, DIR)
    try:
        for part in parts[:-1]:
            following = os.open(part, DIR, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        info = os.fstat(leaf)
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT or info.st_nlink != 1:
            os.close(leaf)
            raise GuardianError("Input harus file lokal reguler tunggal pada batas snapshot.")
        return os.fdopen(leaf, "rb")
    finally:
        os.close(descriptor)


def read_fixture(root, name):
    with open_file(root, name) as stream:
        value = stream.read(LIMIT + 1)
    if len(value) > LIMIT:
        raise GuardianError("Berkas tumbuh melebihi batas saat dibaca.")
    return value


def fingerprint(data):
    return {"sha256": sha256(data).hexdigest(), "bytes": len(data)}


def validate_manifest(manifest):
    schema(manifest, "ace.guardian.snapshot.v1", ("files",))
    paths = set()
    total = 0
    for entry in items(manifest["files"], 900, 1):
        obj(entry, ("path", "sha256", "bytes"))
        parts = relative(entry["path"])
        if parts in paths:
            raise GuardianError("Berkas snapshot terdaftar ganda.")
        paths.add(parts)
        digest(entry["sha256"])
        total += integer(entry["bytes"], "Ukuran file snapshot", 0, LIMIT)
    if total > 30_000_000:
        raise GuardianError("Total snapshot melewati anggaran pengujian.")
    if any(path[:prefix] in paths for path in paths for prefix in range(1, len(path))):
        raise GuardianError("Daftar snapshot menggunakan berkas dan direktori dengan nama sama.")
    return manifest["files"]


def build_manifest(root, paths):
    chosen = items(paths, 900, 1)
    names = {relative(name): name for name in chosen}
    if len(chosen) != len(names):
        raise GuardianError("Berkas snapshot diminta ganda.")
    result = []
    for name in sorted(names.values()):
        data = read_fixture(root, name)
        result.append({"path": name, **fingerprint(data)})
    document = {"schema": "ace.guardian.snapshot.v1", "files": result}
    validate_manifest(document)
    return document


def verify(root, manifest, *, reject_extras=False):
    verified = {}
    for entry in validate_manifest(manifest):
        data = read_fixture(root, entry["path"])
        if fingerprint(data) != {key: entry[key] for key in ("sha256", "bytes")}:
            raise GuardianError(f"Isi snapshot berbeda: {entry['path']}")
        verified[entry["path"]] = data
    if reject_extras:
        directories = {str(parent) for name in verified for parent in PurePosixPath(name).parents if str(parent) != "."}
        seen = set()
        for path, folders, files in os.walk(root, followlinks=False):
            for leaf in folders + files:
                full = Path(path) / leaf
                name = str(full.relative_to(root))
                seen.add(name)
                if full.is_symlink() or (name not in verified and name not in directories):
                    raise GuardianError("Snapshot memuat symlink atau entri di luar manifest.")
        if seen != set(verified) | directories:
            raise GuardianError("Inventaris snapshot berubah saat dibaca.")
    return verified


def write_new(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
