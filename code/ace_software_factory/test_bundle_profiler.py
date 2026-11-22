"""Verifier ukuran, graph aset dan perbedaan resource lokal/asing."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import bundle_profiler
from ace_software_factory._contracts import identity
from ace_software_factory.repo_scaffolder import materialize


class BundleTests(unittest.TestCase):
    def profile(self,missing=False):
        files={"index.html":b'<link rel="stylesheet" href="style.css"><script src="main.mjs"></script>',
               "main.mjs":b'export {a} from "./extra.mjs";',
               "style.css":b'body{background:url("img.png")}\n'*70,
               "img.png":b"asset bytes", "extra.mjs":b"export const a=3;", "orphan.js":b"unused"}
        if missing:
            files.pop("img.png")
        root=Path(self.enterContext(TemporaryDirectory()))/"source"
        materialize(root,files)
        raw={"schema":"ace.factory-bundle-plan.v1","entry":"index.html","source_ref":"fixture/bundle",
             "bandwidth_bps":100_000,"latency_ms":50,"max_bytes":3000,
             "files":[{"path":key,"sha256":sha256(body).hexdigest()} for key,body in files.items()]}
        return bundle_profiler.profile(root,raw,identity(raw)),files

    def test_provenance_graph_and_estimated_ms_match_formula(self):
        report,files=self.profile()
        self.assertEqual(report["graph"]["style.css"],["img.png"])
        self.assertEqual(report["graph"]["main.mjs"],["extra.mjs"])
        self.assertEqual(report["unreferenced"],["orphan.js"])
        self.assertEqual(report["raw_bytes"],sum(len(data) for key,data in files.items() if key!="orphan.js"))
        transfer=report["estimated_transfer_bytes"]
        self.assertEqual(report["transfer_lower_ms"],(transfer*8000+99_999)//100_000+50)
        self.assertLess(transfer,report["raw_bytes"])

    def test_missing_asset_is_never_estimated_as_complete(self):
        report,_=self.profile(missing=True)
        self.assertEqual(report["status"],"incomplete")
        self.assertEqual(report["findings"],[{"code":"missing_dependency","from":"style.css","reference":"img.png"}])
