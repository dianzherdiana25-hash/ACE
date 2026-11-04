"""Fit a fixed solver to one request received over stdin."""

import json
import resource
import sys

from .baseline import fit
from .contract import MAX_FIT_BYTES, canonical_json


def main():
    result = fit(sys.stdin.buffer.read(MAX_FIT_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    sys.stdout.buffer.write(canonical_json({
        "program": json.loads(result.program.ast),
        "candidates": result.candidates,
        "steps": result.steps,
        "cpu_us": round((usage.ru_utime + usage.ru_stime) * 1_000_000),
        "rss_kib": usage.ru_maxrss,
    }))
