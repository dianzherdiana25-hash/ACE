"""Kemas bagian ZIP deterministik dan hemat pemeriksaan ulang artefak biner."""
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
import stat
import zipfile
from xml.sax.saxutils import escape, quoteattr

from ._contracts import ProductionError


STAMP = (1980, 1, 1, 0, 0, 0)
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def member_name(value):
    if (not isinstance(value, str) or len(value) > 400 or not value.isprintable()
            or ":" in value or "\\" in value or PurePosixPath(value).is_absolute()
            or any(piece in ("", ".", "..") for piece in value.split("/"))):
        raise ProductionError("Path bagian artefak perlu relatif tanpa lompatan.")
    return value


def package(parts, *, first=None):
    if first and first not in parts:
        raise ProductionError("Bagian pertama paket tidak ada.")
    memory = BytesIO()
    emitted = ([first] if first is not None else []) + sorted(set(parts) - {first})
    with zipfile.ZipFile(memory, "w", allowZip64=False) as bundle:
        for name in emitted:
            payload = parts[name]
            info = zipfile.ZipInfo(member_name(name), STAMP)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            compress = zipfile.ZIP_STORED if name == first else zipfile.ZIP_DEFLATED
            bundle.writestr(info, payload, compress_type=compress, compresslevel=6)
    return memory.getvalue()


def unpack(data, cap=24_000_000):
    if not isinstance(data, bytes) or len(data) > cap:
        raise ProductionError("Paket artefak terlalu besar atau bukan bytes.")
    try:
        with zipfile.ZipFile(BytesIO(data)) as bundle:
            index = bundle.infolist()
            if not 1 <= len(index) <= 2000 or sum(item.file_size for item in index) > cap:
                raise ProductionError("Ukuran terbuka atau anggota paket melewati batas.")
            found = {}
            used = set()
            for item in index:
                name = member_name(item.filename)
                if (name.casefold() in used or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16)
                        or item.compress_type not in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED)):
                    raise ProductionError("Bentuk bagian artefak tidak didukung.")
                used.add(name.casefold())
                found[name] = bundle.read(item)
            return found
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ProductionError("Paket artefak rusak.") from error


def xml(body):
    return (XML + body).encode("utf-8")


def e(value):
    return escape(str(value))


def a(value):
    return quoteattr(str(value))


def evidence(parts):
    return {key: {"sha256": sha256(value).hexdigest(), "bytes": len(value)} for key, value in sorted(parts.items())}
