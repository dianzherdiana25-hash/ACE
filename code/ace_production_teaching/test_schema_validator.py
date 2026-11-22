import unittest

from ._contracts import ProductionError
from .schema_validator import validate


class SchemaTests(unittest.TestCase):
    def test_nested_paths_and_boolean_distinct_from_integer(self):
        spec = {"type": "object", "required": ["items", "active"], "properties": {
            "active": {"type": "boolean"},
            "items": {"type": "array", "min_items": 1, "items": {"type": "object", "required": ["id", "points"],
                         "properties": {"id": {"type": "string", "format": "id"},
                                        "points": {"type": "integer", "min": 0, "max": 30}}}}}}
        record = {"items": [{"id": "Valid Name", "points": True, "path/to": 8}]}
        reasons = {(row["path"], row["rule"]) for row in validate(record, spec)["errors"]}
        self.assertEqual(reasons, {("/active", "required"), ("/items/0/id", "format"),
                                   ("/items/0/points", "type"), ("/items/0/path~1to", "additional")})
        self.assertTrue(validate({"active": False, "items": [{"id": "ok", "points": 30}]}, spec)["valid"])
        with self.assertRaisesRegex(ProductionError, "Kata kunci"):
            validate(2, {"type": "integer", "unknown": 8})
