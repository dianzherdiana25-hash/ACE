"""Pilih korpus ID–EN berpasangan tanpa mengubah record berkustodi.

Kapasitas dihitung per jenis tugas, partisi, dan keluarga. Sepasang
contoh selalu berasal dari keluarga yang sama. Rencana hanya dapat
diekspor jika setiap kuota dapat dipenuhi, agar kekurangan satu bahasa
tidak membuat campuran yang tampak seimbang dari jumlah keseluruhan.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS


LANGUAGES = ("id", "en")
SPLITS = ("train", "held_out")


@dataclass(frozen=True, slots=True)
class Example:
    row: dict
    id: str
    evidence: str
    family: str
    language: str

    @classmethod
    def read(cls, row):
        payload = row["payload"]
        return cls(row, row["example_id"], row["provenance"]["evidence_ref"], payload["family_id"], payload["language"])

    def pointer(self):
        return {"id": self.id, "evidence_ref": self.evidence}


def _policy(raw, expected):
    object_fields(raw, ("policy_ref", "seed", "quotas"))
    if identity(raw) != digest(expected):
        raise InputError("Kebijakan keseimbangan berbeda dari anchor.")
    ref = string(raw["policy_ref"], "rujukan kebijakan")
    seed = integer(raw["seed"], 0, 2**64 - 1)
    quotas = {}
    for row in entries(raw["quotas"], 500):
        object_fields(row, ("task_kind", "split", "pairs"))
        key = string(row["task_kind"], "jenis tugas"), string(row["split"], "partisi")
        if key in quotas or key[1] not in SPLITS:
            raise InputError("Partisi kuota tidak dikenal atau kuota ganda.")
        quotas[key] = integer(row["pairs"], 1, MAX_ROWS // 2)
    if not quotas or sum(quotas.values()) > MAX_ROWS // 2:
        raise InputError("Kuota pasangan kosong atau melampaui kapasitas korpus.")
    return ref, seed, quotas


def _rank(seed, group, family, marker):
    return identity([seed, *group, family, marker]), marker


def _pair(group, families, seed):
    """Sebar pasangan secara round robin agar keluarga kecil ikut terwakili."""
    per_family = {}
    unused = Counter()
    for name, table in families.items():
        left, right = (sorted(table[tag], key=lambda row: _rank(seed, group, name, row.id)) for tag in LANGUAGES)
        at_most = min(len(left), len(right))
        unused.update({"id": len(left) - at_most, "en": len(right) - at_most})
        if at_most:
            per_family[name] = list(zip(left[:at_most], right[:at_most], strict=True))
    ranked = sorted(per_family, key=lambda name: _rank(seed, group, name, "family"))
    # Urutkan record tersedia, bukan seluruh hasil kali ronde dan keluarga.
    candidates = [(index, order, rows) for order, name in enumerate(ranked)
                  for index, rows in enumerate(per_family[name])]
    candidates.sort(key=lambda item: item[:2])
    return [rows for _, _, rows in candidates], dict(sorted(unused.items()))


def balance(data, manifest, expected_head, raw_policy, expected_policy):
    ref, seed, quotas = _policy(raw_policy, expected_policy)
    if not verify(data, manifest, expected_head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    excluded = Counter()
    for line in data.splitlines():
        row = decode(line)
        payload = row["payload"]
        group = (payload["task_kind"], row["split"])
        if group not in quotas:
            excluded["outside_quota"] += 1
        elif payload["language"] not in LANGUAGES:
            excluded["language_outside_id_en"] += 1
        else:
            example = Example.read(row)
            grouped[group][example.family][example.language].append(example)
    diagnostics, selected = [], []
    for group, target in sorted(quotas.items()):
        pairs, unused = _pair(group, grouped[group], seed)
        take = pairs[:target]
        diagnostics.append({
            "task_kind": group[0], "split": group[1], "target_pairs": target,
            "available_pairs": len(pairs), "shortfall_pairs": max(0, target - len(pairs)),
            "unpaired_languages": {tag: unused.get(tag, 0) for tag in LANGUAGES},
            "pairs": [{"family_id": left.family, "id": left.pointer(), "en": right.pointer()} for left, right in take],
        })
        selected.extend(example for pair in take for example in pair)
    held = any(row["shortfall_pairs"] for row in diagnostics)
    result = [] if held else [row.row for row in sorted(selected, key=lambda example: example.id)]
    return result, {
        "schema": "ace.forge-bilingual-balance.v1", "policy_ref": ref, "policy_sha256": expected_policy,
        "dataset_head_sha256": expected_head, "status": "hold" if held else "balanced",
        "selected_examples": len(result), "excluded": dict(sorted(excluded.items())), "strata": diagnostics,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args(argv)
    try:
        selected, report = balance(
            read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)), args.expect_head,
            decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256,
        )
        if args.export:
            for row in selected:
                sys.stdout.write(canonical(row).decode("utf-8") + "\n")
        else:
            sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(report["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
