"""Verifier bentuk data, rujukan baris dan duplikat dari HTML fixture."""
from hashlib import sha256
import unittest

from ace_web_operator import page_extractor
from ace_web_operator._contracts import ContractError,identity


PAGE=b'''<!doctype html>
<div class="stock before"><span data-field="key">one</span><span data-field="qty">3</span><a data-field="link" href="/items/one">Lihat</a></div>
<div class="stock"><span data-field="key">one</span><span data-field="qty">3 pcs</span></div>
<div class="unlisted"><span data-field="key">ignored</span></div>'''


def recipe(html):
    return {"schema":"ace.web.extract-plan.v1","source_ref":"fixture/schema","html_ref":"fixture/site.html",
            "html_sha256":sha256(html).hexdigest(),"row_tag":"div","row_class":"stock","primary":"id",
            "fields":[{"name":key,"marker":marker,"type":kind,"from":slot,"required":required,"source_ref":f"fixture/{key}"}
                      for key,marker,kind,slot,required in (
                          ("id","key","text","text",True),("amount","qty","integer","text",True),
                          ("record_path","link","path","href",False))]}


class PageTests(unittest.TestCase):
    def test_extracts_anchored_values_and_marks_duplicate_or_malformed_rows(self):
        raw=recipe(PAGE)
        report=page_extractor.extract(PAGE,raw,identity(raw))
        self.assertEqual((report["records"],report["valid"],report["status"]),(2,1,"partial"))
        first,second=report["rows"]
        self.assertEqual(first["values"],{"id":"one","amount":3,"record_path":"/items/one"})
        self.assertEqual(second["values"]["amount"],None)
        self.assertEqual(second["findings"],[{"field":"amount","line":3,"code":"invalid_field","source_ref":"fixture/amount"},
                                             {"field":"id","line":3,"code":"duplicate_primary","first_line":2}])

    def test_refuses_source_mismatch_and_does_not_invent_empty_catalog(self):
        raw=recipe(PAGE)
        with self.assertRaisesRegex(ContractError,"anchor"):
            page_extractor.extract(PAGE+b"x",raw,identity(raw))
        blank=b"<title>No records</title>"
        raw=recipe(blank)
        self.assertEqual(page_extractor.extract(blank,raw,identity(raw))["status"],"empty")
