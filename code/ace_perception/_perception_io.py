"""Baca berkas lokal relatif root dengan descriptor dan batas ukuran."""
from hashlib import sha256
import os
from pathlib import PurePosixPath
import stat


def relative_parts(value):
    if (not isinstance(value, str) or not value or len(value) > 512 or "\\" in value
            or any(not character.isprintable() for character in value)):
        raise ValueError("Path relatif tidak sah.")
    parts = value.split("/")
    if any(item in ("", ".", "..") for item in parts) or PurePosixPath(value).is_absolute():
        raise ValueError("Path harus berada di dalam root.")
    return tuple(parts)


def read_relative(root, relative, limit, expected=None):
    parts = relative_parts(relative)
    directory_flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
    parent = os.dup(root) if type(root) is int else os.open(root, directory_flags)
    fd = None
    try:
        for item in parts[:-1]:
            child = os.open(item, directory_flags, dir_fd=parent)
            os.close(parent)
            parent = child
        flags = os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY
        fd = os.open(parts[-1], flags, dir_fd=parent)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Berkas bukan data reguler atau melampaui batas byte.")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            data = stream.read(limit+1)
            after = os.fstat(stream.fileno())
        if len(data) > limit or len(data) != info.st_size or (info.st_mtime_ns, info.st_ctime_ns) != (
                after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Berkas berubah saat pembacaan.")
        if expected is not None and sha256(data).hexdigest() != expected:
            raise ValueError("Hash byte sumber tidak cocok.")
        return data
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)
