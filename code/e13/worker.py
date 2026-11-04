"""Fit a registered solver to one request received over stdin."""

import json
import resource
import sys

from .baseline import fit, fit_fixed
from .beam import fit_beam
from .blind import fit_blind
from .contract import MAX_FIT_BYTES, canonical_json
from .extension import POLICIES, REPLAY_BYTES, fit_extension, replay_extension


def main(policy="catalog"):
    limit = REPLAY_BYTES if policy == "replay" else MAX_FIT_BYTES
    raw = sys.stdin.buffer.read(limit + 1)
    if policy in POLICIES:
        result = fit_extension(raw, policy)
    elif policy == "replay":
        result = replay_extension(raw)
    else:
        solver = {"fixed": fit_fixed, "catalog": fit, "blind": fit_blind, "beam": fit_beam}[policy]
        result = solver(raw)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    response = {
        "program": json.loads(result.program.ast),
        "candidates": result.candidates,
        "steps": result.steps,
        "status": result.status,
        "cpu_us": round((usage.ru_utime + usage.ru_stime) * 1_000_000),
        "rss_kib": usage.ru_maxrss,
    }
    if result.trace is not None:
        response["trace"] = result.trace
    sys.stdout.buffer.write(canonical_json(response))
