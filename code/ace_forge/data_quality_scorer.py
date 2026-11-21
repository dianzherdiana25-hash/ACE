"""Nilai mutu mekanis contoh tempa sebelum memilih campuran data.

Kustodi diperiksa sebelum penilaian. Skor menjelaskan panjang, label
bahasa, bentuk target, duplikasi prompt di jawaban, dan karakter
kontrol berdasarkan rubrik eksplisit. Laporan menyimpan skor dan
rujukan per contoh tanpa menyalin teks. Penilai fakta tetap diperlukan.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


CHECKS = ("prompt_length", "target_length", "language_label", "target_format", "non_echo", "control_chars")
FORMATS = ("text", "json", "json_object", "integer")


def _span(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise InputError("Rentang panjang harus [min, max].")
    minimum = integer(raw[0], 1, 16_000)
    return minimum, integer(raw[1], minimum, 16_000)


def _policy(raw):
    object_fields(raw, ("rubric_ref", "languages", "task_policies", "weights", "required_checks", "minimum_score_bp"))
    ref = string(raw["rubric_ref"], "rujukan rubrik")
    languages = set()
    for item in entries(raw["languages"], 50):
        reference(item, languages, "label bahasa")
    if not languages:
        raise InputError("Rubrik memerlukan label bahasa.")
    weight = raw["weights"]
    object_fields(weight, CHECKS)
    weights = {field: integer(weight[field], 0, 10_000) for field in CHECKS}
    if sum(weights.values()) != 10_000:
        raise InputError("Bobot mutu harus berjumlah 10.000 basis points.")
    required = set()
    for field in entries(raw["required_checks"], len(CHECKS)):
        if reference(field, required, "pemeriksaan wajib") not in CHECKS:
            raise InputError("Pemeriksaan wajib tidak dikenal.")
    by_kind = {}
    for row in entries(raw["task_policies"], 100):
        object_fields(row, ("task_kind", "prompt_chars", "target_chars", "target_format"))
        kind = string(row["task_kind"], "jenis tugas")
        fmt = string(row["target_format"], "format target")
        if kind in by_kind or fmt not in FORMATS:
            raise InputError("Jenis tugas ganda atau format target tidak dikenal.")
        by_kind[kind] = (_span(row["prompt_chars"]), _span(row["target_chars"]), fmt)
    if not by_kind:
        raise InputError("Rubrik memerlukan kebijakan jenis tugas.")
    return ref, languages, by_kind, weights, required, integer(raw["minimum_score_bp"], 1, 10_000)


def _formatted(text, fmt):
    if fmt == "text":
        return True
    try:
        node = decode(text.encode("utf-8"))
        canonical(node)
    except (ValueError, RecursionError):
        return False
    if fmt == "integer":
        return type(node) is int
    if fmt == "json_object":
        return isinstance(node, dict)
    return True


def _allow_chars(text):
    return all(char in "\n\r\t" or unicodedata.category(char) != "Cc" for char in text)


def _normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def score(data, manifest, expected_head, raw_policy):
    custody = verify(data, manifest, expected_head)
    if not custody["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    rubric_ref, languages, policies, weights, required, minimum = _policy(raw_policy)
    output, groups = [], defaultdict(list)
    for line in data.splitlines():
        row = decode(line)
        payload, evidence = row["payload"], row["provenance"]
        kind = payload["task_kind"]
        prompt, target = payload["prompt"], payload["target"]
        record = {"event_id": payload["event_id"], "example_id": row["example_id"], "task_kind": kind,
                  "split": row["split"], "evidence_ref": evidence["evidence_ref"], "prompt_chars": len(prompt),
                  "target_chars": len(target)}
        if kind not in policies:
            record.update(status="unscored", score_bp=None, checks=None, blockers=["task_policy_missing"])
        else:
            (p0, p1), (t0, t1), fmt = policies[kind]
            checks = {
                "prompt_length": p0 <= len(prompt) <= p1, "target_length": t0 <= len(target) <= t1,
                "language_label": payload["language"] in languages, "target_format": _formatted(target, fmt),
                "non_echo": _normalized(prompt) != _normalized(target), "control_chars": _allow_chars(prompt + target),
            }
            result = sum(weights[name] for name, passed in checks.items() if passed)
            blockers = [f"required:{key}" for key in sorted(required) if not checks[key]]
            if result < minimum:
                blockers.append("score_below_floor")
            record.update(status="hold" if blockers else "ready", checks=checks, score_bp=result, blockers=blockers)
        output.append(record)
        groups[kind].append(record)
    summary = []
    for kind, records in sorted(groups.items()):
        scores = [row["score_bp"] for row in records if row["score_bp"] is not None]
        counts = Counter(row["status"] for row in records)
        summary.append({"task_kind": kind, "pairs": len(records), "ready": counts["ready"], "hold": counts["hold"],
                        "unscored": counts["unscored"],
                        "mean_score_bp": _fraction(Fraction(sum(scores), len(scores))) if scores else None})
    return {"schema": "ace.forge-data-quality.v1", "dataset_head_sha256": expected_head, "rubric_ref": rubric_ref,
            "rubric_sha256": identity(raw_policy), "minimum_score_bp": minimum, "summary": summary,
            "records": sorted(output, key=lambda row: row["event_id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("rubric", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expect-head", required=True)
    args = parser.parse_args(argv)
    try:
        result = score(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                       args.expect_head, decode(read_bytes(args.rubric, MAX_BYTES)))
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
