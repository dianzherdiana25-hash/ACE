"""Jalankan bench institut pada fixture tertutup dengan kunci terpisah, verifier, dan bukti."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import (ResearchError, anchor, canonical, decode, identifier, identity,
                         integer, items, obj, read, schema, source_bytes)
from .deep_report_writer import make_report
from .number_provenance import verify_numbers
from .research_qa import STATES, audit_report


def run_bench(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.bench-plan.v1",
           ("scope", "cases", "gold", "minimum_claim_match_bp", "minimum_rubric_bp"))
    if plan["scope"] != "closed_fixture":
        raise ResearchError("Bench hanya menerima lingkup fixture tertutup.")
    threshold = integer(plan["minimum_claim_match_bp"], "Ambang klaim", 8500, 10000)
    rubric_threshold = integer(plan["minimum_rubric_bp"], "Ambang rubrik", 1, 10000)
    gold_link = obj(plan["gold"], ("path", "sha256"))
    truth = decode(source_bytes(root, gold_link["path"], gold_link["sha256"], 250000))
    schema(truth, "ace.institute.bench-gold.v1", ("cases",))
    expected_cases = {}
    for row in items(truth["cases"], 30, 1):
        obj(row, ("id", "claim_status"))
        key = identifier(row["id"], "Kunci kasus")
        if key in expected_cases or not isinstance(row["claim_status"], dict) or not row["claim_status"]:
            raise ResearchError("Kunci kasus ganda atau tidak memiliki label.")
        for name, state in row["claim_status"].items():
            if state not in STATES:
                raise ResearchError("Status label bench tidak sah.")
            identifier(name, "Kunci klaim")
        expected_cases[key] = row["claim_status"]
    seen = set()
    results = []
    artifacts = {}
    matching = 0
    claims = 0
    provenance_pass = True
    numeric_support_pass = True
    for case in items(plan["cases"], 30, 1):
        obj(case, ("id", "report_plan", "reference_numbers"))
        key = identifier(case["id"], "Kasus")
        if key in seen or key not in expected_cases:
            raise ResearchError("Kasus ganda atau tidak memiliki kunci independen.")
        seen.add(key)
        case_plan = case["report_plan"]
        report = make_report(case_plan, identity(case_plan), root)
        qa = audit_report(report, min_score=rubric_threshold, min_sources=1, minimum_limits=1, root=root)
        raw_claims = {row["id"]: row["status"] for section in report["sections"] for row in section["claims"]}
        if raw_claims.keys() != expected_cases[key].keys():
            raise ResearchError("Kunci tidak mencakup identitas klaim dari kasus.")
        checks = [{"id": name, "actual": raw_claims[name], "expected": status,
                   "matches": status == raw_claims[name]} for name, status in sorted(expected_cases[key].items())]
        proved = sum(row["matches"] for row in checks)
        matching += proved
        claims += len(checks)
        texts = case["reference_numbers"]
        lineage = verify_numbers(texts, identity(texts), root, draft_bytes=report["markdown"].encode())
        provenance_pass &= lineage["status"] == "complete" and lineage["coverage_bp"] == 10000
        supported = report["summary"]["supported"]
        numeric_support_pass &= supported > 0 and len(qa["verified_claims"]) == supported
        files = {"report.json": canonical(report) + b"\n", "report.md": report["markdown"].encode(),
                 "qa.json": canonical(qa) + b"\n", "number_provenance.json": canonical(lineage) + b"\n"}
        for name, data in files.items():
            artifacts[f"{key}/{name}"] = data
        results.append({"id": key, "claim_cases": checks, "claim_matches": proved, "claim_count": len(checks),
                        "numeric_claims_verified": len(qa["verified_claims"]), "supported_claims": supported,
                        "reference_number_coverage_bp": lineage["coverage_bp"], "rubric_bp": qa["score_bp"],
                        "rubric_status": qa["status"]})
    if expected_cases.keys() != seen:
        raise ResearchError("Ada kasus dari kunci bench yang belum dijalankan.")
    rate = matching * 10000 // claims
    decision = rate >= threshold and numeric_support_pass and provenance_pass and all(
        row["rubric_status"] == "passes_rubric" for row in results)
    return artifacts, {"schema": "ace.institute.bench-result.v1", "plan_sha256": expected, "scope": plan["scope"],
                       "gold": gold_link, "cases": results, "claims_matched": matching, "claim_count": claims,
                       "claim_match_bp": rate, "all_supported_numbers_rechecked": numeric_support_pass,
                       "all_reference_numbers_sourced": provenance_pass,
                       "artifacts": {name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
                                     for name, data in sorted(artifacts.items())},
                       "status": "fixture_pass" if decision else "fixture_hold"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        evidence, report = run_bench(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for name, raw in evidence.items():
            path = args.output / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        (args.output / "run.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "fixture_pass")


if __name__ == "__main__":
    raise SystemExit(main())
