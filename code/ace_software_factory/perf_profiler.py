"""Profil wall-time produk pada beban unittest yang ditambatkan.

Setiap pengulangan membangun namespace baru dari isi sumber yang sama.
Pengukuran meliputi overhead start sandbox dan proses pengujian. Sampel
gagal dan warm-up dipisahkan dari statistik steady run.
"""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from ._contracts import ContractError, canonical, checked, decode, integer, read, schema, text
from .build_loop import _description, _read_tree, _runner
from .repo_scaffolder import materialize


def _nearest_rank(sorted_samples, fraction):
    position = (len(sorted_samples) * fraction + 99) // 100 - 1
    return sorted_samples[position]


def _statistics(times):
    samples = sorted(times)
    if not samples:
        return None
    n = len(samples)
    return {"min_ns": samples[0], "max_ns": samples[-1], "median_ns": (samples[(n-1)//2] + samples[n//2])//2,
            "p95_ns": _nearest_rank(samples, 95), "mean_ns": sum(samples)//n}


def profile(root, plan, expected, *, runner=_runner, clock=perf_counter_ns):
    checked(plan, expected)
    schema(plan, "ace.factory-perf-plan.v1", ("source_ref", "label", "files", "warmup", "repeats",
                                             "timeout_seconds", "expected_tests", "max_p95_ns"))
    label = text(plan["label"], "Label workload", 180)
    pointer = text(plan["source_ref"], "Rujukan beban", 200)
    make_ready = integer(plan["warmup"], "Pengulangan warm-up", 0, 3)
    repeats = integer(plan["repeats"], "Pengulangan terukur", 1, 30)
    maximum = integer(plan["timeout_seconds"], "Timeout per sampel", 1, 20)
    if maximum * (make_ready + repeats) > 120:
        raise ContractError("Beban melebihi anggaran waktu total.")
    expected_tests = integer(plan["expected_tests"], "Jumlah tes harapan", 1, 20_000)
    threshold = plan["max_p95_ns"]
    if threshold is not None:
        integer(threshold, "Ambang p95", 1, maximum * 10**9)
    files = _read_tree(root, plan["files"])
    samples = []
    timings = []
    for index in range(make_ready + repeats):
        with TemporaryDirectory(prefix="ace-factory-profile-") as folder:
            target = Path(folder) / "sample"
            materialize(target, files)
            initial = clock()
            audit = runner(target, maximum)
            wall = clock() - initial
        if wall < 0:
            raise ContractError("Clock pengukuran tidak monoton.")
        measured = index >= make_ready
        good = audit["status"] == "passed" and audit["tests"] == expected_tests and audit["skipped"] == 0
        samples.append({"sample": index + 1, "measured": measured, "elapsed_ns": wall, "test": audit, "usable": good})
        if not good:
            break
        if measured:
            timings.append(wall)
    metrics = _statistics(timings)
    status = "incomplete" if len(timings) != repeats else "measured"
    if status == "measured" and threshold is not None:
        status = "over_budget" if metrics["p95_ns"] > threshold else "within_budget"
    return {"schema": "ace.factory-perf-report.v1", "plan_sha256": expected, "label": label, "source_ref": pointer,
            "source": _description(files), "measurement": "sandboxed_unittest_process_wall_ns",
            "expected_measured_samples": repeats, "samples": samples, "statistics": metrics,
            "max_p95_ns": threshold, "status": status}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = profile(args.root, decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(result) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] in {"incomplete", "over_budget"})


if __name__ == "__main__":
    raise SystemExit(main())
