"""Sandbox-only predictive histograms for a choice between two grammars."""

import resource
import sys
from collections import Counter
from itertools import product

from e13.contract import ContractError, array, canonical_json, read_json, require_fields

from .e14g_worker import WIRE_BYTES, _features, _label


def solve(raw):
    request = read_json(raw, WIRE_BYTES)
    require_fields(request, "family", "demos", "inputs")
    family = request["family"]
    if family not in ("S", "G"):
        raise ContractError("unknown family")
    demos = array(request["demos"], 32, 32)
    pool = array(request["inputs"], 8, 8)
    for example in demos:
        require_fields(example, "input", "output")
    outputs = {}
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    blank = () if family == "S" else None
    for length in (5, 6):
        features = [_features(family, demo["input"], length) for demo in demos]
        labeled = [(hits, _label(family, demo["output"], count))
                   for (count, hits), demo in zip(features, demos, strict=True)]
        scores = [(sum(hits.get(word, blank) == label for hits, label in labeled), word)
                  for word in product(symbols, repeat=length)]
        best = max(score for score, _ in scores)
        words = [word for score, word in scores if score == best]
        histograms = []
        for input_value in pool:
            _, hits = _features(family, input_value, length)
            dist = Counter(hits.get(word, blank) for word in words)
            histograms.append(sorted(dist.items(), key=lambda item: canonical_json(item[0])))
        outputs[str(length)] = {"fit_matches": best, "candidates": len(words),
                                "histograms": histograms, "fit_comparisons": len(scores) * len(demos),
                                "prediction_calls": len(pool) * len(words)}
    return outputs


def main():
    out = solve(sys.stdin.buffer.read(WIRE_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {"classes": out, "cpu_us": round(1_000_000 * (usage.ru_utime + usage.ru_stime)),
              "rss_kib": usage.ru_maxrss}
    sys.stdout.buffer.write(canonical_json(result))
