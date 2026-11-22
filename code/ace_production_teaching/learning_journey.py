"""Arsipkan perjalanan learner pseudonim sebagai kumpulan histori dan receipt ber-hash."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._artifacts import evidence, package, unpack
from ._contracts import (ProductionError, anchor, canonical, day, decode, digest, identifier,
                         items, obj, read, schema, source_bytes)
from .session_manager import verify_session


def archive_journey(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.journey-plan.v1", ("learner", "sessions"))
    learner = identifier(plan["learner"], "Learner pseudonim")
    options = []
    seen = set()
    files = {}
    total = 0
    for row in items(plan["sessions"], 80, 1):
        obj(row, ("date", "id", "trace", "initial_sha256", "head_sha256"))
        cid = identifier(row["id"], "Sesi")
        stamp = day(row["date"])
        if cid in seen:
            raise ProductionError("ID sesi perjalanan ganda.")
        seen.add(cid)
        ref = obj(row["trace"], ("path", "sha256"))
        raw = source_bytes(root, ref["path"], ref["sha256"], 1_000_000)
        total += len(raw)
        if total > 12_000_000:
            raise ProductionError("Histori perjalanan melewati batas byte.")
        trace = [decode(entry) for entry in raw.splitlines() if entry.strip()]
        items(trace, 161, 1)
        if any(entry["session"] != cid for entry in trace) or trace[-1]["action"] != "closed":
            raise ProductionError("Arsip membutuhkan penutupan sesi yang sesuai.")
        if verify_session(trace, digest(row["initial_sha256"])) != digest(row["head_sha256"]):
            raise ProductionError("Head receipt sesi berbeda.")
        if any(("text" in event or "answer" in event) for event in trace):
            raise ProductionError("Receipt arsip tidak boleh membawa jawaban mentah.")
        file = f"sessions/{cid}.jsonl"
        files[file] = raw
        options.append({"id": cid, "date": stamp.isoformat(), "file": file, "trace_sha256": ref["sha256"],
                        "head_sha256": row["head_sha256"], "event_count": len(trace)})
    record = {"schema": "ace.teaching.journey-manifest.v1", "plan_sha256": expected, "learner": learner,
              "timeline": sorted(options, key=lambda row: (row["date"], row["id"])), "files": evidence(files)}
    data = package({**files, "manifest.json": canonical(record) + b"\n"})
    if evidence({key: value for key, value in unpack(data).items() if key != "manifest.json"}) != record["files"]:
        raise ProductionError("Arsip perjalanan tidak konsisten dengan manifest.")
    return data, {"schema": "ace.teaching.journey-receipt.v1", "archive_sha256": sha256(data).hexdigest(), "manifest": record}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, record = archive_journey(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(record) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
