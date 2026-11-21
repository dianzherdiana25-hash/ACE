"""Nilai bukti smoke artefak yang direkam dalam jendela paling lama 60 detik.

Protokol mengunci roster probe, SHA-256 artefak, dan satu aturan
jawaban deterministik per probe. Durasi mencakup dari awal batch
sampai hasil terakhir. Keluaran menunjuk receipt per probe tanpa
menyalin jawaban. Pengukuran berlangsung di luar pemeriksa ini.
"""
import argparse
from collections import Counter
from datetime import timedelta
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from .dataset_forge import MAX_BYTES


MAX_CASES = 128
MAX_SECONDS = 60


def _expected(raw):
    object_fields(raw, ("kind", "value"))
    kind = raw["kind"]
    if kind == "json_sha256":
        return kind, digest(raw["value"])
    if kind == "exact_text":
        return kind, string(raw["value"], "jawaban sasaran", max_chars=1000, preserve=True)
    if kind == "integer":
        return kind, integer(raw["value"], -10**12, 10**12)
    raise InputError("Aturan smoke tidak dikenal.")


def _probes(raw):
    by_id = {}
    refs = set()
    for row in entries(raw, MAX_CASES):
        object_fields(row, ("id", "test_ref", "expected"))
        key = string(row["id"], "ID smoke")
        pointer = string(row["test_ref"], "rujukan smoke")
        if key in by_id or pointer in refs:
            raise InputError("ID atau sumber probe ganda.")
        refs.add(pointer)
        by_id[key] = pointer, _expected(row["expected"])
    if not by_id:
        raise InputError("Roster smoke kosong.")
    return by_id


def _results(raw, artifact, started, probes):
    results = {}
    refs = set()
    for row in entries(raw, MAX_CASES):
        object_fields(row, ("id", "artifact_sha256", "receipt_ref", "finished_at", "outcome", "answer"))
        key = string(row["id"], "ID hasil")
        pointer = string(row["receipt_ref"], "rujukan hasil")
        finished = utc_stamp(row["finished_at"])
        outcome = row["outcome"]
        if (key not in probes or key in results or pointer in refs or finished < started
                or digest(row["artifact_sha256"]) != artifact or outcome not in ("answered", "failed")
                or outcome == "failed" and row["answer"] is not None):
            raise InputError("Receipt smoke tidak cocok dengan jadwal, artefak, atau roster.")
        refs.add(pointer)
        results[key] = (outcome, row["answer"], pointer, finished)
    return results


def _correct(rule, answer):
    kind, target = rule
    if kind == "json_sha256":
        return identity(answer) == target
    if kind == "exact_text":
        return isinstance(answer, str) and answer == target
    return type(answer) is int and answer == target


def assess(raw, observed, expected):
    object_fields(raw, ("protocol_ref", "artifact_sha256", "max_seconds", "probes"))
    if identity(raw) != digest(expected):
        raise InputError("Protokol smoke berbeda dari anchor.")
    protocol = string(raw["protocol_ref"], "rujukan protokol smoke")
    artifact = digest(raw["artifact_sha256"])
    seconds = integer(raw["max_seconds"], 1, MAX_SECONDS)
    probes = _probes(raw["probes"])
    object_fields(observed, ("batch_ref", "started_at", "observations"))
    batch = string(observed["batch_ref"], "rujukan batch")
    start = utc_stamp(observed["started_at"])
    results = _results(observed["observations"], artifact, start, probes)
    rows = []
    for key, (test_ref, rule) in sorted(probes.items()):
        found = results.get(key)
        if found is None:
            status, ref, ended = "missing", None, None
        else:
            outcome, answer, ref, ended = found
            if ended - start > timedelta(seconds=seconds):
                status = "timeout"
            elif outcome == "failed":
                status = "failed"
            else:
                status = "passed" if _correct(rule, answer) else "incorrect"
        rows.append({"id": key, "test_ref": test_ref, "receipt_ref": ref,
                     "finished_at": ended.isoformat() if ended else None, "status": status})
    counts = Counter(row["status"] for row in rows)
    end = max((item[3] for item in results.values()), default=None)
    window = end - start if end is not None else None
    elapsed = ((window.days * 86400 + window.seconds) * 10**6 + window.microseconds
               if window is not None else None)
    status = "passed" if counts["passed"] == len(rows) else (
        "timeout" if counts["timeout"] else "failed" if counts["failed"] or counts["incorrect"] else "incomplete")
    return {"schema": "ace.forge-model-smoke.v1", "protocol_ref": protocol, "protocol_sha256": expected,
            "observations_sha256": identity(observed), "artifact_sha256": artifact, "batch_ref": batch,
            "max_seconds": seconds, "elapsed_microseconds": elapsed, "status": status,
            "counts": {name: counts[name] for name in ("passed", "failed", "incorrect", "timeout", "missing")},
            "probes": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.receipts, MAX_BYTES)),
                        args.expect_protocol_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
