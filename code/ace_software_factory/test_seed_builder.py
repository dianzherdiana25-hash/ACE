"""Verifier data seed terhadap bind parameters, tipe, dan transaksi FK."""
from contextlib import closing
from hashlib import sha256
import sqlite3
import unittest

from ace_software_factory import seed_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.test_schema_designer import repository


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.model = repository()
        self.plan = {"schema": "ace.factory-seed-plan.v1", "model_sha256": identity(self.model),
                     "source_ref": "fixture/import",
                     "rows": [{"id": "item_one", "table": "item", "source_ref": "fixture/row/1",
                               "values": {"id": 6, "category_id": 2}},
                              {"id": "cat_two", "table": "category", "source_ref": "fixture/row/2",
                               "values": {"id": 2, "name": "Uji 'kategori'"}}]}

    def build(self):
        return seed_builder.build(self.model, self.plan, identity(self.plan))

    def test_atomic_seed_accepts_references_out_of_order_and_keeps_defaults(self):
        data, report = self.build()
        self.assertEqual(report["counts"], {"category": 1, "item": 1})
        self.assertEqual(report["seed_sha256"], sha256(data).hexdigest())
        self.assertEqual(report["receipts"][0]["source_ref"], "fixture/row/1")
        self.assertNotIn("values", report["receipts"][0])
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(data)
            self.assertEqual(db.execute("SELECT item.visible, category.name FROM item JOIN category "
                                        "ON item.category_id = category.id").fetchone(), (1, "Uji 'kategori'"))

    def test_rejects_missing_foreign_key_and_duplicate_primary(self):
        self.plan["rows"][0]["values"]["category_id"] = 3
        with self.assertRaisesRegex(ContractError, "Foreign key"):
            self.build()
        self.plan["rows"][0]["values"]["category_id"] = 2
        old = self.plan["rows"][-1]
        self.plan["rows"].append({**old, "id": "other_cat", "values": {"id": 2}})
        with self.assertRaisesRegex(ContractError, "other_cat"):
            self.build()

    def test_rejects_bool_used_as_integer_before_sqlite_can_coerce(self):
        self.plan["rows"][0]["values"]["id"] = True
        with self.assertRaisesRegex(ContractError, "item_one"):
            self.build()
