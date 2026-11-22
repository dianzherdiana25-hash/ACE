"""Verifier CAS revisi, produk retired tanpa hapus dan hasil kanonis."""
import unittest

from ace_web_operator import catalog_manager
from ace_web_operator._contracts import ContractError,identity


def item(key):
    return {"sku":key,"name":"Unit "+key,"category":"fixture","stock":2,"price_minor":8,
            "status":"active","retire_ref":None,"source_ref":"fixture/"+key}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.raw={"schema":"ace.web.catalog-snapshot.v1","source_ref":"fixture/old","shop":"demo",
                  "currency":"IDR","revision":2,"categories":["fixture"],"items":[item("old")]}
        self.delta={"schema":"ace.web.catalog-delta.v1","source_ref":"fixture/revision","shop":"demo",
                    "base_sha256":identity(self.raw),"changes":[
                        {"operation":"retire","sku":"old","expected_sha256":identity(item("old")),
                         "product":None,"source_ref":"fixture/retire"},
                        {"operation":"upsert","sku":"new","expected_sha256":None,
                         "product":item("new"),"source_ref":"fixture/new"}]}

    def step(self):
        return catalog_manager.revise(self.raw,self.delta,identity(self.delta))

    def test_snapshot_keeps_retired_record_and_reports_hashes(self):
        output,receipt=self.step()
        self.assertEqual(self.raw["items"][0]["status"],"active")
        self.assertEqual(output["revision"],3)
        self.assertEqual([row["sku"] for row in output["items"]],["new","old"])
        self.assertEqual(output["items"][1]["retire_ref"],"fixture/retire")
        self.assertEqual(receipt["after_sha256"],identity(output))
        self.assertEqual((output,receipt),self.step())

    def test_failed_preimage_prevents_any_delta(self):
        self.delta["changes"][0]["expected_sha256"]="0"*64
        with self.assertRaisesRegex(ContractError,"Versi"):
            self.step()
        self.assertEqual(len(self.raw["items"]),1)
