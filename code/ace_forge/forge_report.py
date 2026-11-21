"""Bangun laporan per run dari ledger, checkpoint, dan bench bertambat.

State lifecycle dibaca ulang dari receipt. Checkpoint divalidasi
terhadap rencana run. Bench yang disertakan harus menunjuk adaptor
yang muncul dalam checkpoint loop tersebut. Gap dilaporkan sebagai
ketiadaan evidence dan tampil baik di JSON maupun Markdown.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import sys

from . import brain_bench, experiment_tracker, train_runner
from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES
from .model_card_writer import _text


def _training(raw, experiment):
    if raw is None:
        return None
    object_fields(raw, ("plan", "plan_sha256", "checkpoints", "head_sha256", "source_ref"))
    plan = raw["plan"]
    object_fields(plan, ("plan_ref", "jobs"))
    checksum = digest(raw["plan_sha256"])
    if checksum != identity(plan) or checksum != experiment["recipe_sha256"]:
        raise InputError("Rencana checkpoint berbeda dari resep yang direkam.")
    pointer = string(raw["source_ref"], "rujukan checkpoint")
    seen = set()
    jobs = [train_runner.Job.read(row, seen) for row in entries(plan["jobs"], train_runner.MAX_JOBS)]
    if not jobs:
        raise InputError("Rencana checkpoint tanpa pekerjaan.")
    checkpoints = raw["checkpoints"]
    current = train_runner._replay(checkpoints, jobs, checksum, raw["head_sha256"])
    known = {row["sha256"] for row in checkpoints}
    if {row["checkpoint_sha256"] for row in experiment["checkpoints"]} - known:
        raise InputError("Ledger menunjuk checkpoint yang tidak ada di prefix terverifikasi.")
    return {
        "source_ref": pointer, "plan_ref": string(plan["plan_ref"], "rujukan rencana"), "head_sha256": current,
        "expected_jobs": len(jobs), "completed_jobs": len(checkpoints),
        "artifacts": [{"job_id": row["id"], "checkpoint_sha256": row["sha256"],
                       "adapter_sha256": row["receipt"]["adapter_sha256"]} for row in checkpoints],
    }


def _benchmark(raw, train):
    if raw is None:
        return None
    object_fields(raw, ("data", "bench_sha256", "source_ref"))
    if not train or not train["artifacts"]:
        raise InputError("Bench perlu artefak dari checkpoint run.")
    product = brain_bench.report(raw["data"], raw["bench_sha256"])
    if product["after_sha256"] not in {row["adapter_sha256"] for row in train["artifacts"]}:
        raise InputError("Bench menunjuk artefak di luar checkpoint run.")
    pointer = string(raw["source_ref"], "rujukan bench")
    tasks = [{"domain": row["domain"], "compared": row["compared"], "registered": row["registered"],
              "score_delta_bp": row["mean_delta"]["score_bp"] if row["mean_delta"] is not None else None,
              "status": row["status"]} for row in product["domains"]]
    return {"source_ref": pointer, "bench_sha256": product["bench_sha256"], "rubric_ref": product["rubric_ref"],
            "artifact_sha256": product["after_sha256"], "domains": tasks}


def report(raw, expected):
    object_fields(raw, ("report_ref", "experiment_id", "ledger", "training", "benchmark"))
    if identity(raw) != digest(expected):
        raise InputError("Sumber laporan run berbeda dari anchor.")
    pointer = string(raw["report_ref"], "rujukan report")
    key = string(raw["experiment_id"], "ID run")
    ledger = raw["ledger"]
    object_fields(ledger, ("data", "ledger_sha256"))
    audit = experiment_tracker.audit(ledger["data"], ledger["ledger_sha256"])
    state = next((row for row in audit["experiments"] if row["experiment_id"] == key), None)
    if state is None:
        raise InputError("Run tidak terdaftar di ledger.")
    train = _training(raw["training"], state)
    bench = _benchmark(raw["benchmark"], train)
    gaps = []
    if train is None:
        gaps.append("training_evidence_missing")
    elif train["completed_jobs"] != train["expected_jobs"]:
        gaps.append("incomplete_checkpoint_prefix")
    if bench is None:
        gaps.append("held_out_bench_missing")
    elif any(item["status"] != "complete" for item in bench["domains"]):
        gaps.append("incomplete_bench")
    if state["status"] != "completed":
        gaps.append("lifecycle_not_completed")
    return {"schema": "ace.forge-run-report.v1", "report_ref": pointer, "source_sha256": expected,
            "ledger_ref": audit["ledger_ref"], "ledger_sha256": audit["ledger_sha256"], "experiment": state,
            "training": train, "benchmark": bench, "evidence_gaps": gaps}


def markdown(raw):
    state = raw["experiment"]
    lines = [f"# Laporan tempa {_text(state['experiment_id'])}", "",
             f"- Status receipt `{state['status']}`. Sumber {_text(raw['ledger_ref'])}.",
             f"- Unit terpakai {state['spent_units']} dari {state['budget_units']}. Selisih {state['margin_units']}.",
             f"- Percobaan {state['attempts']}. Rencana {_text(state['plan_ref'])}."]
    if state["terminal_ref"] is not None:
        lines.append(f"- Receipt terminal {_text(state['terminal_ref'])}.")
    lines += ["", "## Checkpoint", ""]
    train = raw["training"]
    if train is None:
        lines.append("TIDAK TAHU. Prefix checkpoint belum disertakan.")
    else:
        lines.append(f"{train['completed_jobs']}/{train['expected_jobs']} pekerjaan. "
                     f"Head `{train['head_sha256']}`. Sumber {_text(train['source_ref'])}.")
    lines += ["", "## Bench held-out", ""]
    bench = raw["benchmark"]
    if bench is None:
        lines.append("TIDAK TAHU. Bench belum disertakan.")
    else:
        lines += [f"Rubrik {_text(bench['rubric_ref'])}. Sumber {_text(bench['source_ref'])}.", "",
                  "| Domain | Pasangan | Delta (bp) |", "|---|---:|---:|"]
        for row in bench["domains"]:
            delta = row["score_delta_bp"]
            cells = (_text(row["domain"]), f"{row['compared']}/{row['registered']}",
                     str(Fraction(**delta)) if delta is not None else "TIDAK TAHU")
            lines.append("| " + " | ".join(cells) + " |")
    if raw["evidence_gaps"]:
        lines += ["", "## Kelengkapan bukti", ""]
        lines.extend(f"- `{gap}`" for gap in raw["evidence_gaps"])
    lines += ["", f"Rujukan laporan {_text(raw['report_ref'])}. SHA-256 masukan `{raw['source_sha256']}`."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    try:
        product = report(decode(read_bytes(args.input, MAX_BYTES)), args.expect_input_sha256)
        sys.stdout.write(markdown(product) if args.format == "markdown" else canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
