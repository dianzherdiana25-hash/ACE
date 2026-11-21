"""Baca hash dan ukuran artefak lokal tanpa mengikuti symlink."""
import hashlib
import os
import stat


MAX_ARTIFACT_BYTES = 32 * 2**30


def _hash_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def inspect_file(root, relative):
    parts = relative.split("/")
    if not all(part and part not in (".", "..") and "\\" not in part for part in parts):
        return None, "invalid_artifact_path"
    parent = descriptor = None
    try:
        directory_flags = os.O_NOFOLLOW | os.O_RDONLY | os.O_DIRECTORY
        parent = os.open(root, directory_flags)
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=parent)
            os.close(parent)
            parent = next_fd
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_ARTIFACT_BYTES:
            return None, "artifact_type_or_size"
        hasher = hashlib.sha256()
        observed = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            observed += len(chunk)
            if observed > before.st_size:
                return None, "artifact_read_changed"
            hasher.update(chunk)
        after = os.fstat(descriptor)
        named = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if observed != before.st_size or _hash_identity(before) != _hash_identity(after) or _hash_identity(after) != _hash_identity(named):
            return None, "artifact_read_changed"
        return {"sha256": hasher.hexdigest(), "bytes": observed}, None
    except FileNotFoundError:
        return None, "artifact_missing"
    except OSError:
        return None, "artifact_unreadable_or_unsafe"
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)
