"""Tinjau beberapa batch serapan yang sudah ditambatkan sebelum registry draf ditinjau."""
import argparse
from pathlib import Path
import sys

from ._artifact import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, identity, integer, obj, read, schema, text
from .skill_board import build
from .skill_registry import revise

MAX_ARTIFACT = 12_000_000
MAX_TOTAL = 50_000_000

def campaign(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.web.skill-campaign-plan.v1", ("source_ref", "roadmap", "registry", "batches", "target"))
    owner_ref = text(plan["source_ref"], "Rujukan tinjauan")
    byte_count = 0
    digests = {}
    def load(ref):
        nonlocal byte_count
        obj(ref, ("path", "sha256"))
        path = text(ref["path"], "Rujukan artefak", 300)
        fingerprint = digest(ref["sha256"])
        if path in digests:
            raise ContractError("Kampanye serapan merujuk path artefak yang sama dua kali.")
        raw = read_relative(root, path, min(MAX_ARTIFACT, MAX_TOTAL - byte_count), fingerprint)
        byte_count += len(raw)
        digests[path] = fingerprint
        return decode(raw)

    initial = load(plan["registry"])
    roadmap = load(plan["roadmap"])
    revision = initial
    def score(state):
        spec = {"schema": "ace.web.skill-board-plan.v1", "source_ref": owner_ref,
                "roadmap_sha256": identity(roadmap), "registry_sha256": identity(state), "staleness_sha256": None}
        return build(spec, identity(spec), roadmap, state)
    early = score(initial)
    names = {row["id"] for group in early["clusters"] for row in group["skills"]}
    target = integer(plan["target"], "Target akuisisi", 1, len(names))
    audit = []
    ids = set()
    for raw in entries(plan["batches"], 20):
        entry = obj(raw, ("id", "policy", "batch"))
        label = identifier(entry["id"], "Batch")
        if label in ids:
            raise ContractError("ID batch kampanye ganda.")
        ids.add(label)
        policy, batch = load(entry["policy"]), load(entry["batch"])
        revised, receipt = revise(revision, policy, identity(policy), batch)
        if any(row["skill"] not in names for row in receipt["transitions"]):
            raise ContractError("Revisi memuat kandidat di luar roadmap kampanye.")
        revision = revised
        audit.append({"id": label, "policy": entry["policy"], "batch": entry["batch"],
                      "revision_before": receipt["previous_sha256"], "revision_after": receipt["registry_sha256"],
                      "verification": identity(receipt), "transitions": receipt["transitions"]})
    final = score(revision)
    coverage = final["counts"]
    return {"schema": "ace.web.skill-campaign-review.v1", "plan_sha256": expected,
            "scope": "readonly_registry_review", "roadmap": plan["roadmap"], "registry": plan["registry"],
            "input_hashes": dict(sorted(digests.items())), "board_sha256": identity(final), "target": target,
            "acquired_before": early["counts"]["ACQUIRED"], "acquired_after": coverage["ACQUIRED"],
            "remaining_to_target": max(0, target - coverage["ACQUIRED"]), "status_counts": coverage,
            "batches": audit, "registry_candidate": revision, "planned_skills": final["skills_requested"],
            "read_bytes": byte_count}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = campaign(decode(read(args.plan)), args.expect_sha256, args.root)
        sys.stdout.buffer.write(canonical(result) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
