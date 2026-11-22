"""Uji capture PNG Chromium dan penolakan sebelum screenshot."""
from hashlib import sha256
import unittest

from ace_web_operator import evidence_shooter
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available,fixture,plan


class ScreenshotTests(unittest.TestCase):
    def test_real_local_capture_contains_png_dimensions_and_hash(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        profile=plan(http.server_port)
        raw={"schema":"ace.web.screenshot-plan.v1","source_ref":"fixture/capture","capture_ref":"fixture/out.png",
             "path":"/","test_id":"name","assertion":{"test_id":"out","expected":"Awal"},
             "browser":{key:profile[key] for key in ("origin","allow_paths","timeout_ms","request_limit")}}
        data,result=evidence_shooter.shoot(raw,identity(raw))
        self.assertEqual(result["status"],"captured",result)
        self.assertEqual(result["png"]["sha256"],sha256(data).hexdigest())
        self.assertGreater(result["png"]["width"],0)
        self.assertNotIn("png_base64",str(result))
        raw["assertion"]["expected"]="Tidak ada"
        data,result=evidence_shooter.shoot(raw,identity(raw))
        self.assertIsNone(data)
        self.assertEqual(result["reason"],"assertion_failed")

    def test_malformed_image_refuses_receipt(self):
        with self.assertRaisesRegex(ContractError,"PNG"):
            evidence_shooter.inspect_png({"png_base64":"dGVzdA==","bytes":35,"sha256":"a"*64})
