"""Verifier perubahan klausul penting dengan pointer dan jendela revisi."""
from hashlib import sha256
import unittest

from ace_web_operator import tos_watcher
from ace_web_operator._contracts import ContractError,identity


class TermsTests(unittest.TestCase):
    def compare(self,before,after):
        plan={"schema":"ace.web.tos-watch-plan.v1","site":"fixture","source_ref":"fixture/registry"}
        for key,day,data in (("before",1,before),("after",2,after)):
            plan[key]={"sha256":sha256(data).hexdigest(),"at":f"2026-01-0{day}T00:00:00Z","ref":"fixture/"+key}
        return tos_watcher.compare(plan,identity(plan),before,after)

    def test_changed_and_removed_annotated_clauses_are_labeled(self):
        before=b'<p data-term-id="data" data-term-class="retention">Simpan selama tiga bulan.</p><p data-term-id="other" data-term-class="general">Berlaku.</p>'
        after=b'<p data-term-id="data" data-term-class="retention">Simpan selama empat bulan.</p>'
        report=self.compare(before,after)
        self.assertEqual([row["status"] for row in report["changes"]],["text_changed","removed"])
        changed=report["changes"][0]
        self.assertEqual(changed["word_delta"],{"added_words":1,"removed_words":1})
        self.assertTrue(changed["review_required"])
        self.assertEqual(changed["before"]["source_ref"],"fixture/before")

    def test_different_markup_can_keep_clause_equivalent(self):
        first=b'<p data-term-id="rule" data-term-class="general">Satu dua</p>'
        second=b'<section data-term-id="rule" data-term-class="general">Satu <em>dua</em></section>'
        self.assertEqual(self.compare(first,second)["status"],"unchanged_in_scope")
        with self.assertRaisesRegex(ContractError,"ganda"):
            self.compare(first,first+first)
