"""Verifier arsip hash, byte identik, dan respons salah dari situs lokal."""
from hashlib import sha256
from io import BytesIO
import unittest
from zipfile import ZipFile

from ace_web_operator import web_archiver
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import HTML,fixture


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        host=fixture(self)
        self.plan={"schema":"ace.web.archive-plan.v1","origin":f"http://127.0.0.1:{host.server_port}",
                   "source_ref":"fixture/archive","permission_ref":"fixture/owner-permission",
                   "sources":[{"path":path,"media_type":"text/html","sha256":sha256(HTML).hexdigest(),
                               "bytes":len(HTML),"source_ref":"fixture/read"} for path in ("/","/mirror")]}

    def capture(self):
        return web_archiver.capture(self.plan,identity(self.plan))

    def test_real_capture_two_paths_share_object_and_verify_reproducibly(self):
        data,report=self.capture()
        self.assertEqual(data,self.capture()[0])
        self.assertEqual((report["sources"],report["objects"]),(2,1))
        checked=web_archiver.verify(data,report["manifest_sha256"])
        self.assertEqual((checked["sources"],checked["status"]),(2,"verified"))

    def test_rejects_bad_expected_value_and_existing_archive_byte_edit(self):
        data,report=self.capture()
        target=BytesIO()
        with ZipFile(BytesIO(data)) as valid,ZipFile(target,"w") as changed:
            for member in valid.namelist():
                payload=valid.read(member) if member==web_archiver.MANIFEST else b"x"*len(HTML)
                changed.writestr(web_archiver._member(member),payload)
        with self.assertRaisesRegex(ContractError,"Objek rusak"):
            web_archiver.verify(target.getvalue(),report["manifest_sha256"])
        self.plan["sources"][0]["sha256"]="0"*64
        with self.assertRaisesRegex(ContractError,"Capture tidak cocok"):
            self.capture()
