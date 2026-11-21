"""Verifier struktur halaman, CTA terdaftar dan rujukan manfaat."""
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import landing_builder
from ace_software_factory._contracts import ContractError, identity


class Markup(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.elements = []
        self.feed(page.decode())

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class LandingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.plan = {"schema": "ace.factory-landing-plan.v1", "id": "catalog_local", "lang": "id",
                     "name": "Katalog lokal", "headline": "Kerja <tertata>",
                     "summary": 'Simpan "rekap" lokal.', "source_ref": "fixture/pitch", "accent": "#143646",
                     "benefits": [{"id": "export", "title": "Ekspor", "description": "<img src=x> sebagai teks.",
                                   "source_ref": "fixture/spec/0"}],
                     "cta": {"label": "Mulai", "target": "/guide/setup", "source_ref": "fixture/spec/1"},
                     "routes": ["/guide/setup"], "hero": None}

    def build(self):
        return landing_builder.build(self.root, self.plan, identity(self.plan))

    def test_static_semantic_structure_and_escaping(self):
        files, report = self.build()
        parsed = Markup(files["index.html"])
        tags = [tag for tag, _ in parsed.elements]
        self.assertEqual(tags.count("h1"), 1)
        self.assertIn(("html", {"lang": "id"}), parsed.elements)
        self.assertIn(("a", {"class": "primary", "href": "/guide/setup"}), parsed.elements)
        self.assertNotIn("img", tags)
        self.assertNotIn("script", tags)
        self.assertIn(b"&lt;img src=x&gt;", files["index.html"])
        self.assertEqual(report["benefits"][0]["source_ref"], "fixture/spec/0")

    def test_requires_contrast_and_ref_declared_before_link_generation(self):
        self.plan["accent"] = "#efefef"
        with self.assertRaisesRegex(ContractError, "kontras"):
            self.build()
        self.plan["accent"] = "#123456"
        self.plan["cta"]["target"] = "//unknown.invalid/"
        with self.assertRaisesRegex(ContractError, "terdaftar"):
            self.build()
