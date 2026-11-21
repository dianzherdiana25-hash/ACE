"""Kontrak raster dan spesifikasi lokal yang dipakai beberapa program persepsi."""
import json

from . import _raster
from .document_extractor import _zone
from .ocr_engine import _pairs


MAX_SPEC_BYTES = 1_000_000


def spec(data, schema, fields):
    if not isinstance(data, bytes) or len(data) > MAX_SPEC_BYTES:
        raise ValueError("Ukuran spesifikasi melampaui batas.")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(raw, dict) or set(raw) != {"schema", *fields} or raw["schema"] != schema:
        raise ValueError(f"Skema {schema} tidak sah.")
    return raw


def bounded_box(raw, image):
    box = _zone(raw)
    if box is None or box[2] > image.width or box[3] > image.height:
        raise ValueError("Wilayah di luar raster.")
    return box


def encode(width, height, pixels, maximum=255):
    if not 0 < width*height <= _raster.MAX_PIXELS or len(pixels) != width*height or not 1 <= maximum <= 255:
        raise ValueError("Dimensi atau kedalaman raster tidak sah.")
    if maximum != 255 and any(value > maximum for value in pixels):
        raise ValueError("Sampel raster di luar kedalaman.")
    return f"P5\n{width} {height}\n{maximum}\n".encode("ascii") + bytes(pixels)


def normalized(image):
    return bytes((value*255 + image.maximum//2)//image.maximum for value in image.pixels)
