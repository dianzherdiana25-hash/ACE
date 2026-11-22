"""Susun dossier telaah dari keputusan yang dapat dihitung ulang.

Registry, bench kualitas, guard regresi, smoke, dan ledger persetujuan
masing-masing diperiksa ulang. Seluruh laporan harus menunjuk artefak
yang sama. Lampiran kosong atau gate yang tertahan dicatat eksplisit,
sehingga dossier selalu bisa ditelaah tanpa mengaktifkan artefak.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import sys

from . import activation_ladder, brain_bench, forgetting_guard, model_registry_v2, smoke_test_model
from ._forge_io import InputError, canonical, decode, digest, identity, integer, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES
from .model_card_writer import _text


def _registry(raw, baseline, candidate):
    if raw is None:
        return None, None
    object_fields(raw, ("source_ref", "records", "head"))
    source = string(raw["source_ref"], "rujukan registry")
    product = model_registry_v2.inspect(raw["records"], raw["head"])
    known = {row["sha256"]: row for row in product["artifacts"]}
    artifact = known.get(candidate)
    lineage = set()
    pending = list(artifact["parent_sha256"]) if artifact else []
    while pending:
        parent = pending.pop()
        if parent not in lineage:
            lineage.add(parent)
            pending.extend(known[parent]["parent_sha256"])
    return {"source_ref": source, "head": product["head_sha256"], "artifact": artifact,
            "baseline_in_lineage": baseline in lineage}, artifact


def _bench(raw, baseline, candidate):
    if raw is None:
        return None
    object_fields(raw, ("data", "bench_sha256", "source_ref"))
    source = string(raw["source_ref"], "rujukan bench")
    product = brain_bench.report(raw["data"], raw["bench_sha256"])
    if (product["before_sha256"], product["after_sha256"]) != (baseline, candidate):
        raise InputError("Bench memakai baseline atau kandidat berbeda.")
    return {"source_ref": source, "evidence_sha256": identity(raw["data"]), "report": product}


def _guard(raw, baseline, candidate):
    if raw is None:
        return None
    object_fields(raw, ("data", "protocol_sha256", "source_ref", "baseline_sha256", "candidate_sha256"))
    source = string(raw["source_ref"], "rujukan guard")
    if (digest(raw["baseline_sha256"]), digest(raw["candidate_sha256"])) != (baseline, candidate):
        raise InputError("Guard memakai baseline atau kandidat berbeda.")
    product = forgetting_guard.screen(raw["data"], raw["protocol_sha256"])
    return {"source_ref": source, "evidence_sha256": identity(raw), "report": product}


def _smoke(raw, candidate):
    if raw is None:
        return None
    object_fields(raw, ("protocol", "receipts", "protocol_sha256"))
    product = smoke_test_model.assess(raw["protocol"], raw["receipts"], raw["protocol_sha256"])
    if product["artifact_sha256"] != candidate:
        raise InputError("Smoke menunjuk kandidat berbeda.")
    return {"source_ref": product["batch_ref"], "evidence_sha256": identity(raw), "report": product}


def _approval(raw, candidate, components):
    if raw is None:
        return None
    object_fields(raw, ("policy", "history", "policy_sha256", "history_sha256"))
    product = activation_ladder.evaluate(raw["policy"], raw["history"], raw["policy_sha256"], raw["history_sha256"])
    if product["artifact_sha256"] != candidate:
        raise InputError("Persetujuan menunjuk kandidat berbeda.")
    stages = {row["stage"]: row["evidence_sha256"] for row in product["stages"]}
    for key, value in components.items():
        if key not in stages or value is not None and stages[key] != value["evidence_sha256"]:
            raise InputError(f"Persetujuan tidak terikat ke bukti dossier untuk {key}.")
    return product


def assemble(raw, expected):
    object_fields(raw, ("dossier_ref", "baseline_sha256", "candidate_sha256", "target_domain",
                        "minimum_gain_bp", "registry", "held_out", "regression", "smoke", "approval"))
    if identity(raw) != digest(expected):
        raise InputError("Dossier berbeda dari anchor.")
    source = string(raw["dossier_ref"], "rujukan dossier")
    baseline, candidate = digest(raw["baseline_sha256"]), digest(raw["candidate_sha256"])
    if baseline == candidate:
        raise InputError("Baseline dan kandidat harus berbeda.")
    domain = string(raw["target_domain"], "domain sasaran")
    minimum = integer(raw["minimum_gain_bp"], 1, 10_000)
    registry, item = _registry(raw["registry"], baseline, candidate)
    components = {"held_out": _bench(raw["held_out"], baseline, candidate),
                  "regression": _guard(raw["regression"], baseline, candidate), "smoke": _smoke(raw["smoke"], candidate)}
    approval = _approval(raw["approval"], candidate, components)
    missing = [key for key, value in {"registry": registry, **components, "approval": approval}.items() if value is None]
    blockers = []
    if registry is not None:
        if item is None:
            blockers.append("artifact_not_registered")
        elif item["status"] != "qualified" or item["domain"] != domain:
            blockers.append("registry_not_qualified_for_domain")
        else:
            if not registry["baseline_in_lineage"]:
                blockers.append("registry_baseline_not_in_lineage")
            review = item["review"]
            bench_item = components["held_out"]
            if bench_item is not None and review["held_out_sha256"] != bench_item["evidence_sha256"]:
                blockers.append("registry_review_bench_mismatch")
            guard = components["regression"]
            if guard is not None and review["regression_ref"] != guard["source_ref"]:
                blockers.append("registry_review_regression_mismatch")
    bench = components["held_out"]
    if bench is not None:
        target = next((row for row in bench["report"]["domains"] if row["domain"] == domain), None)
        if target is None or target["status"] != "complete":
            blockers.append("target_coverage_missing")
        elif Fraction(**target["mean_delta"]["score_bp"]) < minimum:
            blockers.append("target_gain_below_threshold")
    for name, passing in (("regression", "pass"), ("smoke", "passed")):
        if components[name] is not None and components[name]["report"]["status"] != passing:
            blockers.append(f"{name}_gate_held")
    if approval is not None and approval["status"] != "approvals_complete":
        blockers.append("approval_" + approval["status"])
    return {"schema": "ace.forge-model-dossier.v1", "dossier_ref": source, "input_sha256": expected,
            "baseline_sha256": baseline, "candidate_sha256": candidate,
            "target_domain": domain, "minimum_gain_bp": minimum, "registry": registry, **components, "approval": approval,
            "missing": missing, "blockers": blockers, "status": "hold" if missing or blockers else "ready_for_review"}


def markdown(report):
    lines = ["# Dossier tempa", "", f"Status `{report['status']}`. Sumber {_text(report['dossier_ref'])}.",
             f"Artefak `{report['candidate_sha256']}` dibanding baseline `{report['baseline_sha256']}`.",
             f"Domain sasaran {_text(report['target_domain'])}. Ambang {report['minimum_gain_bp']} bp.", ""]
    for field in ("registry", "held_out", "regression", "smoke", "approval"):
        value = report[field]
        pointer = (value.get("source_ref") or value["ledger_ref"]) if value is not None else None
        if pointer is None:
            lines.append(f"- {field}. TIDAK TAHU. Sumber belum disertakan.")
        else:
            lines.append(f"- {field}. Sumber {_text(pointer)}.")
    lines.extend(f"- Tertahan `{reason}`." for reason in report["blockers"])
    lines += ["", f"SHA-256 masukan `{report['input_sha256']}`."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        product = assemble(decode(read_bytes(args.dossier, MAX_BYTES)), args.expect_sha256)
        sys.stdout.write(markdown(product) if args.format == "markdown" else canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(product["status"] != "ready_for_review")


if __name__ == "__main__":
    raise SystemExit(main())
