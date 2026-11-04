"""Compare closed structural, enumerative and beam policies on public banks."""

import argparse
import json
import platform
import random
import subprocess
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from .bank import bank_digest, development_bank
from .pilot import source_digest, summarize, verify_replay
from .transfer_bank import transfer_bank
from .transfer_pilot import _record


def run_pilot():
    started, cpu = perf_counter_ns(), process_time_ns()
    banks = {"development": development_bank()[0], "diagnostic": transfer_bank()}
    bank_cpu = (process_time_ns() - cpu) // 1_000
    order_seed = 131505
    schedule = [(name, episode, policy) for name, episodes in banks.items()
                for episode in episodes for policy in ("structured", "enumerative", "beam")]
    random.Random(order_seed).shuffle(schedule)
    rows = [{"bank": name, **_record(episode, policy)} for name, episode, policy in schedule]
    return {
        "mode": "development", "purpose": "public comparison of closed fit policies",
        "order_seed": order_seed, "source_sha256": source_digest(),
        "bank_sha256": {name: bank_digest(episodes) for name, episodes in banks.items()},
        "bank_cpu_us": bank_cpu, "evaluator_total_cpu_us": (process_time_ns() - cpu) // 1_000,
        "wall_us": (perf_counter_ns() - started) // 1_000,
        "machine": {"kernel": platform.release(), "platform": platform.machine(),
                    "evaluator_python": platform.python_version(),
                    "worker_python": subprocess.check_output(["/usr/bin/python3", "-V"], text=True).strip()},
        "summary": {name: summarize(row for row in rows if row["bank"] == name) for name in banks},
        "runs": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    report = run_pilot()
    if args.verify:
        verify_replay(json.loads(args.verify.read_text()), report)
    print(json.dumps(report, separators=(",", ":")))
    return int(any(row["fit_status"] == "worker_error"
                   or any(s["failures"] for s in row["scores"].values())
                   for row in report["runs"]))


if __name__ == "__main__":
    raise SystemExit(main())
