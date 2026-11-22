"""Hubungkan OCR, ekstraksi tabel, dan receipt audio pada satu bench fixture bertambat."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _perception_io, _vision, audio_pipeline, document_extractor, perception_bench, table_extractor
from .audio_pipeline import _canonical, _sha
from .perceptual_memory import _digest

SCHEMA = "ace.perception-fixture-suite.v1"

def _item(root, ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Rujukan input fixture perlu path dan SHA-256.")
    return _perception_io.read_relative(root, ref["path"], 2_000_000, _digest(ref["sha256"]))

def _extract_table(report):
    if not report["cells"]:
        return []
    rows = [[None] * report["columns"] for _ in range(report["rows"])]
    for cell in report["cells"]:
        value = (dict(perception_bench.UNRESOLVED_CELL) if cell["status"] == "partial" else cell["text"])
        rows[cell["row"] - 1][cell["column"] - 1] = value
    return rows

def run(root, plan, expected):
    settings = _vision.spec(plan, SCHEMA, ("protocol", "inputs"))
    if _sha(settings) != _digest(expected):
        raise ValueError("Rencana fixture berbeda dari anchor.")
    protocol = _item(root, settings["protocol"])
    protocol_sha256 = sha256(protocol).hexdigest()
    _, roster, _ = perception_bench._plan(protocol, protocol_sha256)
    if not isinstance(settings["inputs"], dict) or settings["inputs"].keys() != roster.keys():
        raise ValueError("Daftar fixture harus sama dengan roster gold.")
    receipts, trace = [], []
    for key, (kind, sha, _, _) in sorted(roster.items()):
        source = settings["inputs"][key]
        fields = {"media", "transcript"} if kind == "asr" else {"media", "font", "layout"}
        if not isinstance(source, dict) or source.keys() != fields:
            raise ValueError("Kolom fixture tidak cocok dengan kelas media.")
        raw = _item(root, source["media"])
        if sha256(raw).hexdigest() != sha:
            raise ValueError(f"Byte media fixture tidak cocok dengan protokol: {key}")
        if kind == "asr":
            evidence = audio_pipeline.align(raw, _item(root, source["transcript"]))
            value = " ".join(row["text"] for row in evidence["segments"] if row["status"] == "read")
            scope = "provided_transcript_against_fixture_reference"
        else:
            font = _item(root, source["font"])
            layout = _item(root, source["layout"])
            if kind == "document":
                evidence = document_extractor.extract(raw, font, layout)
                value = {row["id"]: row["value"] for row in evidence["claims"] if row["status"] == "extracted"}
            else:
                evidence = table_extractor.extract(raw, font, layout)
                value = _extract_table(evidence)
            scope = "pixel_input_extraction"
        artifact = _sha(evidence)
        trace.append({"case": key, "inputs": source, "artifact_sha256": artifact, "scope": scope,
                      "status": evidence["status"]})
        receipts.append({"id": key, "media_sha256": sha, "receipt_ref": f"fixture/extraction/{key}/{artifact}", "result": value})
    results = _canonical({"schema": "ace.perception-held-out-results.v1", "results": receipts})
    return {"schema": "ace.perception-fixture-evidence.v1", "scope": "synthetic_closed_fixture",
            "plan_sha256": expected, "derivations": trace, "observations": receipts,
            "scores": perception_bench.report(protocol, results, protocol_sha256)}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    cfg = parser.parse_args(argv)
    try:
        plan = _perception_io.read_relative(cfg.root, "plan.json", _vision.MAX_SPEC_BYTES)
        sys.stdout.buffer.write(_canonical(run(cfg.root, plan, cfg.expect_sha256)) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
