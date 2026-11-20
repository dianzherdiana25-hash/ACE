"""Telaah kandidat dengan gerbang kemampuan target dan regresi umum.

Semua kandidat memakai protokol, ukuran, dan baseline yang didaftarkan.
Hasil benchmark dan guard diterima dari berkas lokal. Ketiadaan hasil
menahan kandidat itu sendiri. Frontier menunjukkan tradeoff kualitas,
waktu, dan memori hanya dari kandidat yang melewati kedua gerbang.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import sys

from . import brain_bench, forgetting_guard
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_CANDIDATES = 160


def _setup(plan, expected):
    object_fields(plan, ("gate_ref", "baseline_sha256", "target_protocol_sha256", "general_protocol_sha256",
                         "rubric_ref", "target_floors", "candidates"))
    if identity(plan) != digest(expected):
        raise InputError("Rencana gerbang berbeda dari anchor.")
    gate = string(plan["gate_ref"], "rujukan gerbang")
    rubric = string(plan["rubric_ref"], "rujukan rubrik bersama")
    if rubric == gate:
        raise InputError("Rujukan rubrik dan gerbang harus berbeda.")
    first = digest(plan["baseline_sha256"])
    target_protocol = digest(plan["target_protocol_sha256"])
    general_protocol = digest(plan["general_protocol_sha256"])
    if target_protocol == general_protocol:
        raise InputError("Protokol target dan umum harus terpisah.")
    floors = {}
    for item in entries(plan["target_floors"], 100):
        object_fields(item, ("domain", "min_gain_bp"))
        domain = string(item["domain"], "domain target")
        if domain in floors:
            raise InputError("Domain target ganda.")
        floors[domain] = integer(item["min_gain_bp"], 1, 10_000)
    if not floors:
        raise InputError("Gerbang memerlukan ambang untuk domain target.")
    roster, seen = {}, {gate, rubric}
    for item in entries(plan["candidates"], MAX_CANDIDATES):
        object_fields(item, ("artifact_sha256", "registry_ref", "bench_sha256"))
        key = digest(item["artifact_sha256"])
        if key == first or key in roster:
            raise InputError("Kandidat ganda atau sama dengan baseline.")
        roster[key] = {"registry_ref": reference(item["registry_ref"], seen, "rujukan registry"),
                       "bench_sha256": digest(item["bench_sha256"])}
    if not roster:
        raise InputError("Rencana gerbang memerlukan kandidat.")
    return gate, rubric, first, target_protocol, general_protocol, floors, roster, seen


def _evaluation(key, packet, base, rubric, target_protocol, general_protocol, floors, candidate):
    bench = packet["benchmark"]
    guard_envelope = packet["general"]
    object_fields(guard_envelope, ("baseline_sha256", "candidate_sha256", "input"))
    if guard_envelope["baseline_sha256"] != base or guard_envelope["candidate_sha256"] != key:
        raise InputError("Guard merujuk pasangan artefak berbeda.")
    target = brain_bench.report(bench, candidate["bench_sha256"])
    if target["before_sha256"] != base or target["after_sha256"] != key:
        raise InputError("Bench merujuk pasangan artefak berbeda.")
    if target["rubric_ref"] != rubric or forgetting_guard.protocol_digest(bench["protocol"]) != target_protocol:
        raise InputError("Rubrik atau protokol target berbeda dari kebijakan bersama.")
    guard_input = guard_envelope["input"]
    general = forgetting_guard.screen(guard_input, general_protocol)
    target_rows = [row for domain in target["domains"] for row in domain["cases"]]
    general_rows = [row for domain in general["domains"] for row in domain["cases"]]
    for label in ("case_id", "case_ref"):
        if {item[label] for item in target_rows} & {item[label] for item in general_rows}:
            raise InputError("Kasus target bertumpang tindih dengan domain umum.")
    domains = {row["domain"]: row for row in target["domains"]}
    if domains.keys() != floors.keys():
        raise InputError("Domain hasil target berbeda dari kebijakan.")
    checks, blockers = [], []
    for name, floor in sorted(floors.items()):
        summary = domains[name]
        delta = summary["mean_delta"]
        passed = delta is not None and Fraction(**delta["score_bp"]) >= floor
        reason = "insufficient_target_pairs" if delta is None else "below_gain_floor" if not passed else None
        if reason:
            blockers.append({"domain": name, "reason": reason})
        checks.append({"domain": name, "compared": summary["compared"], "registered": summary["registered"],
                       "gain_bp": delta["score_bp"] if delta is not None else None, "floor_bp": floor, "passed": passed})
    for name in general["blocked_domains"]:
        blockers.append({"domain": name, "reason": "general_guard_hold"})
    return {"status": "hold" if blockers else "qualified", "blockers": blockers, "target_domains": checks,
            "general_status": general["status"], "mean_delta": target["aggregate"]["mean_delta"]}


def _frontier(rows):
    # Semua dimensi dihitung sebagai benefit, dengan biaya dibalik tandanya.
    scores = {}
    for row in rows:
        if row["status"] != "qualified":
            continue
        delta = row["mean_delta"]
        scores[row["artifact_sha256"]] = (Fraction(**delta["score_bp"]), -Fraction(**delta["elapsed_us"]),
                                           -Fraction(**delta["peak_bytes"]))
    frontier = []
    for key, values in sorted(scores.items()):
        dominated = any(other != values and all(x <= y for x, y in zip(values, other, strict=True))
                        for other in scores.values())
        if not dominated:
            frontier.append(key)
    return frontier


def evaluate(plan, submissions, expected_plan_sha256):
    gate, rubric, base, target_protocol, general_protocol, floors, roster, refs = _setup(plan, expected_plan_sha256)
    submitted = {}
    for item in entries(submissions, MAX_CANDIDATES):
        object_fields(item, ("artifact_sha256", "source_ref", "benchmark", "general"))
        key = digest(item["artifact_sha256"])
        if key in submitted or key not in roster:
            raise InputError("Bukti kandidat ganda atau tidak terdaftar.")
        submitted[key] = (reference(item["source_ref"], refs, "rujukan produk ukur"), item)
    reports = []
    for key, row in sorted(roster.items()):
        summary = {"artifact_sha256": key, **row}
        if key not in submitted:
            reports.append({**summary, "status": "missing_evidence", "source_ref": None})
            continue
        source, packet = submitted[key]
        base_row = {**summary, "source_ref": source, "packet_sha256": identity(packet)}
        try:
            value = _evaluation(key, packet, base, rubric, target_protocol, general_protocol, floors, row)
        except (ValueError, RecursionError) as exc:
            reports.append({**base_row, "status": "invalid_evidence", "detail": str(exc)})
            continue
        reports.append({**base_row, **value})
    return {"schema": "ace.forge-evaluation-gate.v1", "gate_ref": gate, "plan_sha256": expected_plan_sha256,
            "baseline_sha256": base, "rubric_ref": rubric, "candidate_results": reports,
            "frontier": _frontier(reports)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expect-plan-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = evaluate(decode(read_bytes(args.plan, MAX_BYTES)), decode(read_bytes(args.evidence, MAX_BYTES)),
                          args.expect_plan_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
