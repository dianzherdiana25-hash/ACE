from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .dataset_cleaner import clean
from .test_data_analyst import column, table


class CleanerTests(unittest.TestCase):
    def test_source_held_unchanged_and_quarantine_cites_bad_input(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"record,value\n Small ,02\nsmall,4\nlarge,bad\nlarge,8\n,9\n"
            origin, spec = table(root, raw, [column("record", "category", nullable=True, normalize="casefold"),
                                            column("value", "integer")])
            plan = {"schema": "ace.institute.clean-plan.v1", "data": origin, "format": spec, "unique_by": ["record"]}
            result, report = clean(plan, identity(plan), root)
            self.assertEqual((root / "source.csv").read_bytes(), raw)
            self.assertEqual(result, b"record,value\nsmall,2\nlarge,8\n")
            self.assertEqual(report["csv_sha256"], sha256(result).hexdigest())
            self.assertEqual(report["lineage"][0]["changed_fields"], ["record", "value"])
            self.assertEqual([row["line"] for row in report["quarantine"]], [3, 4, 6])
            self.assertEqual(report["quarantine"][0]["issues"][0]["first_line"], 2)
            self.assertEqual(report["quarantine"][2]["issues"][0]["reason"], "missing_dedup_key")
