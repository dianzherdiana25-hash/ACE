"""Dekode kode batang dan QR dari raster lokal dengan ZBar.

Proses mengenali payload dan lokasi, tanpa memakai payload sebagai
perintah atau membuka alamat yang dilaporkan. Mode hash-only
merekam identitas payload tanpa mengungkap isinya. Jenis kode
dibatasi daftar eksplisit sebelum scanner dibuka.
"""
import argparse
import base64
import ctypes
from ctypes.util import find_library
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical


FORMATS = {"EAN8": 8, "UPCE": 9, "UPCA": 12, "EAN13": 13, "CODE39": 39, "QRCODE": 64, "CODE128": 128}
MAX_CODES = 128
MAX_BYTES_PER_SYMBOL = 8192
MAX_LOCATIONS = 1024
MAX_CODE_PIXELS = 1_600_000
_Y800 = int.from_bytes(b"Y800", "little")


def _library():
    name = find_library("zbar")
    if not name:
        raise ValueError("libzbar lokal diperlukan untuk pembacaan kode.")
    try:
        lib = ctypes.CDLL(name)
    except OSError as error:
        raise ValueError("libzbar lokal tidak dapat dimuat.") from error
    ptr = ctypes.c_void_p
    u = ctypes.c_uint
    i = ctypes.c_int
    n = ctypes.c_ulong
    functions = {
        "image_scanner_create": (ptr, []), "image_scanner_destroy": (None, [ptr]),
        "image_scanner_set_config": (i, [ptr, i, i, i]),
        "image_create": (ptr, []), "image_destroy": (None, [ptr]),
        "image_set_format": (None, [ptr, n]), "image_set_size": (None, [ptr, u, u]),
        "image_set_data": (None, [ptr, ptr, n, ptr]), "scan_image": (i, [ptr, ptr]),
        "image_first_symbol": (ptr, [ptr]), "symbol_next": (ptr, [ptr]),
        "symbol_get_type": (i, [ptr]), "symbol_get_data_length": (u, [ptr]), "symbol_get_data": (ptr, [ptr]),
        "symbol_get_loc_size": (u, [ptr]), "symbol_get_loc_x": (i, [ptr, u]), "symbol_get_loc_y": (i, [ptr, u]),
        "symbol_get_quality": (i, [ptr]),
    }
    try:
        for key, (output, args) in functions.items():
            handle = getattr(lib, "zbar_"+key)
            handle.restype = output
            handle.argtypes = args
    except AttributeError as error:
        raise ValueError("ABI libzbar tidak didukung.") from error
    return lib


def _symbol(lib, ptr, formats, expose):
    kind = lib.zbar_symbol_get_type(ptr)
    names = {number: name for name, number in formats.items()}
    if kind not in names:
        return None
    length = lib.zbar_symbol_get_data_length(ptr)
    count = lib.zbar_symbol_get_loc_size(ptr)
    address = lib.zbar_symbol_get_data(ptr)
    if length > MAX_BYTES_PER_SYMBOL or count > MAX_LOCATIONS or (length and not address):
        raise ValueError("Ukuran simbol hasil di luar batas.")
    payload = ctypes.string_at(address, length)
    points = [[lib.zbar_symbol_get_loc_x(ptr, index), lib.zbar_symbol_get_loc_y(ptr, index)]
              for index in range(count)]
    evidence = {"format": names[kind], "payload_sha256": sha256(payload).hexdigest(),
                "payload_bytes": length, "points": points, "quality": lib.zbar_symbol_get_quality(ptr)}
    if expose:
        try:
            value = payload.decode("utf-8")
        except UnicodeDecodeError:
            evidence.update(encoding="base64", data=base64.b64encode(payload).decode("ascii"))
        else:
            evidence.update(encoding="utf-8", data=value)
    return evidence


def scan(data, *, formats=("QRCODE", "EAN13", "CODE128"), hash_only=False):
    if (not isinstance(formats, (list, tuple)) or not formats or len(formats) > len(FORMATS)
            or any(not isinstance(name, str) or name not in FORMATS for name in formats)
            or len(set(formats)) != len(formats) or type(hash_only) is not bool):
        raise ValueError("Daftar format atau mode payload tidak sah.")
    requested = {name: FORMATS[name] for name in formats}
    raster = _raster.decode(data)
    if raster.width*raster.height > MAX_CODE_PIXELS:
        raise ValueError("Raster kode melampaui batas.")
    library = _library()
    scanner = library.zbar_image_scanner_create()
    if not scanner:
        raise ValueError("Scanner lokal gagal dibuat.")
    handle = None
    try:
        if library.zbar_image_scanner_set_config(scanner, 0, 0, 0):
            raise ValueError("Scanner gagal menonaktifkan format bawaan.")
        for number in requested.values():
            if library.zbar_image_scanner_set_config(scanner, number, 0, 1):
                raise ValueError("Scanner gagal mengaktifkan format.")
        handle = library.zbar_image_create()
        if not handle:
            raise ValueError("Buffer raster scanner gagal dibuat.")
        pixels = _vision.normalized(raster)
        buffer = ctypes.create_string_buffer(pixels, len(pixels))
        library.zbar_image_set_format(handle, _Y800)
        library.zbar_image_set_size(handle, raster.width, raster.height)
        library.zbar_image_set_data(handle, ctypes.cast(buffer, ctypes.c_void_p), len(pixels), None)
        size = library.zbar_scan_image(scanner, handle)
        if not 0 <= size <= MAX_CODES:
            raise ValueError("Scanner gagal atau jumlah kode melampaui batas.")
        rows = []
        current = library.zbar_image_first_symbol(handle)
        visited = 0
        while current:
            visited += 1
            if visited > MAX_CODES:
                raise ValueError("Daftar simbol melebihi batas.")
            result = _symbol(library, current, requested, not hash_only)
            if result is not None:
                rows.append(result)
            current = library.zbar_symbol_next(current)
        rows.sort(key=lambda item: (item["format"], item["payload_sha256"], item["points"]))
    finally:
        if handle:
            library.zbar_image_destroy(handle)
        library.zbar_image_scanner_destroy(scanner)
    return {"schema": "ace.perception-code-read.v1", "source_sha256": sha256(data).hexdigest(),
            "size": [raster.width, raster.height], "formats": sorted(formats), "hash_only": hash_only, "codes": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--format", action="append", choices=sorted(FORMATS))
    parser.add_argument("--hash-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        options = {"formats": args.format} if args.format else {}
        report = scan(_raster.read(args.image), hash_only=args.hash_only, **options)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(not report["codes"])


if __name__ == "__main__":
    raise SystemExit(main())
