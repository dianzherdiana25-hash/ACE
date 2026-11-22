from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .open_dataset_publisher import prepare_dataset
from .test_comparison_analyst import save
from .test_data_analyst import column, table


class DatasetDraftTests(unittest.TestCase):
    def test_rare_groups_suppressed_and_direct_identifiers_never_written(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"id,group,measure\nfirst,a,8\nsecond,a,9\nthird,z,21\n"
            link, spec = table(root, raw, [column("id", "text"), column("group", "category"), column("measure", "integer")])
            plan = {"schema": "ace.institute.open-dataset-plan.v1", "dataset": link, "format": spec,
                    "columns": [{"id": key, "release_role": role} for key, role in (
                        ("id", "direct_identifier"), ("group", "quasi_identifier"), ("measure", "public"))],
                    "policy": {"min_group": 2, "rare_groups": "suppress"},
                    "license": {"id": "fixture", "approved_scope": "fixture:permission", **save(root, "terms", b"Permission fixture")}}
            cleaned, result = prepare_dataset(plan, identity(plan), root)
            self.assertEqual(cleaned, b"group,measure\na,8\na,9\n")
            self.assertEqual(result["suppressed_rows"], 1)
            self.assertEqual(result["dropped_columns"], ["id"])
            self.assertEqual((root / link["path"]).read_bytes(), raw)
            plan["policy"]["rare_groups"] = "hold"
            self.assertIsNone(prepare_dataset(plan, identity(plan), root)[0])
