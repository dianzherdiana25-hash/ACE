"""Verifier dokumentasi dari kontrak yang juga dipakai backend hasil build."""
import unittest

from ace_software_factory import api_builder, api_docs_builder
from ace_software_factory._contracts import ContractError, decode, identity
from ace_software_factory.test_api_builder import settings
from ace_software_factory.test_schema_designer import repository


class ApiDocsTests(unittest.TestCase):
    def setUp(self):
        source=repository()
        plan=settings(source)
        files,_=api_builder.build(source,plan,identity(plan))
        self.contract=decode(files["api.json"])

    def test_exposes_existing_route_methods_and_accurate_schema_without_remote_script(self):
        files,report=api_docs_builder.build(self.contract,identity(self.contract),"Dokumen <lokal>","1.0")
        docs=decode(files["openapi.json"])
        self.assertEqual(docs["openapi"],"3.1.0")
        self.assertEqual(set(docs["paths"]["/categories/{id}"]),{"get","patch","delete"})
        self.assertEqual(set(docs["paths"]["/items/{id}"]),{"get"})
        request=docs["paths"]["/items"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertEqual(request["properties"]["visible"],{"type":"boolean"})
        self.assertEqual(request["properties"]["category_id"],{"type":["integer","null"]})
        self.assertIn(b'<form data-route="/categories">',files["index.html"])
        self.assertIn(b"Dokumen &lt;lokal&gt;",files["index.html"])
        self.assertNotIn(b"http:",files["index.html"])
        self.assertEqual(report["operations"],8)

    def test_tampered_api_anchor_is_rejected(self):
        with self.assertRaisesRegex(ContractError,"anchor"):
            api_docs_builder.build(self.contract,"0"*64,"Dokumen","1.0")
