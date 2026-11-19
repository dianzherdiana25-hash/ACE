import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.pattern_catalog import build_catalog, diff_catalogs
from tools.pattern_distill import DISTILL_SCHEMA, distill_evidence


SCRIPT = Path(__file__).with_name("pattern_catalog.py")


def pattern(episode="fixture", digest="a", *, evidence="history.jsonl", signature="code:sum"):
    return {
        "schema": DISTILL_SCHEMA, "event_class": "pattern_distilled",
        "kind": "semantic", "staging_only": True, "source_episode": episode,
        "task_shape": {"task_kind": "code", "signature": signature,
                       "keywords": ["sum"], "constraints_detected": []},
        "approach": ["Use two operands."], "pitfalls": [],
        "provenance": {"output_sha256": digest * 64, "instruction_sha256": "f" * 64,
                       "task_kind": "code", "entry_index": 1, "evidence_file": evidence},
    }


class PatternCatalogTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write(self, name, *patterns):
        path = self.root / name
        path.write_text("".join(json.dumps(row) + "\n" for row in patterns), encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", check=False)

    def test_duplicates_include_all_pointers_and_prefer_complete_locator(self):
        row = pattern()
        first = self.write("first.jsonl", row, row)
        elsewhere = pattern(evidence="copy.jsonl")
        del elsewhere["provenance"]["entry_index"]
        second = self.write("second.jsonl", elsewhere)
        result = build_catalog([second, first, first])
        self.assertEqual(result, build_catalog([first, second]))
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["patterns"], [{
            "pattern": row, "quality": {
                "score": 100,
                "provenance": {"points": 40, "checks": dict.fromkeys(row["provenance"], True)},
                "length": {"points": 20, "chars": len(json.dumps(row)), "max_chars": 2048},
                "task_shape": {"points": 40, "keywords": 1, "constraints": 0},
            },
            "sources": [{"catalog": str(first), "line": 1}, {"catalog": str(first), "line": 2},
                        {"catalog": str(second), "line": 1}],
        }])

    def test_conflicts_are_quarantined_and_distinct_outputs_are_kept(self):
        first = self.write("first.jsonl", pattern())
        changed = pattern()
        changed["approach"] = ["Use a third operand."]
        second = self.write("second.jsonl", changed, pattern(digest="b"))
        result = build_catalog([first, second])
        self.assertEqual([entry["pattern"] for entry in result["patterns"]], [pattern(digest="b")])
        conflict, = result["conflicts"]
        self.assertEqual((conflict["source_episode"], conflict["output_sha256"]), ("fixture", "a" * 64))
        self.assertEqual(len({variant["content_sha256"] for variant in conflict["variants"]}), 2)
        self.assertEqual({item["catalog"] for variant in conflict["variants"] for item in variant["sources"]},
                         {str(first), str(second)})

    def test_quality_explains_long_incomplete_and_generic_patterns(self):
        row = pattern(signature="code:generic")
        row["task_shape"]["keywords"] = []
        del row["provenance"]["instruction_sha256"]
        catalog = self.write("one.jsonl", row)
        quality = build_catalog([catalog], max_chars=50)["patterns"][0]["quality"]
        self.assertEqual(quality["score"], 42)
        self.assertFalse(quality["provenance"]["checks"]["instruction_sha256"])
        self.assertGreater(quality["length"]["chars"], quality["length"]["max_chars"])
        self.assertEqual(quality["task_shape"], {"points": 10, "keywords": 0, "constraints": 0})
        canonical_length = len(json.dumps(row, ensure_ascii=False, sort_keys=True))
        self.assertEqual(build_catalog([catalog], max_chars=canonical_length)["patterns"][0]["quality"]
                         ["length"]["points"], 20)

    def test_version_and_diff_cover_add_remove_change_and_conflict(self):
        shared = pattern("shared")
        first = self.write("before.jsonl", pattern("removed"), shared)
        old = build_catalog([first])
        changed = pattern("shared", signature="code:other")
        conflict = pattern("removed", signature="code:other")
        second = self.write("after.jsonl", changed, pattern("added"), pattern("removed"), conflict)
        new = build_catalog([second], previous=old)
        delta = diff_catalogs(old, new)
        self.assertEqual(old["version"], 1)
        self.assertIsNone(old["parent_sha256"])
        self.assertEqual(new["version"], 2)
        expected = hashlib.sha256(json.dumps(old, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        self.assertEqual(new["parent_sha256"], expected.hexdigest())
        self.assertEqual(new["parent_sha256"], delta["from"]["sha256"])
        self.assertEqual([key["source_episode"] for key in delta["patterns"]["added"]], ["added"])
        self.assertEqual([key["source_episode"] for key in delta["patterns"]["removed"]], ["removed"])
        self.assertEqual(delta["patterns"]["changed"], [
            {"source_episode": "shared", "output_sha256": "a" * 64, "fields": ["pattern", "quality", "sources"]},
        ])
        self.assertEqual([key["source_episode"] for key in delta["conflicts"]["added"]], ["removed"])

    def test_cli_build_export_and_diff_a_real_distiller_fixture(self):
        episode = self.write("episode.jsonl", {
            "id": "fixture", "task_kind": "code", "instruction": "Buat fungsi jumlah tanpa loop.",
            "ratified": True, "output": "def jumlah(x,y):\n    return x + y",
        })
        distilled = self.root / "staging.jsonl"
        distill_evidence([episode], distilled)
        original = distilled.read_bytes()

        first = self.cli("build", distilled)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_path = self.root / "v1.json"
        first_path.write_text(first.stdout, encoding="utf-8")
        exported = self.cli("export", first_path)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(json.loads(exported.stdout), json.loads(original))

        second = self.cli("build", distilled, "--previous", first_path)
        self.assertEqual(second.returncode, 0, second.stderr)
        second_path = self.root / "v2.json"
        second_path.write_text(second.stdout, encoding="utf-8")
        diff = self.cli("diff", first_path, second_path)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertEqual(json.loads(diff.stdout)["patterns"], {"added": [], "removed": [], "changed": []})
        self.assertEqual(distilled.read_bytes(), original)

    def test_invalid_line_is_rejected_without_partial_output(self):
        path = self.write("invalid.jsonl", pattern(), {"schema": "bogus"})
        result = self.cli("build", path)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid.jsonl:2", result.stderr)

    def test_invalid_snapshots_are_rejected(self):
        source = self.write("one.jsonl", pattern())
        snapshot = build_catalog([source])
        snapshot["patterns"].append(snapshot["patterns"][0])
        broken = self.write("broken.json", snapshot)
        result = self.cli("export", broken)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("Duplicate identity", result.stderr)

    def test_empty_input_catalog_and_absent_catalog_are_distinct(self):
        self.assertEqual(build_catalog([self.write("empty.jsonl")])["patterns"], [])
        with self.assertRaisesRegex(ValueError, "At least one JSONL"):
            build_catalog([])


if __name__ == "__main__":
    unittest.main()
