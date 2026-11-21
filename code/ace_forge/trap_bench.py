"""Audit jawaban jebakan berpasangan dengan kasus kontrol.

Setiap pasangan memiliki label yang dipatok, keluarga, dan kategori.
Report memisahkan kegagalan khusus trap, abstain yang tepat, dan
jawaban salah berkeyakinan tinggi. Receipt jawaban direkam sebelumnya
dan tidak memicu panggilan organ.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_PAIRS = 4000
ACTIONS = ("accept", "reject", "abstain")


def _case(raw, refs):
    object_fields(raw, ("prompt_ref", "expected", "gold_ref"))
    if raw["expected"] not in ACTIONS:
        raise InputError("Label gold tidak dikenal.")
    return {"prompt_ref": reference(raw["prompt_ref"], refs, "rujukan prompt"),
            "expected": raw["expected"], "gold_ref": reference(raw["gold_ref"], refs, "rujukan gold")}


def _verdict(raw, refs):
    if raw is None:
        return None
    object_fields(raw, ("action", "confidence_bp", "receipt_ref"))
    if raw["action"] not in ACTIONS:
        raise InputError("Tindakan untuk trap tidak dikenal.")
    confidence = raw["confidence_bp"]
    if confidence is not None:
        confidence = integer(confidence, 0, 10_000)
    return {"action": raw["action"], "confidence_bp": confidence,
            "receipt_ref": reference(raw["receipt_ref"], refs, "rujukan receipt")}


def _summarize(rows, minimum):
    counts = Counter(row["pair_outcome"] for row in rows)
    paired = len(rows) - counts["incomplete"]
    known = paired >= minimum
    return {"expected": len(rows), "paired": paired, "counts": dict(sorted(counts.items())),
            "trap_errors_with_high_confidence": sum(row["trap_high_confidence_error"] for row in rows),
            "trap_replies_with_confidence": sum(row["trap"]["answer"] is not None and
                row["trap"]["answer"]["confidence_bp"] is not None for row in rows),
            "appropriate_trap_abstentions": sum(row["trap"]["correct"] is True and
                row["trap"]["expected"] == "abstain" for row in rows),
            "trap_accuracy": _fraction(Fraction(counts["both_correct"] + counts["control_error_only"], paired)) if known else None,
            "control_accuracy": _fraction(Fraction(counts["both_correct"] + counts["trap_error_only"], paired)) if known else None,
            "trap_minus_control": _fraction(Fraction(counts["control_error_only"] - counts["trap_error_only"], paired))
            if known else None,
            "status": "paired" if known else "insufficient_evidence"}


def assess(protocol, responses, expected_protocol):
    object_fields(protocol, ("protocol_ref", "artifact_sha256", "high_confidence_bp", "minimum_pairs", "pairs"))
    if identity(protocol) != digest(expected_protocol):
        raise InputError("Roster trap berbeda dari anchor.")
    source = string(protocol["protocol_ref"], "rujukan protokol")
    artifact = digest(protocol["artifact_sha256"])
    high = integer(protocol["high_confidence_bp"], 1, 10_000)
    minimum = integer(protocol["minimum_pairs"], 1, MAX_PAIRS)
    refs, ids, pairs = {source}, set(), {}
    for row in entries(protocol["pairs"], MAX_PAIRS):
        object_fields(row, ("id", "category", "family_id", "trap", "control"))
        key = reference(row["id"], ids, "ID pasangan")
        pairs[key] = {"id": key, "category": string(row["category"], "kategori"),
                      "family_id": string(row["family_id"], "keluarga"),
                      "trap": _case(row["trap"], refs), "control": _case(row["control"], refs)}
    if not pairs:
        raise InputError("Roster trap kosong.")
    recorded = {}
    for row in entries(responses, MAX_PAIRS):
        object_fields(row, ("id", "artifact_sha256", "trap", "control"))
        key = string(row["id"], "ID jawaban")
        if key not in pairs or key in recorded or digest(row["artifact_sha256"]) != artifact:
            raise InputError("Receipt ganda, tidak terdaftar, atau artefaknya keliru.")
        recorded[key] = {arm: _verdict(row[arm], refs) for arm in ("trap", "control")}

    grouped, items = defaultdict(list), []
    for key, case in sorted(pairs.items()):
        replies = recorded.get(key, {"trap": None, "control": None})
        arm_cards = {}
        for arm in ("trap", "control"):
            answer = replies[arm]
            arm_cards[arm] = {**case[arm], "answer": answer,
                              "correct": answer["action"] == case[arm]["expected"] if answer else None}
        t, c = (arm_cards[arm]["correct"] for arm in ("trap", "control"))
        outcome = "incomplete" if t is None or c is None else {
            (True, True): "both_correct", (False, True): "trap_error_only",
            (True, False): "control_error_only", (False, False): "both_incorrect"}[t, c]
        confident = replies["trap"]["confidence_bp"] if replies["trap"] else None
        card = {**case, **arm_cards, "pair_outcome": outcome,
                "trap_high_confidence_error": t is False and confident is not None and confident >= high}
        grouped[case["category"]].append(card)
        items.append(card)
    return {"schema": "ace.forge-trap-bench.v1", "protocol_ref": source, "protocol_sha256": expected_protocol,
            "artifact_sha256": artifact, "responses_sha256": identity(responses), "high_confidence_bp": high,
            "report": _summarize(items, minimum), "categories": [
                {"category": key, **_summarize(rows, minimum)} for key, rows in sorted(grouped.items())
            ], "pairs": items}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("responses", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = assess(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.responses, MAX_BYTES)),
                         args.expect_protocol_sha256)
        sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
