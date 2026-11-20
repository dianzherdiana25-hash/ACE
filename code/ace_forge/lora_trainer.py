"""Fit adaptor LoRA lapisan dense dari aktivasi yang sudah direkam.

Lapisan asal direpresentasikan oleh keluaran beku per contoh. Resep
mengoptimasi delta (alpha / rank) × B × A dengan MSE, sehingga berkas
yang keluar bisa dipetakan ke satu lapisan bernama tanpa memerlukan
inferensi organ. Dataset masuk ditambatkan dengan SHA-256. Keluaran
menyertakan loss train dan provenance untuk pemeriksaan held-out terpisah.
"""
import argparse
from dataclasses import dataclass
from math import fsum, sqrt
from pathlib import Path
from random import Random
import sys

from ._forge_io import InputError, canonical, decode, digest, identity, integer, object_fields, read_bytes, string
from ._numeric import MAX_FEATURES, operation_budget, real, reference, sample_rows, stable, steps_count, vector
from .dataset_forge import MAX_BYTES


@dataclass(frozen=True, slots=True)
class Recipe:
    ref: str
    layer: str
    dataset: str
    base: str
    epoch_count: int
    learning_rate: float
    gradient_cap: float
    input_width: int
    output_width: int
    rank: int
    alpha: float
    seed: int

    @classmethod
    def read(cls, raw):
        object_fields(raw, ("recipe_ref", "layer", "base_sha256", "dataset_sha256", "input_width", "output_width",
                            "rank", "alpha", "learning_rate", "gradient_cap", "epochs", "seed"))
        width = integer(raw["input_width"], 1, MAX_FEATURES)
        outputs = integer(raw["output_width"], 1, MAX_FEATURES)
        return cls(string(raw["recipe_ref"], "rujukan resep"), string(raw["layer"], "lapisan dense"),
                   digest(raw["dataset_sha256"]), digest(raw["base_sha256"]), steps_count(raw["epochs"]),
                   real(raw["learning_rate"], 1e-8, 1), real(raw["gradient_cap"], 1e-7, 10_000),
                   width, outputs, integer(raw["rank"], 1, min(width, outputs, 16)),
                   real(raw["alpha"], 1e-5, 64), integer(raw["seed"], 0, 2**64 - 1))


@dataclass(frozen=True, slots=True)
class Sample:
    key: str
    anchor: str
    features: list
    frozen: list
    target: list

    @classmethod
    def read(cls, row, recipe, keys, refs):
        object_fields(row, ("id", "source_ref", "input", "base_output", "target"))
        return cls(reference(row["id"], keys, "ID contoh"), reference(row["source_ref"], refs, "rujukan contoh"),
                   vector(row["input"], recipe.input_width, "aktivasi"),
                   vector(row["base_output"], recipe.output_width, "keluaran lapisan beku"),
                   vector(row["target"], recipe.output_width, "target"))


def _dot(left, right):
    return fsum(x * y for x, y in zip(left, right, strict=True))


def _zero(rows, columns):
    return [[0.0] * columns for _ in range(rows)]


def _loss_gradient(a, b, samples, scale, *, gradient):
    width = len(a[0])
    grad_a = _zero(len(a), width)
    grad_b = _zero(len(b), len(a))
    normalization = len(samples) * len(b)
    losses = []
    for item in samples:
        hidden = [_dot(row, item.features) for row in a]
        error = [base + scale * _dot(row, hidden) - target
                 for base, row, target in zip(item.frozen, b, item.target, strict=True)]
        losses.append(fsum(value * value for value in error))
        if gradient:
            factor = 2 * scale / normalization
            for output, delta in enumerate(error):
                for index, component in enumerate(hidden):
                    grad_b[output][index] += factor * delta * component
            for index in range(len(a)):
                projected_error = fsum(row[index] * delta for row, delta in zip(b, error, strict=True))
                for coordinate, feature in enumerate(item.features):
                    grad_a[index][coordinate] += factor * projected_error * feature
    loss = fsum(losses) / normalization
    stable((loss,))
    return loss, grad_a, grad_b


def _update(a, b, grad_a, grad_b, recipe):
    norm = sqrt(fsum(value**2 for matrix in (grad_a, grad_b) for row in matrix for value in row))
    stable((norm,))
    clipped = norm > recipe.gradient_cap
    step_size = recipe.learning_rate * (recipe.gradient_cap / norm if clipped else 1)
    for matrix, gradients in ((a, grad_a), (b, grad_b)):
        for row, grad in zip(matrix, gradients, strict=True):
            for index, value in enumerate(grad):
                row[index] -= value * step_size
            stable(row)
    return clipped


def fit(recipe_raw, source, expected_source_sha256):
    recipe = Recipe.read(recipe_raw)
    object_fields(source, ("dataset_ref", "base_sha256", "layer", "samples"))
    observed = identity(source)
    if not digest(expected_source_sha256) == recipe.dataset == observed:
        raise InputError("Snapshot aktivasi berbeda dari anchor.")
    if digest(source["base_sha256"]) != recipe.base or source["layer"] != recipe.layer:
        raise InputError("Aktivasi berasal dari artefak atau lapisan berbeda.")
    dataset_ref = string(source["dataset_ref"], "rujukan aktivasi")
    if dataset_ref == recipe.ref:
        raise InputError("Rujukan data dan resep harus terpisah.")
    raw_samples = sample_rows(source["samples"])
    operation_budget(len(raw_samples) * recipe.rank * (recipe.input_width + recipe.output_width) * (recipe.epoch_count + 1))
    keys, refs = set(), {dataset_ref, recipe.ref}
    samples = sorted((Sample.read(row, recipe, keys, refs) for row in raw_samples), key=lambda row: row.key)
    rng = Random(recipe.seed)
    unit = 1 / sqrt(recipe.input_width)
    a = [[(2 * rng.random() - 1) * unit for _ in range(recipe.input_width)] for _ in range(recipe.rank)]
    b = _zero(recipe.output_width, recipe.rank)
    scale = recipe.alpha / recipe.rank
    history = []
    clipped = 0
    for epoch in range(recipe.epoch_count):
        loss, grad_a, grad_b = _loss_gradient(a, b, samples, scale, gradient=True)
        history.append({"epoch": epoch, "train_mse": loss})
        clipped += _update(a, b, grad_a, grad_b, recipe)
    loss, _, _ = _loss_gradient(a, b, samples, scale, gradient=False)
    history.append({"epoch": recipe.epoch_count, "train_mse": loss})
    adapter = {
        "schema": "ace.lora-dense-adapter.v1", "base_sha256": recipe.base,
        "layer": recipe.layer, "rank": recipe.rank, "alpha": recipe.alpha, "a": a, "b": b,
    }
    return {
        "schema": "ace.lora-train-receipt.v1", "recipe_ref": recipe.ref, "recipe_sha256": identity(recipe_raw),
        "dataset_ref": dataset_ref, "dataset_sha256": observed,
        "sample_refs": [{"id": row.key, "source_ref": row.anchor} for row in samples],
        "adapter": adapter, "adapter_sha256": identity(adapter),
        "gradient_clip_count": clipped, "trace": history,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("activations", type=Path)
    parser.add_argument("--expect-dataset-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = fit(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.activations, MAX_BYTES)),
                     args.expect_dataset_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
