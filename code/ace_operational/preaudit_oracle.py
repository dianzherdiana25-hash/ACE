"""Independent oracle for the pre-audit validator — TEST SUPPORT ONLY.

Written directly from the written specification in
docs/research/PREAUDIT_VALIDATOR_V1_DESIGN_FREEZE.md, in the most direct way
possible, sharing no code with preaudit_validator (plain hashlib/json, no
strict parser, no pointer machinery beyond literal key walks). The validator
is never imported here, and this module is never imported by the validator.

Purpose: fixture expectations in the self-test ladder come from this oracle,
so a validator bug cannot quietly become its own expected output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def oracle_c1_states(source_root, manifest):
    """path -> 'SESUAI' | 'TIDAK SESUAI' for well-formed manifest entries."""
    states = {}
    root = Path(source_root)
    for entry in manifest["artifacts"]:
        path = root / entry["path"]
        if not path.is_file():
            states[entry["path"]] = "TIDAK SESUAI"
            continue
        data = path.read_bytes()
        ok = len(data) == entry["size_bytes"] and \
            hashlib.sha256(data).hexdigest() == entry["sha256"]
        states[entry["path"]] = "SESUAI" if ok else "TIDAK SESUAI"
    return states


def oracle_expected_verdict(prereg_text, results_text):
    """Per-record expected verdict ('pass'/'fail') per the preregistered rule
    written as {metric, gte|gt|lte|lt|eq}. Independent plain implementation."""
    prereg = json.loads(prereg_text)
    rule = prereg["protocol"]["pass_rule"]
    metric = rule["metric"]
    if "gte" in rule:
        op, threshold = ">=", rule["gte"]
    elif "gt" in rule:
        op, threshold = ">", rule["gt"]
    elif "lte" in rule:
        op, threshold = "<=", rule["lte"]
    elif "lt" in rule:
        op, threshold = "<", rule["lt"]
    else:
        op, threshold = "==", rule["eq"]
    expected = []
    for line in results_text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        value = record["result"]["metrics"][metric]
        holds = {">=": value >= threshold, ">": value > threshold,
                 "<=": value <= threshold, "<": value < threshold,
                 "==": value == threshold}[op]
        expected.append("pass" if holds else "fail")
    return expected


def oracle_sum_pairs(records, key):
    """Sum [num, den] pairs under item[key], which may be a dict of pairs."""
    totals = {}
    for item in records:
        target = item[key]
        if isinstance(target, dict):
            for name, pair in target.items():
                acc = totals.setdefault(name, [0, 0])
                acc[0] += pair[0]
                acc[1] += pair[1]
        else:
            acc = totals.setdefault("__single__", [0, 0])
            acc[0] += target[0]
            acc[1] += target[1]
    return totals


def oracle_rate(pair):
    """Exact rate as a (numerator, denominator) reduced fraction via gcd."""
    import math
    num, den = pair
    g = math.gcd(num, den)
    return (num // g, den // g)


# ---------------------------------------------------------------------------
# v2 extension (design freeze PREAUDIT_VALIDATOR_V2_DESIGN_FREEZE.md).
# Written from the freeze text only; shares no code with the validator.
# ---------------------------------------------------------------------------

def oracle_spec_digest(manifest, validator_source_bytes):
    """Recompute the validation_spec_digest independently: SHA-256 over the
    canonical JSON closing evidence closure + ruleset + validator build +
    configuration. Canonical = sorted keys, Decimals tagged by exact string.
    """
    import re
    from decimal import Decimal

    version_match = re.search(r'VALIDATOR_VERSION = "([^"]+)"',
                              validator_source_bytes.decode("utf-8"))
    closure = sorted(
        [[a["path"], a["sha256"], a["size_bytes"]] for a in manifest["artifacts"]],
        key=lambda triple: triple[0])
    closure = [{"path": p, "sha256": h, "size_bytes": n} for p, h, n in closure]
    spec = {
        "evidence_closure": closure,
        "ruleset": {
            "count_assertions": manifest.get("count_assertions"),
            "verdict_check": manifest.get("verdict_check"),
        },
        "validator_build": {
            "version": version_match.group(1),
            "source_sha256": hashlib.sha256(validator_source_bytes).hexdigest(),
        },
        "configuration": {
            "report_schema": "ace.preaudit_report.v2",
            "manifest_schema": "ace.preaudit_manifest.v1",
            "reason_code_registry_version": "1",
            "stage_model_version": "1",
        },
    }

    def default(obj):
        if isinstance(obj, Decimal):
            return {"__decimal__": str(obj)}
        raise TypeError(repr(obj))

    blob = json.dumps(spec, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=default).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
