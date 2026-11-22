"""Verifier fragment, probe 404, dan tautan eksternal tanpa snapshot."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_web_operator import link_validator
from ace_web_operator._contracts import identity


class LinkTests(unittest.TestCase):
    def test_counts_broken_missing_and_unknown_separately(self):
        root=Path(self.enterContext(TemporaryDirectory()))
        page=b'''<h1 id="start">Daftar</h1><a href="#start">Ini</a><a href="#gone">Tak ada</a>
<a href="https://else.invalid/fail">Diuji</a><a href="https://new.invalid/">Belum diuji</a>
<a href="javascript:local()">Salah</a>'''
        (root/"index.html").write_bytes(page)
        probes={"schema":"ace.web.link-probes.v1","entries":[
            {"url":"https://else.invalid/fail","status":404,"source_ref":"fixture/probe","evidence_sha256":"a"*64}]}
        plan={"schema":"ace.web.link-validation-plan.v1","source_ref":"fixture/manifest","probe_sha256":identity(probes),
              "documents":[{"path":"index.html","url":"https://local.invalid/","source_ref":"fixture/main",
                            "sha256":sha256(page).hexdigest()}]}
        result=link_validator.validate(root,plan,identity(plan),probes)
        self.assertEqual(result["counts"],{"broken_response":1,"invalid":1,"missing_fragment":1,
                                           "unobserved_external":1,"verified_snapshot":1})
        self.assertEqual(result["checks"][2]["probe_ref"],"fixture/probe")
