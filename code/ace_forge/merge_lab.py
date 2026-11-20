"""Gabungkan snapshot bobot numerik dengan kompatibilitas eksplisit.

Interpolasi memakai bobot nonnegatif dengan jumlah satu. Mode delta
menambah perubahan relatif terhadap satu snapshot basis. Semua
snapshot harus terikat hash, memiliki arsitektur dan tensor yang sama,
serta melewati batas numerik. Diagnostik jarak bobot disimpan untuk
melacak perubahan artefak sebelum evaluasi kemampuan terpisah.
"""
import argparse
from dataclasses import dataclass
from math import fsum, prod
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import real, reference
from .dataset_forge import MAX_BYTES


MAX_SOURCES = 12
MAX_TENSORS = 256
MAX_ELEMENTS = 100_000
MAX_VALUE = 1_000_000


@dataclass(frozen=True, slots=True)
class Tensor:
    name: str
    shape: tuple
    values: tuple

    @classmethod
    def read(cls, raw, names):
        object_fields(raw, ("name", "shape", "values"))
        name = reference(raw["name"], names, "nama tensor")
        shape = tuple(integer(dimension, 1, MAX_ELEMENTS) for dimension in entries(raw["shape"], 6))
        size = prod(shape)
        if not 1 <= size <= MAX_ELEMENTS:
            raise InputError("Dimensi tensor melebihi batas elemen.")
        numbers = entries(raw["values"], MAX_ELEMENTS)
        if len(numbers) != size:
            raise InputError("Jumlah angka tidak sesuai bentuk tensor.")
        return cls(name, shape, tuple(real(value, -MAX_VALUE, MAX_VALUE) for value in numbers))

    def export(self):
        return {"name": self.name, "shape": list(self.shape), "values": list(self.values)}


@dataclass(frozen=True, slots=True)
class Snapshot:
    sha: str
    ref: str
    architecture: str
    tensors: dict

    @classmethod
    def read(cls, row, refs):
        object_fields(row, ("weights_ref", "architecture_ref", "tensors"))
        ref = reference(row["weights_ref"], refs, "rujukan snapshot")
        architecture = string(row["architecture_ref"], "rujukan arsitektur")
        names = set()
        tensors = {tensor.name: tensor for tensor in
                   (Tensor.read(raw, names) for raw in entries(row["tensors"], MAX_TENSORS))}
        if not tensors or sum(len(tensor.values) for tensor in tensors.values()) > MAX_ELEMENTS:
            raise InputError("Jumlah tensor kosong atau melampaui batas total elemen.")
        return cls(identity(row), ref, architecture, tensors)

    def layout(self):
        return {name: value.shape for name, value in self.tensors.items()}


def _coefficients(raw, loaded, base):
    expected = {}
    for row in entries(raw, MAX_SOURCES):
        object_fields(row, ("snapshot_sha256", "weight_bp"))
        checksum = digest(row["snapshot_sha256"])
        if checksum in expected or checksum == base or checksum not in loaded:
            raise InputError("Kontributor ganda, hilang, atau memakai basis.")
        expected[checksum] = integer(row["weight_bp"], -10_000 if base else 1, 10_000)
    if len(expected) < 2 or 0 in expected.values():
        raise InputError("Merge membutuhkan dua kontributor berbobot nonnol.")
    if base is None and sum(expected.values()) != 10_000:
        raise InputError("Bobot interpolasi harus tepat 10.000 basis points.")
    if base and sum(abs(weight) for weight in expected.values()) > 20_000:
        raise InputError("Total besar koefisien delta melampaui batas.")
    if set(loaded) != set(expected) | ({base} if base else set()):
        raise InputError("Daftar snapshot berbeda dari resep.")
    return expected


def merge(recipe, snapshots, expected_recipe_sha256):
    object_fields(recipe, ("recipe_ref", "output_ref", "mode", "base_sha256", "weights"))
    if identity(recipe) != digest(expected_recipe_sha256):
        raise InputError("Resep merge berbeda dari anchor.")
    recipe_ref = string(recipe["recipe_ref"], "rujukan resep")
    output_ref = string(recipe["output_ref"], "rujukan bobot keluaran")
    if recipe_ref == output_ref:
        raise InputError("Rujukan resep dan keluaran harus berbeda.")
    mode = recipe["mode"]
    if mode not in ("interpolate", "task_delta") or (mode == "task_delta") != (recipe["base_sha256"] is not None):
        raise InputError("Mode merge atau basis tidak sah.")
    base = digest(recipe["base_sha256"]) if mode == "task_delta" else None
    refs = {recipe_ref, output_ref}
    loaded = {}
    for row in entries(snapshots, MAX_SOURCES):
        item = Snapshot.read(row, refs)
        loaded[item.sha] = item
    by_sha = _coefficients(recipe["weights"], loaded, base)
    contributors = [(loaded[key], by_sha[key] / 10_000) for key in sorted(by_sha)]
    shape_source = loaded[base] if base else contributors[0][0]
    layout = shape_source.layout()
    if any(item.architecture != shape_source.architecture or item.layout() != layout for item in loaded.values()):
        raise InputError("Arsitektur, nama, atau bentuk tensor tidak kompatibel.")

    # task_delta = (1 - jumlah koefisien) * basis + Σ koefisien * kontributor.
    terms = contributors + ([(loaded[base], 1 - fsum(weight for _, weight in contributors))] if base else [])
    merged = []
    for name, shape in sorted(layout.items()):
        result = [fsum(value * weight for value, (_, weight) in zip(values, terms, strict=True))
                  for values in zip(*(item.tensors[name].values for item, _ in terms), strict=True)]
        if any(abs(value) > MAX_VALUE for value in result):
            raise InputError("Bobot gabungan keluar dari batas numerik.")
        merged.append(Tensor(name, shape, tuple(result)))
    output = {"weights_ref": output_ref, "architecture_ref": shape_source.architecture,
              "tensors": [tensor.export() for tensor in merged]}
    distances = []
    size = sum(len(tensor.values) for tensor in merged)
    for key, snapshot in sorted(loaded.items()):
        square_error = fsum((actual - prior)**2
                            for tensor in merged
                            for actual, prior in zip(tensor.values, snapshot.tensors[tensor.name].values, strict=True))
        distances.append({"snapshot_sha256": key, "snapshot_ref": snapshot.ref, "weight_bp": by_sha.get(key),
                          "mean_squared_distance": square_error / size})
    return {"schema": "ace.weight-merge-receipt.v1", "recipe_ref": recipe_ref, "recipe_sha256": expected_recipe_sha256,
            "mode": mode, "tensor_count": len(merged), "elements": size, "base_sha256": base,
            "snapshots": distances, "output_sha256": identity(output), "output": output}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("snapshots", type=Path)
    parser.add_argument("--expect-recipe-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = merge(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.snapshots, MAX_BYTES)),
                       args.expect_recipe_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
