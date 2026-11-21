"""Optimasi DPO pada pasangan tercatat dengan representasi tetap.

Skor log pasangan berasal dari kebijakan beku dan referensi beku.
Koreksi linear pada fitur chosen/rejected menghasilkan selisih log
probabilitas karena normalisasi bersama dalam satu prompt saling
hapus. Optimizer mempelajari koreksi itu dengan loss DPO. Format ini
cocok untuk readout tetap atas fitur yang sudah diekstrak secara lokal.
"""
import argparse
from dataclasses import dataclass
from math import exp, fsum, log1p
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, identity, integer, object_fields, read_bytes, string
from ._numeric import MAX_FEATURES, operation_budget, real, reference, sample_rows, stable, steps_count, vector
from .dataset_forge import MAX_BYTES


@dataclass(frozen=True, slots=True)
class Recipe:
    ref: str
    feature_ref: str
    baseline: str
    reference_sha: str
    pairs: str
    width: int
    epochs: int
    beta: float
    l2: float
    step: float

    @classmethod
    def read(cls, raw):
        object_fields(raw, ("recipe_ref", "feature_spec_ref", "baseline_sha256", "reference_sha256", "pairs_sha256",
                            "width", "epochs", "beta", "l2", "learning_rate"))
        return cls(
            string(raw["recipe_ref"], "sumber resep"), string(raw["feature_spec_ref"], "sumber fitur"),
            digest(raw["baseline_sha256"]), digest(raw["reference_sha256"]), digest(raw["pairs_sha256"]),
            integer(raw["width"], 1, MAX_FEATURES), steps_count(raw["epochs"]),
            real(raw["beta"], 0.001, 8), real(raw["l2"], 0, 64), real(raw["learning_rate"], 1e-8, 1),
        )


@dataclass(frozen=True, slots=True)
class Choice:
    ref: str
    features: list
    baseline_logp: float
    reference_logp: float

    @classmethod
    def read(cls, raw, width, refs):
        object_fields(raw, ("ref", "features", "baseline_logp", "reference_logp"))
        return cls(reference(raw["ref"], refs, "rujukan kandidat"), vector(raw["features"], width, "fitur"),
                   real(raw["baseline_logp"], -10_000, 0), real(raw["reference_logp"], -10_000, 0))


@dataclass(frozen=True, slots=True)
class Pair:
    key: str
    prompt_ref: str
    assessment_ref: str
    chosen: Choice
    rejected: Choice
    margin: float
    delta: tuple

    @classmethod
    def read(cls, raw, width, keys, refs):
        object_fields(raw, ("id", "prompt_ref", "assessment_ref", "chosen", "rejected"))
        key = reference(raw["id"], keys, "ID pasangan")
        prompt = string(raw["prompt_ref"], "rujukan prompt")
        assessment = reference(raw["assessment_ref"], refs, "rujukan penilaian")
        chosen = Choice.read(raw["chosen"], width, refs)
        rejected = Choice.read(raw["rejected"], width, refs)
        if prompt in refs:
            raise InputError("Rujukan prompt harus terpisah dari bukti dan kandidat.")
        if chosen.features == rejected.features:
            raise InputError("Fitur pasangan sama, sehingga tidak dapat membedakan preferensi.")
        margin = (chosen.baseline_logp - rejected.baseline_logp) - (chosen.reference_logp - rejected.reference_logp)
        delta = tuple(x - y for x, y in zip(chosen.features, rejected.features, strict=True))
        return cls(key, prompt, assessment, chosen, rejected, margin, delta)


def _logistic_terms(z):
    """Hitung softplus(-z) dan sigmoid(-z) tanpa overflow."""
    if z >= 0:
        value = exp(-z)
        return log1p(value), value / (1 + value)
    value = exp(z)
    return -z + log1p(value), 1 / (1 + value)


def _metrics(weights, pairs, recipe):
    loss = []
    gradients = [0.0] * len(weights)
    for pair in pairs:
        margin = pair.margin + fsum(weight * value for weight, value in zip(weights, pair.delta, strict=True))
        step_loss, derivative = _logistic_terms(recipe.beta * margin)
        loss.append(step_loss)
        factor = -recipe.beta * derivative / len(pairs)
        for index, value in enumerate(pair.delta):
            gradients[index] += factor * value
    mean = fsum(loss) / len(pairs)
    objective = mean + 0.5 * recipe.l2 * fsum(weight**2 for weight in weights)
    final_gradient = [delta + recipe.l2 * weight for delta, weight in zip(gradients, weights, strict=True)]
    stable((mean, objective, *final_gradient))
    return {"mean_dpo_loss": mean, "objective": objective}, final_gradient


def fit(raw_recipe, source, expected_pairs_sha256):
    recipe = Recipe.read(raw_recipe)
    object_fields(source, ("pairs_ref", "feature_spec_ref", "baseline_sha256", "reference_sha256", "pairs"))
    observed = identity(source)
    if not digest(expected_pairs_sha256) == recipe.pairs == observed:
        raise InputError("Snapshot pasangan berbeda dari anchor.")
    if (digest(source["baseline_sha256"]), digest(source["reference_sha256"]), source["feature_spec_ref"]) != (
        recipe.baseline, recipe.reference_sha, recipe.feature_ref
    ):
        raise InputError("Pasangan memakai identitas artefak atau fitur berbeda.")
    refs, keys = {recipe.ref}, set()
    reference(recipe.feature_ref, refs, "rujukan fitur")
    source_ref = reference(source["pairs_ref"], refs, "rujukan pasangan")
    rows = sample_rows(source["pairs"])
    operation_budget(len(rows) * recipe.width * (recipe.epochs + 1))
    pairs = sorted((Pair.read(row, recipe.width, keys, refs) for row in rows), key=lambda item: item.key)
    if any(pair.prompt_ref in refs for pair in pairs):
        raise InputError("Rujukan prompt bertabrakan dengan bukti pasangan lain.")
    weights = [0.0] * recipe.width
    trace = []
    for epoch in range(recipe.epochs + 1):
        metrics, gradient = _metrics(weights, pairs, recipe)
        trace.append({"epoch": epoch, **metrics})
        if epoch < recipe.epochs:
            weights = [weight - recipe.step * update for weight, update in zip(weights, gradient, strict=True)]
            stable(weights)
    adapter = {"schema": "ace.dpo-linear-adapter.v1", "feature_spec_ref": recipe.feature_ref,
               "baseline_sha256": recipe.baseline, "reference_sha256": recipe.reference_sha, "weights": weights}
    return {
        "schema": "ace.dpo-fit-receipt.v1", "recipe_ref": recipe.ref, "recipe_sha256": identity(raw_recipe),
        "pairs_ref": source_ref, "pairs_sha256": observed, "adapter": adapter, "adapter_sha256": identity(adapter),
        "pairs": [{"id": pair.key, "prompt_ref": pair.prompt_ref, "assessment_ref": pair.assessment_ref,
                   "chosen_ref": pair.chosen.ref, "rejected_ref": pair.rejected.ref} for pair in pairs],
        "trace": trace,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--expect-pairs-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = fit(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.pairs, MAX_BYTES)),
                     args.expect_pairs_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
