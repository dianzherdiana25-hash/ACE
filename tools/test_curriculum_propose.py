"""Fixture usulan kurikulum mandiri; katalog dibuat lewat distiler repo."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.curriculum_propose import propose_curriculum
from tools.pattern_distill import distill_evidence


SCRIPT = Path(__file__).with_name("curriculum_propose.py")


class CurriculumProposeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.catalog = root / "patterns.jsonl"
        self.gaps = root / "gaps.json"
        self.output = root / "proposal.json"
        episodes = root / "episodes.jsonl"
        rows = [
            ("z", "code", "interval kosong", "def merge_z(xs): pass"),
            ("a", "code", "interval kosong", "def merge_a(xs): pass"),
            ("a", "code", "interval kosong", "def merge_b(xs): pass"),
            ("other", "language", "interval larik kosong", "Periksa urutan."),
            ("partial", "code", "larik", "def larik(xs): pass"),
        ]
        episodes.write_text("".join(json.dumps({
            "id": ep, "task_kind": kind, "instruction": instruction,
            "ratified": True, "output": output, "reasons": ["Periksa masukan."],
        }) + "\n" for ep, kind, instruction, output in rows), encoding="utf-8")
        distill_evidence([episodes], self.catalog)
        self.gap_list = [
            {"id": "z", "priority": 2, "task_kind": "code", "keywords": ["interval"]},
            {"id": "open", "priority": 8, "task_kind": "code", "keywords": ["larik"],
             "constraints_detected": ["edge_empty"]},
            {"id": "a", "priority": 2, "task_kind": "code", "constraints_detected": ["edge_empty"]},
            {"id": "first", "priority": 9, "task_kind": "code", "keywords": ["kosong", "interval"],
             "constraints_detected": ["edge_empty"]},
        ]
        self.write_gaps(self.gap_list)

    def write_gaps(self, rows):
        self.gaps.write_text(json.dumps(rows), encoding="utf-8")

    def cli(self, seed="1", output=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--patterns", str(self.catalog), "--gaps",
             str(self.gaps), "--output", str(output or self.output)],
            capture_output=True, env={**os.environ, "PYTHONHASHSEED": seed},
        )

    def test_priority_then_gap_id_and_complete_pattern_provenance(self):
        result = propose_curriculum(self.catalog, self.gaps)
        proposals = result["proposals"]
        self.assertEqual([p["gap"]["id"] for p in proposals], ["first", "a", "z"])
        self.assertEqual(proposals[0]["gap"], {**self.gap_list[3], "keywords": ["interval", "kosong"]})
        patterns = [json.loads(line) for line in self.catalog.read_text(encoding="utf-8").splitlines()]
        expected = [{
            "source_episode": p["source_episode"], "output_sha256": p["provenance"]["output_sha256"],
            "approach": p["approach"], "pitfalls": p["pitfalls"],
        } for p in patterns if p["source_episode"] in {"a", "z"}]
        expected.sort(key=lambda p: (p["source_episode"], p["output_sha256"]))
        self.assertEqual(len(expected), 3)
        for proposal in proposals:
            self.assertEqual(proposal["source_patterns"], expected)

    def test_partial_matches_across_patterns_and_wrong_kind_leave_gap_open(self):
        result = propose_curriculum(self.catalog, self.gaps)
        self.assertEqual(result["open_gaps"], [self.gap_list[1]])
        self.assertNotIn("open", [p["gap"]["id"] for p in result["proposals"]])

    def test_cli_byte_identical_across_runs_and_input_permutations(self):
        first = self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = self.output.read_bytes()
        self.assertEqual(json.loads(expected), propose_curriculum(self.catalog, self.gaps))
        second = self.cli(seed="2")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.output.read_bytes(), expected)
        rows = self.catalog.read_bytes().splitlines(keepends=True)
        self.catalog.write_bytes(b"".join(reversed(rows)))
        self.write_gaps(list(reversed(self.gap_list)))
        third = self.cli(seed="3")
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual(self.output.read_bytes(), expected)

    def test_empty_catalog_or_gap_list(self):
        self.catalog.write_bytes(b"")
        result = propose_curriculum(self.catalog, self.gaps)
        self.assertEqual(result["proposals"], [])
        self.assertEqual([g["id"] for g in result["open_gaps"]], ["first", "open", "a", "z"])
        self.write_gaps([])
        self.assertEqual(propose_curriculum(self.catalog, self.gaps)["open_gaps"], [])

    def test_ambiguous_or_invalid_gap_does_not_replace_prior_output(self):
        self.output.write_bytes(b"previous")
        gap = self.gap_list[0]
        for rows in ([gap, gap], [{**gap, "priority": True}], [{**gap, "keywords": []}],
                     [{**gap, "keywords": "interval"}], [{**gap, "misspelled_filter": []}]):
            with self.subTest(rows=rows):
                self.write_gaps(rows)
                self.assertEqual(self.cli().returncode, 2)
                self.assertEqual(self.output.read_bytes(), b"previous")

    def test_duplicate_or_invalid_patterns_identified_by_line(self):
        lines = self.catalog.read_bytes().splitlines()
        first = json.loads(lines[0])
        row = json.loads(lines[1])
        for bad in (first, {**row, "event_class": "receipt"}, {**row, "provenance": {}},
                    {**row, "task_shape": {}}, {**row, "approach": []}):
            with self.subTest(bad=bad):
                self.catalog.write_text(json.dumps(first) + "\n" + json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "baris 2"):
                    propose_curriculum(self.catalog, self.gaps)

    def test_cli_input_cannot_be_overwritten(self):
        for path in (self.catalog, self.gaps):
            before = path.read_bytes()
            self.assertEqual(self.cli(output=path).returncode, 2)
            self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
