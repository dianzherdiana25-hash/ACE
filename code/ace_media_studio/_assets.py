"""Baca artefak relatif melalui descriptor agar nama tidak bisa keluar root."""
from hashlib import sha256
import os
from pathlib import PurePosixPath
import stat

from ._contracts import ContractError, digest


def asset(root, relative, expected, cap):
    if not isinstance(relative, str) or not relative or len(relative) > 400:
        raise ContractError("Path aset perlu diisi dalam batas.")
    parts = relative.split("/")
    if PurePosixPath(relative).is_absolute() or any(part in ("", ".", "..") for part in parts):
        raise ContractError("Path aset harus relatif tanpa lompatan.")
    digest(expected)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(root, flags)
    try:
        for component in parts[:-1]:
            child = os.open(component, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
                raise ContractError("Aset harus berkas reguler dalam batas.")
            data = stream.read(cap + 1)
    except OSError as error:
        raise ContractError("Aset lokal tidak dapat dibaca secara aman.") from error
    finally:
        os.close(parent)
    if len(data) > cap or sha256(data).hexdigest() != expected:
        raise ContractError("Ukuran atau hash aset berbeda dari kontrak.")
    return data
