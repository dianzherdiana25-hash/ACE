"""Verifier salinan migrasi, rollback input tak cocok, dan preservasi row."""
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import sqlite3
import unittest

from ace_software_factory import migration_builder, schema_designer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.test_schema_designer import column, entity, repository


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.old = repository()
        self.new = deepcopy(self.old)
        self.new["entities"][0]["columns"].append(column("active", "boolean", default={"literal": True}))
        self.new["entities"].append(entity("settings", [column("id"),column("raw", "blob", True)]))
        with closing(sqlite3.connect(":memory:")) as source:
            source.executescript(schema_designer.design(self.old)["sql"])
            source.execute("INSERT INTO category (id,name) VALUES (?,?)",(3,"'kotak'"))
            source.execute("INSERT INTO item (id,category_id,visible) VALUES (4,3,0)")
            source.commit()
            self.snapshot = source.serialize()

    def run_migration(self):
        plan = {"schema": "ace.factory-additive-migration.v1", "source_ref": "fixture/migration",
                "source_sha256": sha256(self.snapshot).hexdigest(), "old_model_sha256": identity(self.old),
                "new_model_sha256": identity(self.new)}
        return migration_builder.migrate(self.snapshot, self.old, self.new, plan, identity(plan))

    def test_migrates_rows_and_foreign_keys_with_default_and_new_table(self):
        migrated, report = self.run_migration()
        self.assertEqual(report["status"],"verified")
        self.assertEqual(report["changes"]["tables"],["settings"])
        self.assertEqual(report["changes"]["existing_tables"]["category"]["columns"],["active"])
        for table in report["row_checks"]:
            self.assertEqual((table["rows"],table["old_sha256"]),(1,table["new_sha256"]))
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(migrated)
            self.assertEqual(db.execute("select id,name,active from category").fetchone(),(3,"'kotak'",1))
            self.assertEqual(db.execute("select visible from item").fetchone(),(0,))
            self.assertFalse(db.execute("PRAGMA foreign_key_check").fetchall())

    def test_refuses_constraint_rewrites_or_wrong_source_layout(self):
        self.new["entities"][0]["unique"] = []
        with self.assertRaisesRegex(ContractError,"Constraint"):
            self.run_migration()
        self.new = deepcopy(self.old)
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(self.snapshot)
            db.execute("CREATE TABLE unexpected (id INTEGER)")
            self.snapshot = db.serialize()
        with self.assertRaisesRegex(ContractError,"Layout"):
            self.run_migration()
