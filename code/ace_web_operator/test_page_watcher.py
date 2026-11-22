"""Verifier perubahan blok, noise diabaikan, dan snapshot berurutan."""
from hashlib import sha256
import unittest

from ace_web_operator import page_watcher
from ace_web_operator._contracts import ContractError,identity


def recipe(before,after):
    entry=lambda name,payload,when:{"artifact_ref":f"fixture/{name}.html","sha256":sha256(payload).hexdigest(),"at":when}
    return {"schema":"ace.web.page-watch-plan.v1","source_ref":"fixture/watch","site":"updates",
            "ignore_blocks":["clock"],"before":entry("before",before,"2026-11-20T12:00:00Z"),
            "after":entry("after",after,"2026-11-20T12:01:00Z")}


class WatchTests(unittest.TestCase):
    def compare(self,before,after):
        raw=recipe(before,after)
        return page_watcher.compare(raw,identity(raw),before,after)

    def test_tracked_changed_removed_added_with_location(self):
        before=b'<p data-watch="label">awal</p>\n<p data-watch="missing">gone</p>'
        after=b'<p data-watch="label">akhir</p>\n<p data-watch="new">new</p>'
        result=self.compare(before,after)
        self.assertEqual(result["status"],"changed")
        self.assertEqual({row["id"]:row["change"] for row in result["changes"]},
                         {"label":"changed","missing":"removed","new":"added"})
        self.assertEqual(result["changes"][1]["before"]["line"],2)

    def test_ignores_declared_clock_even_with_changed_bytes(self):
        before=b'<p data-watch="clock">a</p><p data-watch="label">Text   here</p>'
        after=b'<p data-watch="clock">b</p><p data-watch="label">Text here</p>'
        result=self.compare(before,after)
        self.assertEqual(result["status"],"only_untracked_bytes_changed")
        self.assertEqual(result["changes"],[])
        raw=recipe(before,after)
        with self.assertRaisesRegex(ContractError,"anchor|manifest"):
            page_watcher.compare(raw,identity(raw),before,after+b"x")
