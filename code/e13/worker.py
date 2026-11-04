"""Fit a registered solver to one request received over stdin."""

import json
import resource
import sys

from .baseline import fit, fit_fixed
from .beam import fit_beam
from .blind import fit_blind
from .contract import MAX_FIT_BYTES, canonical_json


def main(policy="catalog"):
    solver = {"fixed": fit_fixed, "catalog": fit, "blind": fit_blind, "beam": fit_beam}[policy]
    result = solver(sys.stdin.buffer.read(MAX_FIT_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    sys.stdout.buffer.write(canonical_json({
        "program": json.loads(result.program.ast),
        "candidates": result.candidates,
        "steps": result.steps,
        "status": result.status,
        "cpu_us": round((usage.ru_utime + usage.ru_stime) * 1_000_000),
        "rss_kib": usage.ru_maxrss,
    }))
