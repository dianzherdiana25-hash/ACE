"""Verifier download tervalidasi, resume dan penolakan lisensi fixture."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import bulk_downloader
from ace_web_operator._artifact import write_new
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator._http import Observation


class BulkTests(unittest.TestCase):
    def setUp(self):
        self.payload=b"x,y\n2,3\n"
        self.root=Path(self.enterContext(TemporaryDirectory()))/"snapshot"
        self.plan={"schema":"ace.web.bulk-download-plan.v1","source_ref":"fixture/plan","access_ref":"fixture/approval",
                   "origin":"http://127.0.0.1:9010","max_total_bytes":500,
                   "datasets":[{"id":name,"path":"/"+name,"bytes":len(self.payload),"sha256":sha256(self.payload).hexdigest(),
                                "media_type":"text/csv","license":"CC0-1.0","license_ref":"fixture/license",
                                "source_ref":"fixture/pages/"+name} for name in ("alpha","beta")]}

    def pull(self,transport,**kwargs):
        return bulk_downloader.download(self.plan,identity(self.plan),transport=transport,**kwargs)

    def test_duplicate_objects_and_verified_resume_avoid_requests(self):
        calls=[]
        def fetch(base,path,cap):
            calls.append(path)
            return Observation(200,"text/csv",self.payload,None)
        files,report=self.pull(fetch)
        self.assertEqual(calls,["/alpha"])
        self.assertEqual([row["status"] for row in report["records"]],["downloaded","deduplicated"])
        write_new(self.root,files)
        _,report=self.pull(lambda *args,**kwargs:self.fail("no download"),resume=self.root)
        self.assertEqual([row["status"] for row in report["records"]],["resumed","deduplicated"])

    def test_wrong_byte_or_license_cannot_be_emitted(self):
        files,report=self.pull(lambda *args,**kwargs:Observation(200,"text/csv",b"x,y\n9,9\n",None))
        self.assertEqual(set(files),{"download_receipt.json"})
        self.assertEqual(report["held"],2)
        self.plan["datasets"][0]["license"]="private"
        with self.assertRaisesRegex(ContractError,"lisensi"):
            self.pull(lambda *args,**kwargs:self.fail("no download"))
