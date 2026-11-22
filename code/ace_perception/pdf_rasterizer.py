"""Render halaman PDF lokal menjadi raster PGM yang dapat dipakai OCR.

Poppler bekerja di direktori sementara atas byte masukan yang
dibatasi. Batas panjang sisi, rentang halaman, dan waktu mencegah
ekspor tak terkendali. Verifikasi raster serta roster halaman
dilakukan sebelum direktori hasil baru dibuat.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from . import _raster
from .audio_pipeline import _canonical, _integer


MAX_PDF_BYTES = 12_000_000
MAX_PAGES = 12
MAX_EDGE = 1500
MAX_TOTAL_RASTER_BYTES = 28_000_000
EXPORT_NAME = re.compile(r"page-[0-9]{6,7}\.pgm")
PAGE_NAME = re.compile(r"pg-([0-9]{1,8})\.pgm")


def _products(stage, first, last, edge):
    found = {}
    total = 0
    for path in stage.iterdir():
        match = PAGE_NAME.fullmatch(path.name)
        if match is None:
            if path.name != "source.pdf":
                raise ValueError("Renderer menghasilkan nama artefak tak terduga.")
            continue
        page = int(match[1])
        if page < first or page > last or page in found or not path.is_file() or path.is_symlink():
            raise ValueError("Renderer menghasilkan halaman di luar roster.")
        payload = _raster.read(path, min(_raster.MAX_BYTES, MAX_TOTAL_RASTER_BYTES-total))
        total += len(payload)
        image = _raster.decode(payload)
        if max(image.width, image.height) > edge:
            raise ValueError("Sisi raster melampaui batas renderer.")
        found[page] = (payload, image.width, image.height)
    if set(found) != set(range(first, last+1)):
        raise ValueError("Renderer tidak mengembalikan seluruh halaman yang diminta.")
    return [(page, *found[page]) for page in range(first, last+1)]


def rasterize(pdf_data, *, first_page=1, last_page=1, long_edge=1200, timeout_seconds=25):
    if not isinstance(pdf_data, bytes) or len(pdf_data) > MAX_PDF_BYTES or not pdf_data.startswith(b"%PDF-"):
        raise ValueError("Masukan perlu berkas PDF lokal dalam batas byte.")
    low = _integer(first_page, 1, 1_000_000, "Halaman awal")
    high = _integer(last_page, low, min(low+MAX_PAGES-1, 1_000_000), "Halaman akhir")
    edge = _integer(long_edge, 32, MAX_EDGE, "Sisi raster")
    timeout = _integer(timeout_seconds, 1, 120, "Timeout renderer")
    if (high-low+1)*(edge*edge+64) > MAX_TOTAL_RASTER_BYTES:
        raise ValueError("Anggaran raster seluruh halaman melampaui batas.")
    renderer = shutil.which("pdftoppm")
    if renderer is None:
        raise ValueError("pdftoppm lokal diperlukan untuk merender PDF.")
    with TemporaryDirectory(prefix="ace-perception-pdf-") as folder:
        stage = Path(folder)
        (stage/"source.pdf").write_bytes(pdf_data)
        args = [renderer, "-f", str(low), "-l", str(high), "-gray", "-scale-to", str(edge), "source.pdf", "pg"]
        try:
            process = subprocess.run(args, cwd=stage, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Renderer PDF melewati batas waktu.") from exc
        if process.returncode != 0:
            raise ValueError(f"Renderer PDF berhenti dengan status {process.returncode}.")
        observed = _products(stage, low, high, edge)
    artifacts = {}
    records = []
    for page, payload, width, height in observed:
        name = f"page-{page:06d}.pgm"
        artifacts[name] = payload
        records.append({"page": page, "file": name, "sha256": sha256(payload).hexdigest(),
                        "width": width, "height": height, "bytes": len(payload)})
    return artifacts, {"schema": "ace.perception-pdf-raster.v1", "source_sha256": sha256(pdf_data).hexdigest(),
                        "first_page": low, "last_page": high, "long_edge": edge, "renderer": "pdftoppm",
                        "pages": records}


def write_artifacts(directory, products, manifest):
    if any(not EXPORT_NAME.fullmatch(name) for name in products):
        raise ValueError("Nama ekspor halaman tidak sah.")
    directory.mkdir(mode=0o700)
    for name, payload in products.items():
        with (directory/name).open("xb") as stream:
            stream.write(payload)
    with (directory/"manifest.json").open("xb") as stream:
        stream.write(_canonical(manifest) + b"\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int)
    parser.add_argument("--long-edge", type=int, default=1200)
    parser.add_argument("--timeout-seconds", type=int, default=25)
    args = parser.parse_args(argv)
    try:
        data = _raster.read(args.pdf, MAX_PDF_BYTES)
        pages, report = rasterize(data, first_page=args.first_page,
                                  last_page=args.last_page if args.last_page is not None else args.first_page,
                                  long_edge=args.long_edge, timeout_seconds=args.timeout_seconds)
        write_artifacts(args.output_dir, pages, report)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
