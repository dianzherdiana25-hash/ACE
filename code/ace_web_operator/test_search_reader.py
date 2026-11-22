"""Verifier rangking, ekstrak snippet dan URL yang dideduplikasi."""
from hashlib import sha256
import unittest

from ace_web_operator import search_reader
from ace_web_operator._contracts import identity


class SearchTests(unittest.TestCase):
    def extract(self,data):
        plan={"schema":"ace.web.search-reader-plan.v1","source_ref":"fixture/config","snapshot_ref":"fixture/results.html",
              "query":"catatan","snapshot_sha256":sha256(data).hexdigest(),"max_results":4,"max_chars":50}
        return search_reader.extract(data,plan,identity(plan))

    def test_block_summary_preserves_citations_and_case_normalized_urls(self):
        html=b'''<li data-search-result="true"><a data-role="title" href="https://Docs.Invalid:443/note#a">Judul</a>
<p data-role="snippet">Bukti <b>yang</b> dibaca.</p></li>
<li data-search-result="true"><a data-role="title" href="https://docs.invalid/note">Salinan</a></li>
<li data-search-result="true"><a data-role="title" href="javascript:skip">Unknown</a></li>'''
        result=self.extract(html)
        self.assertEqual([row["url"] for row in result["results"]],["https://docs.invalid/note"])
        self.assertEqual(result["brief"][0]["excerpt"],"Bukti yang dibaca.")
        self.assertEqual(result["brief"][0]["source_ref"],"fixture/results.html")
        self.assertEqual([row["reason"] for row in result["findings"]],["duplicate","invalid_address"])

    def test_no_snippet_does_not_generate_summary(self):
        html=b'<li data-search-result="true"><a data-role="title" href="https://docs.invalid/">Entry</a></li>'
        result=self.extract(html)
        self.assertEqual(result["brief"],[])
        self.assertIsNone(result["results"][0]["excerpt"])
