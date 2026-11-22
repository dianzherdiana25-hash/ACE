"""Verifier pencocokan alias, posisi dan pengecualian salinan snapshot."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import mention_watcher
from ace_web_operator._contracts import identity


class MentionTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        page='<article><p>Élan Studio dan ElanX.</p></article>\n<p hidden>Élan.</p>'.encode()
        data=[("one",page),("two",page),("three",b"<p>Elan does not match the accent.</p>")]
        for key,body in data:
            (self.root/(key+".html")).write_bytes(body)
        self.plan={"schema":"ace.web.mention-plan.v1","source_ref":"fixture/watch",
                   "from":"2026-01-01T00:00:00Z","until":"2026-01-02T00:00:00Z",
                   "tracked":[{"id":"sample","aliases":["Élan","Élan Studio"],"source_ref":"fixture/term"}],
                   "documents":[{"path":key+".html","at":"2026-01-01T01:00:00Z","site":key,
                                 "source_ref":"fixture/"+key,"sha256":sha256(body).hexdigest()} for key,body in data]}

    def scan(self):
        return mention_watcher.scan(self.root,self.plan,identity(self.plan))

    def test_longest_match_is_counted_once_and_duplicate_bytes_do_not_add_mentions(self):
        result=self.scan()
        self.assertEqual(result["counts"],{"sample":1})
        rows={row["site"]:row for row in result["documents"]}
        self.assertEqual(rows["one"]["mentions"][0]["alias"],"Élan Studio")
        self.assertEqual(rows["two"]["duplicate_of"],"one.html")
        self.assertEqual(rows["three"]["mentions"],[])

    def test_window_excludes_record_without_reading_source(self):
        self.plan["documents"][-1]["at"]="2026-02-01T00:00:00Z"
        (self.root/"three.html").unlink()
        self.assertEqual(self.scan()["outside_window"],1)
