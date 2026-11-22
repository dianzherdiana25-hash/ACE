import csv
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .data_anonymizer import anonymize
from .test_tabular_engine import save


class AnonymizationTests(unittest.TestCase):
    def test_mask_drop_and_keyed_labels_and_scope(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref = save(root, "data.csv", b"name,email,book,mark\nAlias A,test@example.test,first,4\nalias a,foo@example.test,second,5\n")
            plan = {"schema": "ace.production.anonymization-plan.v1", "data": ref, "scope": "classroom",
                    "max_records": 6, "columns": [{"column": name, "operation": op} for name, op in
                    (("name", "pseudonym"), ("email", "mask"), ("book", "drop"), ("mark", "keep"))]}
            raw, proof = anonymize(plan, identity(plan), root, key=bytes(range(32)))
            first, second = list(csv.DictReader(StringIO(raw.decode())))
            self.assertEqual(first["name"], second["name"])
            self.assertTrue(first["name"].startswith("p_"))
            self.assertEqual(first["email"], "[REDACTED]")
            self.assertNotIn("book", first)
            self.assertNotIn("Alias A", str(proof))
            plan["scope"] = "private"
            self.assertNotEqual(raw, anonymize(plan, identity(plan), root, key=bytes(range(32)))[0])
            with self.assertRaisesRegex(ProductionError, "Kunci"):
                anonymize(plan, identity(plan), root)
