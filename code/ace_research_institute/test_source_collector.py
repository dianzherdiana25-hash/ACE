from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .source_collector import collect


HEADER = ("| id | population | outcome | context | value | unit | n | lower | upper |\n"
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")


def source(root, key, group, measurement=None, created="2025-01-03", kind="peer_reviewed", **kwargs):
    raw = (f"# {key}\n\n## Hasil\n# Note\nCahaya lokal diukur.\n\n" if measurement is None else
           f"# {key}\n\n## Hasil\n{HEADER}{measurement}\n")
    return source_with_bytes(root, key, group, raw.encode(), created, kind, **kwargs)


def source_with_bytes(root, key, group, raw, created="2025-01-03", kind="peer_reviewed", **kwargs):
    name = f"{key}.md"
    (root / name).write_bytes(raw)
    return {"id": key, "path": name, "sha256": sha256(raw).hexdigest(), "title": key, "published": created,
            "kind": kind, "independence_group": group, "declared_topics": ["cahaya"],
            "methods_ref": "fixture:method", "data_ref": "fixture:data", "license_ref": "fixture:license"} | kwargs


def source_plan(sources):
    return {"schema": "ace.institute.source-plan.v1", "topics": ["cahaya"], "as_of": "2025-01-20",
            "max_age_days": 365, "minimum_score": 70, "sources": sources}


class CollectorTests(unittest.TestCase):
    def test_tally_independence_reasons_and_hash_verification(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = source_plan([source(root, "actual", "one"), source(root, "later", "two", created="2025-01-31")])
            report = collect(plan, identity(plan), root)
            self.assertEqual(report["independent_groups_admitted"], ["one"])
            self.assertEqual((report["admitted"], report["held"]), (1, 1))
            self.assertEqual(report["sources"][0]["supporting_lines"], [{"line": 5, "terms": ["cahaya"]}])
            self.assertIn("future_date", report["sources"][1]["hold_reasons"])
            original = (root / "actual.md").read_bytes()
            plan["sources"].append(source_with_bytes(root, "copied", "other", original))
            report = collect(plan, identity(plan), root)
            copied = next(row for row in report["sources"] if row["id"] == "copied")
            self.assertEqual(copied["hold_reasons"], ["duplicate_source_bytes"])
            (root / "actual.md").write_bytes(original + b"x")
            with self.assertRaisesRegex(ResearchError, "anchor"):
                collect(plan, identity(plan), root)
