#!/usr/bin/env python3
"""Build, export, or compare local versioned pattern catalogs."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

if __package__:
    from .pattern_distill import DISTILL_SCHEMA
else:
    from pattern_distill import DISTILL_SCHEMA


CATALOG_SCHEMA = "ace.pattern-catalog.v1"
DIFF_SCHEMA = "ace.pattern-catalog-diff.v1"
DEFAULT_MAX_CHARS = 2048
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def _sha256(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _is_hash(value):
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_pattern(record):
    if not isinstance(record, dict) or (
        record.get("schema"), record.get("event_class"), record.get("kind")
    ) != (DISTILL_SCHEMA, "pattern_distilled", "semantic") or record.get("staging_only") is not True:
        raise ValueError("Expected a staging pattern_distilled record.")

    provenance = record.get("provenance")
    if not _is_text(record.get("source_episode")) or not isinstance(provenance, dict):
        raise ValueError("Expected source_episode and provenance.")
    if not _is_hash(provenance.get("output_sha256")):
        raise ValueError("Expected a lowercase SHA-256 in provenance.output_sha256.")

    shape = record.get("task_shape")
    if not isinstance(shape, dict) or not _is_text(shape.get("task_kind")):
        raise ValueError("Expected task_shape.task_kind.")
    for obj, field in (
        (record, "approach"), (record, "pitfalls"), (shape, "keywords"), (shape, "constraints_detected"),
    ):
        items = obj.get(field)
        if not isinstance(items, list) or not all(_is_text(item) for item in items):
            raise ValueError(f"Expected a list of nonempty strings in {field}.")
    if not record["approach"]:
        raise ValueError("Expected at least one approach step.")
    return record["source_episode"], provenance["output_sha256"]


def _quality(record, max_chars):
    source = record["provenance"]
    shape = record["task_shape"]
    entry = source.get("entry_index")
    evidence = {
        "evidence_file": _is_text(source.get("evidence_file")),
        "entry_index": type(entry) is int and entry > 0,
        "task_kind": source.get("task_kind") == shape["task_kind"],
        "output_sha256": _is_hash(source.get("output_sha256")),
        "instruction_sha256": _is_hash(source.get("instruction_sha256")),
    }
    length = len(_json(record))
    signature = shape.get("signature")
    keywords = len(set(shape["keywords"]))
    constraints = len(set(shape["constraints_detected"]))
    provenance_points = 8 * sum(evidence.values())
    length_points = 20 if length <= max_chars else 0
    shape_points = (
        10 * (shape["task_kind"] != "unknown")
        + 10 * (_is_text(signature) and not signature.endswith(":generic"))
        + 20 * bool(keywords or constraints)
    )
    return {
        "score": provenance_points + length_points + shape_points,
        "provenance": {"points": provenance_points, "checks": evidence},
        "length": {"points": length_points, "chars": length, "max_chars": max_chars},
        "task_shape": {"points": shape_points, "keywords": keywords, "constraints": constraints},
    }


def _read_patterns(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line, object_pairs_hook=_unique_object)
                key = _validate_pattern(record)
                data = _json(record)
                data.encode("utf-8")  # Fail at the input line, including lone Unicode surrogates.
            except (ValueError, RecursionError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid catalog record: {exc}") from exc
            yield key, record, {"catalog": str(path), "line": line_number}


def _identity(key):
    return {"source_episode": key[0], "output_sha256": key[1]}


def _content_digest(record):
    # A copy or excerpt can change the evidence locator while preserving the pattern.
    provenance = {key: value for key, value in record["provenance"].items()
                  if key not in {"evidence_file", "entry_index"}}
    return _sha256({**record, "provenance": provenance})


def _sources(candidates):
    return sorted((ref for _, ref in candidates), key=lambda ref: (ref["catalog"], ref["line"]))


def build_catalog(paths, *, previous=None, max_chars=DEFAULT_MAX_CHARS):
    """Deduplicate and score patterns into one versioned snapshot."""
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer.")
    paths = sorted(set(map(Path, paths)), key=str)
    if not paths:
        raise ValueError("At least one JSONL catalog is required.")

    version, parent = 1, None
    if previous is not None:
        _index_snapshot(previous)
        version, parent = previous["version"] + 1, _sha256(previous)

    groups = defaultdict(lambda: defaultdict(list))
    for path in paths:
        for key, record, ref in _read_patterns(path):
            groups[key][_content_digest(record)].append((record, ref))

    patterns, conflicts = [], []
    for key, variants in sorted(groups.items()):
        if len(variants) > 1:
            conflicts.append({
                **_identity(key),
                "variants": [{"content_sha256": digest, "sources": _sources(candidates)}
                             for digest, candidates in sorted(variants.items())],
            })
            continue
        candidates = next(iter(variants.values()))
        # Prefer a complete locator; break ties by canonical JSON, independently of input order.
        record = min((candidate for candidate, _ in candidates), key=lambda candidate: (
            -_quality(candidate, max_chars)["provenance"]["points"], _json(candidate),
        ))
        patterns.append({"pattern": record, "quality": _quality(record, max_chars),
                         "sources": _sources(candidates)})
    return {
        "schema": CATALOG_SCHEMA, "version": version, "parent_sha256": parent,
        "max_chars": max_chars, "patterns": patterns, "conflicts": conflicts,
    }


def _index_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("schema") != CATALOG_SCHEMA:
        raise ValueError("Expected ace.pattern-catalog.v1.")
    version = snapshot.get("version")
    if type(version) is not int or version <= 0 or "parent_sha256" not in snapshot:
        raise ValueError("Expected a positive catalog version and parent_sha256.")
    parent = snapshot["parent_sha256"]
    if (version == 1 and parent is not None) or (version > 1 and not _is_hash(parent)):
        raise ValueError("Invalid parent_sha256 for catalog version.")
    if type(snapshot.get("max_chars")) is not int or snapshot["max_chars"] <= 0:
        raise ValueError("Invalid catalog max_chars.")
    patterns = snapshot.get("patterns")
    conflicts = snapshot.get("conflicts")
    if not isinstance(patterns, list) or not isinstance(conflicts, list):
        raise ValueError("Expected catalog pattern and conflict lists.")

    accepted, rejected = {}, {}
    for entry in patterns:
        if not isinstance(entry, dict):
            raise ValueError("Expected a catalog entry object.")
        key = _validate_pattern(entry.get("pattern"))
        if key in accepted:
            raise ValueError("Duplicate identity in catalog patterns.")
        if entry.get("quality") != _quality(entry["pattern"], snapshot["max_chars"]):
            raise ValueError("Catalog quality does not match pattern.")
        accepted[key] = entry
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            raise ValueError("Expected a catalog conflict object.")
        episode = conflict.get("source_episode")
        digest = conflict.get("output_sha256")
        if not _is_text(episode) or not _is_hash(digest):
            raise ValueError("Invalid catalog conflict identity.")
        key = episode, digest
        if key in accepted or key in rejected:
            raise ValueError("Duplicate identity in catalog conflicts.")
        rejected[key] = conflict
    return accepted, rejected


def _delta(old, new):
    return {
        "added": [_identity(key) for key in sorted(new.keys() - old.keys())],
        "removed": [_identity(key) for key in sorted(old.keys() - new.keys())],
        "changed": [
            {**_identity(key), "fields": [
                field for field in sorted(old[key].keys() | new[key].keys())
                if field not in old[key] or field not in new[key] or old[key][field] != new[key][field]
            ]}
            for key in sorted(old.keys() & new.keys()) if old[key] != new[key]
        ],
    }


def diff_catalogs(old, new):
    """Compare catalog versions by pattern identity and conflict identity."""
    old_patterns, old_conflicts = _index_snapshot(old)
    new_patterns, new_conflicts = _index_snapshot(new)
    return {
        "schema": DIFF_SCHEMA,
        "from": {"version": old["version"], "sha256": _sha256(old)},
        "to": {"version": new["version"], "sha256": _sha256(new)},
        "patterns": _delta(old_patterns, new_patterns),
        "conflicts": _delta(old_conflicts, new_conflicts),
    }


def _read_snapshot(path):
    snapshot = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    _json(snapshot).encode("utf-8")
    return snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Merge source JSONL catalogs into a versioned JSON snapshot.")
    build.add_argument("catalogs", nargs="+", type=Path)
    build.add_argument("--previous", type=Path, help="Previous snapshot for version and parent hash.")
    build.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                       help="Length budget for quality scoring (default %(default)s).")
    export = sub.add_parser("export", help="Emit accepted patterns as pattern_distilled JSONL.")
    export.add_argument("snapshot", type=Path)
    diff = sub.add_parser("diff", help="Compare old and new snapshots by identity.")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            previous = _read_snapshot(args.previous) if args.previous else None
            output = _json(build_catalog(args.catalogs, previous=previous, max_chars=args.max_chars)) + "\n"
        elif args.command == "diff":
            output = _json(diff_catalogs(_read_snapshot(args.old), _read_snapshot(args.new))) + "\n"
        else:
            patterns, _ = _index_snapshot(_read_snapshot(args.snapshot))
            output = "".join(_json(patterns[key]["pattern"]) + "\n" for key in sorted(patterns))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    sys.stdout.buffer.write(output.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
