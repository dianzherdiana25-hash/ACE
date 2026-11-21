"""Kuantisasi bobot numerik dan audit perubahan rekonstruksi.

Format menyimpan kode bertanda 4/8 bit, skala simetris per tensor atau
per baris pertama, dan shape. Probe matvec membandingkan dua hasil
aritmetika pada vektor yang dicatat. Keluaran menahan rekomendasi saat
error melampaui kebijakan dan mencatat tensor yang belum memiliki probe.
"""
import argparse
from math import fsum, prod, ulp
from pathlib import Path
import re
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import real, reference, vector
from .dataset_forge import MAX_BYTES
from .merge_lab import MAX_ELEMENTS, MAX_VALUE, Snapshot


def _check_bits(bits):
    if type(bits) is not int or bits not in (4, 8):
        raise InputError("Pilih kuantisasi 4 atau 8 bit.")
    return (1 << (bits - 1)) - 1


def _groups(shape, mode):
    if mode not in ("tensor", "first_axis"):
        raise InputError("Mode skala tidak dikenal.")
    width = prod(shape[1:]) if mode == "first_axis" and shape else prod(shape)
    return width, prod(shape) // width


def _pack(values, bits):
    mask = (1 << bits) - 1
    if bits == 8:
        return bytes(value & mask for value in values)
    return bytes((values[i] & mask) | ((values[i + 1] & mask) << 4 if i + 1 < len(values) else 0)
                 for i in range(0, len(values), 2))


def _unpack(data, size, bits, peak):
    if bits == 4:
        if size % 2 and data[-1] & 240:
            raise InputError("Nibble padding harus nol.")
        raw = [item for byte in data for item in (byte & 15, byte >> 4)][:size]
    else:
        raw = list(data)
    values = [item if item <= peak else item - (1 << bits) for item in raw]
    if any(value < -peak for value in values):
        raise InputError("Kode negatif di luar simetri.")
    return values


