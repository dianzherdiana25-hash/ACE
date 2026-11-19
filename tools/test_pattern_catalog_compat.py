import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tools.pattern_catalog import (
    CATALOG_SCHEMA,
    CATALOG_SCHEMA_V2,
    CONFLICT_TRACE_SCHEMA,
    DISTILL_SCHEMA_V2,
    build_catalog,
    diff_catalogs,
    export_snapshot_jsonl,
    normalize_pattern_for_proposer,
    trace_conflict_changes,
)
from tools.pattern_distill import DISTILL_SCHEMA


SCRIPT = Path(__file__).with_name("pattern_catalog.py")


def _pattern_v1(
    episode="ep-alpha",
    digest="a",
    *,
    signature="code:interval",
    keywords=("interval",),
    constraints=("edge_empty",),
    approach=("Sort intervals before merging.",),
    pitfalls=("Forgetting empty interval input.",),
    evidence="history_v1.jsonl",
    entry_index=1,
):
    return {
        "schema": DISTILL_SCHEMA,
        "event_class": "pattern_distilled",
        "kind": "semantic",
        "staging_only": True,
        "source_episode": episode,
        "task_shape": {
            "task_kind": "code",
            "signature": signature,
            "keywords": list(keywords),
            "constraints_detected": list(constraints),
        },
        "approach": list(approach),
        "pitfalls": list(pitfalls),
        "provenance": {
            "output_sha256": digest * 64,
            "instruction_sha256": "f" * 64,
            "task_kind": "code",
            "entry_index": entry_index,
            "evidence_file": evidence,
        },
    }


def _pattern_v2(
    episode="ep-alpha",
    digest="a",
    *,
    signature="code:interval",
    keywords=("interval",),
    constraints=("edge_empty",),
    approach=("Sort intervals before merging.",),
    pitfalls=("Forgetting empty interval input.",),
    evidence="history_v2.jsonl",
    entry_index=1,
    tags=("migrated", "v2"),
):
    record = _pattern_v1(
        episode=episode,
        digest=digest,
        signature=signature,
        keywords=keywords,
        constraints=constraints,
        approach=approach,
        pitfalls=pitfalls,
        evidence=evidence,
        entry_index=entry_index,
    )
    record["schema"] = DISTILL_SCHEMA_V2
    record["format_version"] = 2
    record["catalog_tags"] = list(tags)
    record["provenance"]["migrated_from"] = DISTILL_SCHEMA
    return record


def _proposer_parse_jsonl(jsonl_path: Path):
    """Exact standalone parser contract of tools/curriculum_propose.py (_read_catalog)."""
    patterns = {}
    for number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            not isinstance(record, dict)
            or record.get("schema") != DISTILL_SCHEMA
            or record.get("event_class") != "pattern_distilled"
        ):
            raise ValueError(f"line {number}: expected {DISTILL_SCHEMA}")
        shape = record.get("task_shape")
        provenance = record.get("provenance")
        if not isinstance(shape, dict) or not isinstance(provenance, dict):
            raise ValueError(f"line {number}: invalid task_shape/provenance")
        episode = record.get("source_episode")
        digest = provenance.get("output_sha256")
        if not isinstance(episode, str) or not episode.strip():
            raise ValueError(f"line {number}: invalid source_episode")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"line {number}: invalid output_sha256")
        key = (episode, digest)
        if key in patterns:
            raise ValueError(f"line {number}: duplicate pattern identity")
        approach = record.get("approach")
        if not isinstance(approach, list) or not approach or not all(isinstance(s, str) and s.strip() for s in approach):
            raise ValueError(f"line {number}: invalid approach")
        patterns[key] = {
            "task_kind": shape["task_kind"],
            "keywords": sorted(set(shape["keywords"])),
            "constraints_detected": sorted(set(shape["constraints_detected"])),
            "source_episode": episode,
            "output_sha256": digest,
            "approach": list(approach),
            "pitfalls": list(record["pitfalls"]),
        }
    return [patterns[k] for k in sorted(patterns)]


class PatternCatalogCrossVersionCompatTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write_jsonl(self, name: str, *rows: dict) -> Path:
        path = self.root / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_cross_version_export_remains_readable_by_proposer(self):
        legacy_a = _pattern_v1(episode="ep-1", digest="1")
        legacy_b = _pattern_v1(episode="ep-2", digest="2", keywords=("dp", "memo"), constraints=("time_limit",))
        raw_v1 = self.write_jsonl("v1_input.jsonl", legacy_a, legacy_b)

        snap_v1 = build_catalog([raw_v1], catalog_format="v1")
        self.assertEqual(snap_v1["schema"], CATALOG_SCHEMA)

        evolved_a = _pattern_v2(episode="ep-1", digest="1")
        evolved_b = _pattern_v2(episode="ep-2", digest="2", keywords=("dp", "memo"), constraints=("time_limit",))
        raw_v2 = self.write_jsonl("v2_input.jsonl", evolved_a, evolved_b)

        snap_v2 = build_catalog([raw_v2], previous=snap_v1, catalog_format="v2")
        self.assertEqual(snap_v2["schema"], CATALOG_SCHEMA_V2)
        self.assertEqual(snap_v2["format_version"], 2)
        self.assertEqual(snap_v2["version"], 2)
        self.assertEqual(
            snap_v2["parent_sha256"],
            hashlib.sha256(json.dumps(snap_v1, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        )

        export_v1 = self.root / "export_v1.jsonl"
        export_v2 = self.root / "export_v2.jsonl"
        export_v1.write_text(export_snapshot_jsonl(snap_v1), encoding="utf-8")
        export_v2.write_text(export_snapshot_jsonl(snap_v2), encoding="utf-8")

        parsed_v1 = _proposer_parse_jsonl(export_v1)
        parsed_v2 = _proposer_parse_jsonl(export_v2)
        self.assertEqual(parsed_v1, parsed_v2)

        # If curriculum_propose is present in combined workspace checkout, also verify live API directly.
        try:
            from tools.curriculum_propose import propose_curriculum
        except ImportError:
            propose_curriculum = None
        if propose_curriculum is not None:
            gaps_path = self.root / "gaps.json"
            gaps_path.write_text(
                json.dumps([
                    {
                        "id": "interval-kosong",
                        "priority": 3,
                        "task_kind": "code",
                        "keywords": ["interval"],
                        "constraints_detected": ["edge_empty"],
                    }
                ]),
                encoding="utf-8",
            )
            self.assertEqual(
                propose_curriculum(export_v1, gaps_path),
                propose_curriculum(export_v2, gaps_path),
            )

    def test_conflict_changes_across_versions_trace_back_to_raw_inputs(self):
        # Version 1:
        # - ep-resolved has a conflict across two lines
        # - ep-dropped has a conflict across two lines
        # - ep-becomes-conflict is clean on line 5
        # - ep-grows has a 2-variant conflict
        ep_resolved_a = _pattern_v1("ep-resolved", "1", approach=["Step A"])
        ep_resolved_b = _pattern_v1("ep-resolved", "1", approach=["Step B"])
        ep_dropped_a = _pattern_v1("ep-dropped", "2", approach=["Drop 1"])
        ep_dropped_b = _pattern_v1("ep-dropped", "2", approach=["Drop 2"])
        ep_clean = _pattern_v1("ep-becomes-conflict", "3", approach=["Clean v1"])
        ep_grows_a = _pattern_v1("ep-grows", "4", approach=["Grow 1"])
        ep_grows_b = _pattern_v1("ep-grows", "4", approach=["Grow 2"])

        in_v1 = self.write_jsonl(
            "catalog_v1.jsonl",
            ep_resolved_a,   # line 1
            ep_resolved_b,   # line 2
            ep_dropped_a,    # line 3
            ep_dropped_b,    # line 4
            ep_clean,        # line 5
            ep_grows_a,      # line 6
            ep_grows_b,      # line 7
        )
        snap_v1 = build_catalog([in_v1], catalog_format="v1")

        # Version 2 (upgraded format):
        # - ep-resolved is resolved to a single agreed v2 variant on line 1
        # - ep-becomes-conflict now collides across lines 2 and 3
        # - ep-new-conflict appears anew across lines 4 and 5
        # - ep-grows gains a 3rd variant on line 8 while preserving earlier 2 variants on lines 6 and 7
        # - ep-dropped is completely removed
        in_v2 = self.write_jsonl(
            "catalog_v2.jsonl",
            _pattern_v2("ep-resolved", "1", approach=["Step A canonical"]),     # line 1
            _pattern_v2("ep-becomes-conflict", "3", approach=["Clean v2"]),     # line 2
            _pattern_v2("ep-becomes-conflict", "3", approach=["Diverged v2"]),  # line 3
            _pattern_v2("ep-new-conflict", "5", approach=["New 1"]),            # line 4
            _pattern_v2("ep-new-conflict", "5", approach=["New 2"]),            # line 5
            _pattern_v1("ep-grows", "4", approach=["Grow 1"]),                  # line 6
            _pattern_v1("ep-grows", "4", approach=["Grow 2"]),                  # line 7
            _pattern_v2("ep-grows", "4", approach=["Grow 3"]),                  # line 8
        )
        snap_v2 = build_catalog([in_v2], previous=snap_v1, catalog_format="v2")

        trace_report = trace_conflict_changes(snap_v1, snap_v2)
        self.assertEqual(trace_report["schema"], CONFLICT_TRACE_SCHEMA)
        self.assertEqual(
            trace_report["summary"],
            {
                "added_from_pattern": 1,
                "added_new": 1,
                "removed_dropped": 1,
                "removed_resolved_to_pattern": 1,
                "variants_changed": 1,
            },
        )
        by_ep = {item["identity"]["source_episode"]: item for item in trace_report["traces"]}

        # 1. Resolved conflict points to old conflict lines (1, 2 in v1) and resolved pattern line (1 in v2).
        resolved = by_ep["ep-resolved"]
        self.assertEqual(resolved["change_type"], "removed_resolved_to_pattern")
        self.assertEqual(resolved["old_state"], "conflict")
        self.assertEqual(resolved["new_state"], "pattern")
        self.assertEqual(len(resolved["variants_removed"]), 2)
        self.assertEqual(
            [(p["role"], Path(p["catalog"]).name, p["line"]) for p in resolved["input_pointers"]],
            [
                ("old_conflict", "catalog_v1.jsonl", 1),
                ("old_conflict", "catalog_v1.jsonl", 2),
                ("new_pattern", "catalog_v2.jsonl", 1),
            ],
        )

        # 2. Pattern turning into conflict points back to clean v1 line 5 AND new v2 lines 2, 3.
        became = by_ep["ep-becomes-conflict"]
        self.assertEqual(became["change_type"], "added_from_pattern")
        self.assertEqual(became["old_state"], "pattern")
        self.assertEqual(became["new_state"], "conflict")
        self.assertEqual(
            [(p["role"], Path(p["catalog"]).name, p["line"]) for p in became["input_pointers"]],
            [
                ("old_pattern", "catalog_v1.jsonl", 5),
                ("new_conflict", "catalog_v2.jsonl", 2),
                ("new_conflict", "catalog_v2.jsonl", 3),
            ],
        )

        # 3. Conflict gaining 3rd variant exposes variants_added with line 8 pointer.
        grows = by_ep["ep-grows"]
        self.assertEqual(grows["change_type"], "variants_changed")
        self.assertEqual(len(grows["variants_added"]), 1)
        self.assertEqual(
            [(Path(s["catalog"]).name, s["line"]) for s in grows["variants_added"][0]["sources"]],
            [("catalog_v2.jsonl", 8)],
        )

        # 4. diff_catalogs embeds the same conflict_traces cleanly alongside legacy keys.
        diff = diff_catalogs(snap_v1, snap_v2)
        self.assertEqual(diff["from"]["schema"], CATALOG_SCHEMA)
        self.assertEqual(diff["to"]["schema"], CATALOG_SCHEMA_V2)
        self.assertEqual(diff["conflict_traces"], trace_report["traces"])

    def test_cli_v2_build_export_and_trace_conflicts_end_to_end(self):
        p1 = self.write_jsonl("c1.jsonl", _pattern_v1("ep-c", "a"), _pattern_v1("ep-clean", "b"))
        b1 = self.cli("build", str(p1), "--format", "v1")
        self.assertEqual(b1.returncode, 0, b1.stderr)
        s1_path = self.root / "snap1.json"
        s1_path.write_text(b1.stdout, encoding="utf-8")

        p2 = self.write_jsonl(
            "c2.jsonl",
            _pattern_v2("ep-c", "a", approach=["Alt 1"]),
            _pattern_v2("ep-c", "a", approach=["Alt 2"]),
            _pattern_v2("ep-clean", "b"),
        )
        b2 = self.cli("build", str(p2), "--previous", str(s1_path), "--format", "v2")
        self.assertEqual(b2.returncode, 0, b2.stderr)
        s2_path = self.root / "snap2.json"
        s2_path.write_text(b2.stdout, encoding="utf-8")

        exp = self.cli("export", str(s2_path))
        self.assertEqual(exp.returncode, 0, exp.stderr)
        exp_path = self.root / "exported.jsonl"
        exp_path.write_text(exp.stdout, encoding="utf-8")
        rows = _proposer_parse_jsonl(exp_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_episode"], "ep-clean")

        tr = self.cli("trace-conflicts", str(s1_path), str(s2_path))
        self.assertEqual(tr.returncode, 0, tr.stderr)
        tr_json = json.loads(tr.stdout)
        self.assertEqual(tr_json["summary"], {"added_from_pattern": 1})
        self.assertEqual(tr_json["traces"][0]["identity"]["source_episode"], "ep-c")

    def test_rejects_corrupted_v2_format_version_or_conflict_variant(self):
        p1 = self.write_jsonl("c1.jsonl", _pattern_v2("ep-1", "a"))
        snap = build_catalog([p1], catalog_format="v2")
        snap["format_version"] = 1  # invalid for v2 schema
        with self.assertRaisesRegex(ValueError, "format_version == 2"):
            export_snapshot_jsonl(snap)

        norm = normalize_pattern_for_proposer(_pattern_v2("ep-1", "a"))
        self.assertEqual(norm["schema"], DISTILL_SCHEMA)
        self.assertNotIn("format_version", norm)


if __name__ == "__main__":
    unittest.main()
