"""Agregasi QA lintas episode dari receipt tercatat dan laporkan celah per musim."""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, integer, obj, read, schema, text)


def _rubric(receipt):
    schema(receipt, "ace.media.studio-bench-report.v1", ("plan_sha256", "scope", "qa", "character",
                                                       "outputs", "backends", "thresholds", "status"))
    scope = receipt["scope"]
    if scope != "closed_fixture":
        raise ContractError("Cakupan receipt studio belum dikenali.")
    checklist = obj(receipt["qa"], ("passed", "total", "score_bp", "checks"))
    criteria = {}
    for row in entries(checklist["checks"], 80, 1):
        obj(row, ("criterion", "pass", "measured"))
        item = identifier(row["criterion"], "Kriteria")
        if item in criteria or type(row["pass"]) is not bool:
            raise ContractError("Kriteria ganda atau status tidak sah.")
        criteria[item] = row["pass"]
    passed = sum(criteria.values())
    if (passed, len(criteria), passed * 10000 // len(criteria)) != (checklist["passed"], checklist["total"], checklist["score_bp"]):
        raise ContractError("Rekap QA berbeda dari pemeriksaan per baris.")
    character = receipt["character"]
    if not isinstance(character, dict) or character.get("schema") != "ace.media.character-audit.v1":
        raise ContractError("Audit karakter tidak dikenali.")
    tracked = 0
    hits = 0
    known = set()
    for item in entries(character["variants"], 20, 1):
        obj(item, ("pose", "image_sha256", "checks"))
        name = identifier(item["pose"], "Pose")
        if name in known:
            raise ContractError("Pose audit karakter ganda.")
        known.add(name)
        digest(item["image_sha256"])
        features = set()
        for row in entries(item["checks"], 20, 1):
            obj(row, ("feature", "point", "pass"))
            label = identifier(row["feature"], "Landmark")
            if label in features or type(row["pass"]) is not bool:
                raise ContractError("Landmark ganda atau hasil tidak sah.")
            features.add(label)
            hits += row["pass"]
            tracked += 1
    if (hits, tracked, hits * 10000 // tracked) != (character["passed_landmarks"], character["landmarks"], character["score_bp"]):
        raise ContractError("Rekap landmark berbeda dari pemeriksaan per baris.")
    digest(receipt["plan_sha256"])
    return {"scope": scope, "qa_passed": passed, "qa_total": len(criteria), "character_passed": hits,
            "character_total": tracked, "failed_criteria": sorted(name for name, passed in criteria.items() if not passed)}


def summarize(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.season-report-plan.v1", ("roster",))
    groups = {}
    seen = set()
    receipt_hashes = set()
    for row in entries(plan["roster"], 160, 1):
        obj(row, ("series", "season", "episode", "source_ref", "receipt"))
        name = identifier(row["series"], "Seri")
        season = integer(row["season"], "Musim", 1, 999)
        episode = integer(row["episode"], "Episode", 1, 999)
        source = text(row["source_ref"], "Pointer episode")
        identity = (name, season, episode)
        if identity in seen:
            raise ContractError("Episode terdaftar ganda.")
        seen.add(identity)
        group = groups.setdefault((name, season), {"episodes": [], "missing": [], "counts": Counter(), "failed": Counter()})
        if row["receipt"] is None:
            group["missing"].append({"episode": episode, "source_ref": source, "reason": "receipt_not_listed"})
            continue
        link = obj(row["receipt"], ("path", "sha256"))
        anchor = digest(link["sha256"])
        if anchor in receipt_hashes:
            raise ContractError("Satu receipt tidak boleh dihitung untuk beberapa episode.")
        receipt_hashes.add(anchor)
        measurement = _rubric(decode(asset(root, link["path"], anchor, 500000)))
        group["episodes"].append({"episode": episode, "source_ref": source, "receipt_sha256": anchor, **measurement})
        group["counts"].update({name: measurement[name] for name in ("qa_passed", "qa_total", "character_passed", "character_total")})
        group["failed"].update(measurement["failed_criteria"])
    report = []
    previous = {}
    for (name, season), row in sorted(groups.items()):
        totals = row["counts"]
        qa = None if not totals["qa_total"] else totals["qa_passed"] * 10000 // totals["qa_total"]
        character = None if not totals["character_total"] else totals["character_passed"] * 10000 // totals["character_total"]
        prior = previous.get(name)
        gap = None if not prior else prior[0]
        report.append({"series": name, "season": season,
                       "episode_count": len(row["episodes"]) + len(row["missing"]), "measured_episodes": len(row["episodes"]),
                       "measurements": sorted(row["episodes"], key=lambda item: item["episode"]),
                       "evidence_gaps": sorted(row["missing"], key=lambda item: item["episode"]),
                       "qa": {"passed": totals["qa_passed"], "total": totals["qa_total"], "score_bp": qa,
                              "failed_criteria": dict(sorted(row["failed"].items()))},
                       "character": {"passed": totals["character_passed"], "total": totals["character_total"], "score_bp": character},
                       "previous_season": gap, "qa_change_bp": qa - prior[1] if qa is not None and prior and prior[1] is not None else None})
        previous[name] = (season, qa)
    return {"schema": "ace.media.season-report.v1", "plan_sha256": expected, "scope": "closed_fixture",
            "measurement_unit": "recorded_checks", "seasons": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = summarize(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
