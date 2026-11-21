"""Turunkan pasangan DPO hanya dari skor kandidat berpasangan yang berkustodi.

Roster prompt dan rubrik dikunci sebelum penerimaan receipt. Pemenang
harus mengalahkan kandidat kedua dengan margin yang terdaftar, tanpa
seri dan dengan fitur berbeda. Prompt held-out serta receipt yang
belum berstatus verified tetap mendapat diagnosis di laporan.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import MAX_FEATURES, MAX_SAMPLES, reference
from .dataset_forge import MAX_BYTES
from .preference_trainer import Choice


MAX_RECEIPTS = 20_000


def _prompt_index(raw, refs):
    prompts = {}
    for row in entries(raw, MAX_SAMPLES):
        object_fields(row, ("id", "prompt_ref", "split"))
        key = string(row["id"], "ID prompt")
        pointer = reference(row["prompt_ref"], refs, "rujukan prompt")
        if row["split"] not in ("train", "held_out") or key in prompts:
            raise InputError("Prompt ganda atau partisi tidak dikenal.")
        prompts[key] = (pointer, row["split"])
    return prompts


def _verified(raw, prompts, refs, width, rubric):
    grouped = defaultdict(list)
    ignored = Counter()
    for row in entries(raw, MAX_RECEIPTS):
        object_fields(row, ("prompt_id", "receipt_ref", "rubric_sha256", "status", "score_bp", "choice"))
        key = string(row["prompt_id"], "ID prompt receipt")
        if key not in prompts or digest(row["rubric_sha256"]) != rubric:
            raise InputError("Receipt di luar roster atau rubrik berbeda.")
        pointer = reference(row["receipt_ref"], refs, "rujukan receipt")
        choice = Choice.read(row["choice"], width, refs)
        if row["status"] == "unverified":
            if row["score_bp"] is not None:
                raise InputError("Receipt belum terverifikasi harus memakai skor null.")
            ignored[key] += 1
            continue
        if row["status"] != "verified":
            raise InputError("Status receipt tidak dikenal.")
        score = integer(row["score_bp"], 0, 10_000)
        grouped[key].append((score, pointer, choice))
    return grouped, ignored


def _pair(keys, prompt, ranked, threshold, rubric):
    if len(ranked) < 2:
        return "insufficient_verified_receipts", None, None, None
    winner, runner_up = ranked[:2]
    margin = winner[0] - runner_up[0]
    if margin == 0:
        return "top_score_tie", margin, None, None
    if margin < threshold:
        return "insufficient_margin", margin, None, None
    if winner[2].features == runner_up[2].features:
        return "identical_features", margin, None, None
    evidence = {"winner_receipt_ref": winner[1], "runner_up_receipt_ref": runner_up[1], "rubric_sha256": rubric,
                "chosen_score_bp": winner[0], "rejected_score_bp": runner_up[0]}
    def payload(choice):
        return {"ref": choice.ref, "features": choice.features, "baseline_logp": choice.baseline_logp,
                "reference_logp": choice.reference_logp}
    pair = {"id": keys, "prompt_ref": prompt, "assessment_ref": "sha256:" + identity(evidence),
            "chosen": payload(winner[2]), "rejected": payload(runner_up[2])}
    return "mined", margin, pair, evidence


def mine(raw, receipts, expected):
    object_fields(raw, ("pairs_ref", "rubric_sha256", "feature_spec_ref", "baseline_sha256", "reference_sha256",
                        "receipt_snapshot_sha256", "width", "min_margin_bp", "prompts"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana preferensi berbeda dari anchor.")
    if identity(receipts) != digest(raw["receipt_snapshot_sha256"]):
        raise InputError("Receipt preferensi berbeda dari komitmen snapshot.")
    source = string(raw["pairs_ref"], "rujukan dataset")
    feature_ref = string(raw["feature_spec_ref"], "rujukan fitur")
    if source == feature_ref:
        raise InputError("Rujukan dataset dan fitur harus terpisah.")
    refs = {source, feature_ref}
    protocol = {"pairs_ref": source, "feature_spec_ref": feature_ref,
                "baseline_sha256": digest(raw["baseline_sha256"]), "reference_sha256": digest(raw["reference_sha256"])}
    rubric = digest(raw["rubric_sha256"])
    width = integer(raw["width"], 1, MAX_FEATURES)
    threshold = integer(raw["min_margin_bp"], 1, 10_000)
    prompts = _prompt_index(raw["prompts"], refs)
    object_fields(receipts, ("source_ref", "feature_spec_ref", "baseline_sha256", "reference_sha256", "evaluations"))
    receipt_ref = reference(receipts["source_ref"], refs, "rujukan snapshot receipt")
    if any(receipts[key] != protocol[key] for key in ("feature_spec_ref", "baseline_sha256", "reference_sha256")):
        raise InputError("Snapshot receipt memakai fitur atau artefak probabilitas berbeda.")
    grouped, ignored = _verified(receipts["evaluations"], prompts, refs, width, rubric)
    pairs = []
    report = []
    for key, (prompt, split) in sorted(prompts.items()):
        ranked = sorted(grouped.get(key, []), key=lambda item: (-item[0], item[2].ref))
        if split == "held_out":
            status, margin, pair, evidence = "held_out", None, None, None
        else:
            status, margin, pair, evidence = _pair(key, prompt, ranked, threshold, rubric)
        if pair is not None:
            pointer = pair["assessment_ref"]
            if pointer in refs:
                raise InputError("Rujukan bukti turunan bertabrakan dengan sumber.")
            refs.add(pointer)
            pairs.append(pair)
        report.append({"id": key, "prompt_ref": prompt, "status": status, "margin_bp": margin,
                       "verified_count": len(ranked), "unverified_count": ignored[key], "evidence": evidence})
    data = {**protocol, "pairs": pairs}
    return {"schema": "ace.forge-receipt-preferences.v1", "recipe_sha256": expected,
            "receipt_snapshot_ref": receipt_ref, "receipt_snapshot_sha256": raw["receipt_snapshot_sha256"],
            "pairs_sha256": identity(data),
            "dataset": data, "counts": dict(sorted(Counter(row["status"] for row in report).items())), "prompts": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--dataset", action="store_true", help="Ekspor skema masukan preference_trainer.")
    args = parser.parse_args(argv)
    try:
        product = mine(decode(read_bytes(args.plan, MAX_BYTES)), decode(read_bytes(args.receipts, MAX_BYTES)),
                       args.expect_sha256)
        if args.dataset and not product["dataset"]["pairs"]:
            raise InputError("Tidak ada pasangan terverifikasi untuk ekspor.")
        sys.stdout.write(canonical(product["dataset"] if args.dataset else product).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
