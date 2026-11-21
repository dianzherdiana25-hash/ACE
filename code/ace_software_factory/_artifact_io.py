"""Baca artefak relatif root dengan pemeriksaan descriptor dan ukuran."""
from hashlib import sha256
import os
import stat

from ._contracts import ContractError
from .repo_scaffolder import _relative


def read_relative(root, relative, maximum, expected=None):
    if not isinstance(relative, str) or not relative.isprintable() or len(relative) > 500:
        raise ContractError("Path artefak tidak sah.")
    parts = _relative(relative)
    directory_flags = os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY
    parent = os.open(root, directory_flags)
    descriptor = None
    try:
        for component in parts[:-1]:
            child = os.open(component, directory_flags, dir_fd=parent)
            os.close(parent)
            parent = child
        descriptor = os.open(parts[-1], os.O_NOFOLLOW | os.O_NONBLOCK | os.O_RDONLY, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise ContractError("Berkas tidak reguler atau melampaui batas.")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(maximum+1)
            after = os.fstat(stream.fileno())
        if len(data) > maximum or before.st_size != len(data) or (
                before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
            raise ContractError("Artefak berubah saat dibaca.")
        if expected is not None and sha256(data).hexdigest() != expected:
            raise ContractError("SHA-256 artefak berbeda dari komitmen.")
        return data
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)
