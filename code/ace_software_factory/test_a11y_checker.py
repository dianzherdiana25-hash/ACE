"""Verifier label, heading, gambar, dan target interaksi HTML."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import a11y_checker
from ace_software_factory._contracts import identity
from ace_software_factory.repo_scaffolder import materialize


class AccessibilityTests(unittest.TestCase):
    def scan(self,source):
        root=Path(self.enterContext(TemporaryDirectory()))/"source"
        materialize(root,{"index.html":source})
        plan={"schema":"ace.factory-a11y-plan.v1","source_ref":"fixture/markup",
              "pages":[{"path":"index.html","sha256":sha256(source).hexdigest()}]}
        return a11y_checker.inspect(root,plan,identity(plan))

    def test_clean_fixture_with_label_multiple_forms_and_decorative_alt(self):
        report=self.scan(b'''<html lang="id"><head><title>Fixture</title></head><body>
<main><h1>Daftar</h1><h2>Masukan</h2>
<label for="tool">Alat</label><input id="tool">
<label>Isi detail<textarea></textarea></label><button>Simpan</button>
<a href="/faq"><img alt="FAQ" src="faq.png"></a><img alt="" src="decoration.png">
</main></body></html>''')
        self.assertEqual(report["status"],"no_rule_matches")

    def test_reports_locators_for_unlabeled_image_and_inaccessible_interactions(self):
        markup=b'''<html><head><title>Fixture</title></head><body>
<main><h1>Daftar</h1><h3>Loncat</h3>
<label for="different">Alat</label><input id="tool">
<img><button aria-labelledby="no_key"></button>
<div onclick="local()" tabindex="2">Tindakan</div>
</main></body></html>'''
        report=self.scan(markup)
        rows=report["pages"][0]["findings"]
        self.assertEqual({row["rule"] for row in rows},{
            "document_language_missing","heading_jump","label_target_missing","control_label_missing",
            "image_alt_missing","interactive_name_missing","aria_reference_missing",
            "positive_tabindex","nonsemantic_click_target"})
        self.assertEqual(next(row["line"] for row in rows if row["rule"]=="image_alt_missing"),4)
