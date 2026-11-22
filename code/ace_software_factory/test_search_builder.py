"""Verifier FTS asli dengan pencarian Unicode, peringkat dan tampering."""
import unittest

from ace_software_factory import search_builder
from ace_software_factory._contracts import ContractError, identity


class SearchTests(unittest.TestCase):
    def setUp(self):
        docs = [{"id": key, "title": title, "body": body, "group": group,
                 "source_ref": f"fixture/docs/{key}"}
                for key,title,body,group in [("one","Pantai dan pasir","Ombak pantai tenang dekat pasir.","travel"),
                                             ("two","Kebun","Pasir kebun menjaga kadar air.","garden"),
                                             ("three","Kafé","Pengunjung mencari minuman.","travel")]]
        source = {"schema": "ace.factory-search-snapshot.v1", "source_ref": "fixture/docs", "documents": docs}
        plan = {"schema": "ace.factory-search-plan.v1", "collection_id": "fixture_terms",
                "snapshot_sha256": identity(source), "source_ref": "fixture/index", "title_weight": 3}
        self.index,self.report = search_builder.build(source,plan,identity(plan))
        self.anchor = self.report["index_sha256"]

    def test_query_all_any_and_escaped_operator_words(self):
        route = lambda words,**params: [row["doc_id"] for row in
                                       search_builder.query(self.index,self.anchor,words,**params)["results"]]
        self.assertEqual(route("pantai pasir"), ["one"])
        self.assertEqual(route("pantai kebun",mode="any"), ["two","one"])
        self.assertEqual(route("pantai OR kebun"), [])
        self.assertEqual(route("pasir",mode="any",group="garden"), ["two"])
        self.assertEqual(route("kafe"), ["three"])

    def test_hits_have_source_and_verification_refuses_wrong_bytes(self):
        result = search_builder.query(self.index,self.anchor,"ombak")
        self.assertEqual(result["results"][0]["source_ref"],"fixture/docs/one")
        self.assertIn("[Ombak]",result["results"][0]["snippet"])
        self.assertEqual(result["snapshot_sha256"],self.report["snapshot_sha256"])
        with self.assertRaisesRegex(ContractError,"anchor"):
            search_builder.query(self.index+b"x",self.anchor,"ombak")
