"""Verifier SQL DDL dengan constraints dalam SQLite murni fixture."""
import sqlite3
import unittest

from ace_software_factory import schema_designer as model


def column(name,kind="integer",nullable=False,default=None):
    return {"name":name,"kind":kind,"nullable":nullable,"default":default}


def entity(name,cols,**changes):
    base={"name":name,"source_ref":f"fixture/{name}","columns":cols,"primary_key":["id"],"unique":[],
          "foreign_keys":[],"indexes":[]}
    return {**base,**changes}


def repository():
    return {"schema":"ace.factory-relational-model.v1","model_ref":"fixture/schema","entities":[
        entity("category",[column("id"),column("name","text",default={"literal":"fixture's label"})],unique=[["name"]]),
        entity("item",[column("id"),column("category_id",nullable=True),column("visible","boolean",default={"literal":True})],
               foreign_keys=[{"columns":["category_id"],"target":"category","target_columns":["id"],"on_delete":"set_null"}],
               indexes=[["category_id"]]),
    ]}


class SchemaTests(unittest.TestCase):
    def test_sqlite_enforces_boolean_and_foreign_key_and_preserves_literal(self):
        result=model.design(repository())
        with sqlite3.connect(":memory:") as db:
            db.executescript(result["sql"])
            db.execute("INSERT INTO category(id) VALUES (1)")
            self.assertEqual(db.execute("SELECT name FROM category").fetchone(),("fixture's label",))
            db.execute("INSERT INTO item(id,category_id) VALUES (10,1)")
            self.assertEqual(db.execute("SELECT visible FROM item").fetchone(),(1,))
            for query in ("INSERT INTO item VALUES (12,1,7)","INSERT INTO item VALUES (12,99,1)"):
                with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError):
                    db.execute(query)
            db.execute("DELETE FROM category WHERE id=1")
            self.assertEqual(db.execute("SELECT category_id FROM item").fetchone(),(None,))
            self.assertEqual(len(db.execute("PRAGMA index_list(item)").fetchall()),1)
        self.assertEqual(result["entities"][1]["foreign_keys"][0]["on_delete"],"set_null")

    def test_foreign_rules_and_nullable_primary_rejected(self):
        raw=repository()
        raw["entities"][1]["columns"][1]["nullable"]=False
        with self.assertRaisesRegex(model.ContractError,"SET NULL"):
            model.design(raw)
        raw=repository()
        raw["entities"][1]["foreign_keys"][0]["target_columns"]=["not_registered"]
        with self.assertRaisesRegex(model.ContractError,"tidak dikenal"):
            model.design(raw)
        raw=repository()
        raw["entities"][0]["columns"][0]["nullable"]=True
        with self.assertRaisesRegex(model.ContractError,"primer"):
            model.design(raw)
