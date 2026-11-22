from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .tabular_engine import transform


def save(root, name, raw):
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": sha256(raw).hexdigest()}


class TableTests(unittest.TestCase):
    def test_join_pivot_aggregate_preserve_lineage_and_absent_values(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = save(root, "notes.csv", b"section,school,metric\na,north,2\na,north,4\na,south,\nb,north,7\n")
            names = save(root, "schools.csv", b"school,region\nnorth,uptown\nsouth,downtown\n")
            plan = {"schema": "ace.production.table-plan.v1", "input": "base", "max_rows": 40,
                    "tables": [{"id": "base", **rows}, {"id": "lookup", **names}],
                    "steps": [{"op": "join", "kind": "left", "right": "lookup", "left_keys": ["school"],
                               "right_keys": ["school"], "prefix": "ref"},
                              {"op": "pivot", "rows": ["section"], "pivot": "ref_region", "measure": "metric", "function": "mean"}]}
            raw, proof = transform(plan, identity(plan), root)
            self.assertEqual(raw, b"section,by_downtown,by_uptown\na,,3\nb,,7\n")
            self.assertEqual(proof["rows"], 2)
            self.assertEqual(len(proof["row_provenance"][0]["input"]), 5)
            self.assertEqual(proof["output_sha256"], sha256(raw).hexdigest())
            plan["steps"][1] = {"op": "aggregate", "keys": ["section", "ref_region"],
                                "metrics": [{"name": "total", "column": "metric", "function": "sum"},
                                            {"name": "n", "column": "metric", "function": "count"}]}
            result = transform(plan, identity(plan), root)[0]
            self.assertEqual(result, b"section,ref_region,total,n\na,downtown,,0\na,uptown,6,2\nb,uptown,7,1\n")
            plan["tables"][1].update(save(root, "schools.csv", b"school,region\nnorth,one\nnorth,two\n"))
            with self.assertRaisesRegex(ProductionError, "kunci kanan unik"):
                transform(plan, identity(plan), root)