def reconstruct(packed):
    object_fields(packed, ("name", "shape", "bits", "mode", "scales", "payload_hex"))
    bits = packed["bits"]
    peak = _check_bits(bits)
    string(packed["name"], "nama tensor")
    shape = tuple(integer(value, 1, MAX_ELEMENTS) for value in entries(packed["shape"], 6))
    size = prod(shape)
    if size > MAX_ELEMENTS:
        raise InputError("Tensor melampaui batas elemen.")
    width, groups = _groups(shape, packed["mode"])
    scales = packed["scales"]
    if not isinstance(scales, list) or len(scales) != groups:
        raise InputError("Jumlah skala tidak cocok dengan shape tensor.")
    scales = [real(value, ulp(0.0), MAX_VALUE) for value in scales]
    raw = packed["payload_hex"]
    byte_count = (size * bits + 7) // 8
    if not isinstance(raw, str) or len(raw) != 2 * byte_count or not re.fullmatch(r"[0-9a-f]+", raw):
        raise InputError("Payload heksadesimal tidak cocok dengan ukuran tensor.")
    codes = _unpack(bytes.fromhex(raw), size, bits, peak)
    restored = [scales[index // width] * code for index, code in enumerate(codes)]
    if any(abs(value) > MAX_VALUE * 1.000000000001 for value in restored):
        raise InputError("Rekonstruksi bobot melampaui batas numerik.")
    return restored


def _quantize(tensor, bits, mode):
    peak = _check_bits(bits)
    width, groups = _groups(tensor.shape, mode)
    codes, scales = [], []
    for group in range(groups):
        chunk = tensor.values[group * width:(group + 1) * width]
        largest = max(map(abs, chunk))
        scale = max(largest / peak, ulp(0.0)) if largest else 1.0
        scales.append(scale)
        codes.extend(max(-peak, min(peak, round(value / scale))) for value in chunk)
    return {"name": tensor.name, "shape": list(tensor.shape), "bits": bits, "mode": mode,
            "scales": scales, "payload_hex": _pack(codes, bits).hex()}


def _matvec(values, features, width):
    return [fsum(value * feature for value, feature in zip(values[i:i + width], features, strict=True))
            for i in range(0, len(values), width)]


def quantify(raw, snapshot, expected_recipe):
    object_fields(raw, ("recipe_ref", "source_sha256", "bits", "mode", "maximum_weight_error", "maximum_probe_error", "probes"))
    if identity(raw) != digest(expected_recipe):
        raise InputError("Resep kuantisasi berbeda dari anchor.")
    pointer = string(raw["recipe_ref"], "rujukan resep")
    refs, ids = {pointer}, set()
    layout = Snapshot.read(snapshot, refs)
    if layout.sha != digest(raw["source_sha256"]):
        raise InputError("Snapshot bobot berbeda dari resep.")
    bits, mode = raw["bits"], raw["mode"]
    _check_bits(bits)
    weight_limit = real(raw["maximum_weight_error"], 0, MAX_VALUE)
    probe_limit = real(raw["maximum_probe_error"], 0, MAX_VALUE * MAX_ELEMENTS)
    packed, observed = [], {}
    metrics = []
    for name, tensor in sorted(layout.tensors.items()):
        row = _quantize(tensor, bits, mode)
        restored = observed[name] = reconstruct(row)
        error = [abs(x - y) for x, y in zip(restored, tensor.values, strict=True)]
        packet_bytes = len(row["payload_hex"]) // 2
        metrics.append({"tensor": name, "elements": len(error), "payload_bytes": packet_bytes,
                        "max_absolute_error": max(error), "mean_squared_error": fsum(v * v for v in error) / len(error),
                        "within_error_limit": max(error) <= weight_limit})
        packed.append(row)
    measured = []
    tested = set()
    operations = 0
    for probe in entries(raw["probes"], 1000):
        object_fields(probe, ("id", "tensor", "input", "source_ref"))
        key = reference(probe["id"], ids, "ID probe")
        source = reference(probe["source_ref"], refs, "rujukan probe")
        name = string(probe["tensor"], "tensor probe")
        tensor = layout.tensors.get(name)
        if tensor is None or len(tensor.shape) != 2:
            raise InputError("Probe perlu menunjuk matriks yang tersedia.")
        width = tensor.shape[1]
        features = vector(probe["input"], width, "input probe", limit=MAX_VALUE)
        operations += len(tensor.values)
        if operations > 5_000_000:
            raise InputError("Total operasi probe melampaui batas.")
        expected = _matvec(tensor.values, features, width)
        reconstructed = _matvec(observed[name], features, width)
        error = max(abs(a - b) for a, b in zip(reconstructed, expected, strict=True))
        measured.append({"id": key, "tensor": name, "source_ref": source, "max_absolute_output_error": error,
                         "within_error_limit": error <= probe_limit})
        tested.add(name)
    failed = [row["tensor"] for row in metrics if not row["within_error_limit"]]
    failed_probes = sorted(row["id"] for row in measured if not row["within_error_limit"])
    unprobed = sorted(layout.tensors.keys() - tested)
    artifact = {"schema": "ace.quantized-tensors.v1", "architecture_ref": layout.architecture, "source_sha256": layout.sha,
                "tensors": packed}
    status = "hold" if failed or failed_probes else "partially_probed" if unprobed else "numeric_probes_within_limits"
    return {"schema": "ace.forge-quantization-report.v1", "recipe_ref": pointer, "recipe_sha256": expected_recipe,
            "source_ref": layout.ref, "status": status, "failed_tensors": failed, "failed_probes": failed_probes,
            "unprobed_tensors": unprobed, "tensor_errors": metrics, "probes": sorted(measured, key=lambda row: row["id"]),
            "payload_bytes_total": sum(row["payload_bytes"] for row in metrics),
            "artifact": artifact, "artifact_sha256": identity(artifact)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--expect-recipe-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = quantify(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.snapshot, MAX_BYTES)),
                          args.expect_recipe_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
