#!/usr/bin/env python3
"""Ekspor catatan siklus direktur dari berkas JSON yang tercatat di Git."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

if __package__:
    from ._director_sources import GitSnapshot, SourceError, repo_path, write_json
else:
    from _director_sources import GitSnapshot, SourceError, repo_path, write_json


LABEL = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}")


def _label(value):
    return isinstance(value, str) and bool(LABEL.fullmatch(value))


def record_cycles(repo, paths):
    records = {}
    for raw_path in paths:
        path = repo_path(raw_path)
        trace = repo.read_json(path)
        if not isinstance(trace, dict):
            raise SourceError("Berkas siklus harus berupa objek JSON.")
        cycle = trace.get("cycle")
        status = trace.get("status")
        if type(cycle) is not int or cycle < 1 or cycle in records or not _label(status):
            raise SourceError("Nomor siklus harus positif dan unik. Status harus berupa label.")
        origin = trace.get("origin")
        issues = []
        if origin is None:
            issues.append("missing_origin")
        elif not _label(origin):
            raise SourceError("origin harus berupa label otak yang tercatat.")
        raw_decisions = trace.get("decisions")
        if raw_decisions is None:
            issues.append("missing_decisions")
            raw_decisions = []
        elif not isinstance(raw_decisions, list):
            raise SourceError("decisions harus berupa daftar.")
        decisions = []
        seen = set()
        for index, item in enumerate(raw_decisions):
            if not isinstance(item, dict) or not all(_label(item.get(key)) for key in ("id", "decision")):
                raise SourceError(f"Keputusan /decisions/{index} harus memuat id dan decision.")
            if item["id"] in seen:
                raise SourceError(f"ID keputusan ganda pada /decisions/{index}.")
            seen.add(item["id"])
            decisions.append({"id": item["id"], "decision": item["decision"],
                              "source_pointer": f"/decisions/{index}"})
        records[cycle] = {
            "cycle": cycle, "status": status, "origin": origin,
            "source": path, "decisions": decisions, "issues": issues,
        }
    return {"schema": "ace.director.cycle-record.v1", "commit": repo.commit,
            "cycles": [records[cycle] for cycle in sorted(records)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycles", nargs="+", help="Path berkas siklus dalam commit.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args(argv)
    try:
        result = record_cycles(GitSnapshot(args.repo, args.revision), args.cycles)
    except SourceError as exc:
        parser.exit(2, f"Error. {exc}\n")
    write_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
