from hashlib import sha256
from shutil import which
import unittest

from ._contracts import ContractError, identity
from .explainer_maker import explain


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class ExplainerTests(unittest.TestCase):
    def test_short_video_embeds_only_relevant_quotations_with_lineage(self):
        article = b"# Catatan\nCahaya turun saat tirai rapat.\n\nTanaman berbuah pada musim panas.\n\nCahaya masuk lewat kaca.\n"
        plan = {"schema": "ace.media.explainer-plan.v1", "article_sha256": sha256(article).hexdigest(),
                "article_ref": "fixture:article", "title": "CAHAYA", "keywords": ["cahaya"],
                "max_cards": 2, "width": 160, "height": 90, "fps": 3, "frames_per_card": 3}
        movie, receipt = explain(article, plan, identity(plan))
        self.assertEqual(receipt["frames"], 6)
        self.assertEqual(receipt["mp4_sha256"], sha256(movie).hexdigest())
        self.assertEqual([r["lines"] for r in receipt["cards"]], [[2, 2], [6, 6]])
        self.assertTrue(all(r["quote"].encode() in article for r in receipt["cards"]))
        self.assertNotIn("Tanaman", str(receipt))
        plan["keywords"] = ["unknown"]
        with self.assertRaisesRegex(ContractError, "Kartu kutipan"):
            explain(article, plan, identity(plan))
