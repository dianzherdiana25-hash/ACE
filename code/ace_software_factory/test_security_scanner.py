"""Verifier perlindungan keluaran dan pola SAST pada produk fixture."""
import unittest

from ace_software_factory import security_scanner
from ace_software_factory._contracts import canonical, identity
from ace_software_factory.test_self_reviewer import fixture


class ScannerTests(unittest.TestCase):
    def test_reports_source_coordinates_and_never_outputs_fixture_values(self):
        data = b'''from subprocess import run as launch
from hashlib import sha1 as old_digest
import ssl as layer
def check(cur, source):
    credential_note = {"api_key": "fixture-canary-text"}
    another_password: str = "fixture-value-never-in-report"
    cur.execute("SELECT data FROM fixture WHERE id=" + source)
    launch(["/usr/bin/true"], shell=True)
    old_digest(b"local-fixture")
    layer._create_unverified_context()
'''
        root, manifest = fixture(self, {"module.py": data})
        report = security_scanner.scan(root, manifest, identity(manifest))
        self.assertEqual(report["status"], "review_required")
        self.assertEqual([(row["line"], row["rule"]) for row in report["findings"]],
                         [(5, "credential_literal"), (6, "credential_literal"), (7, "interpolated_sql"),
                          (8, "shell_enabled"), (9, "legacy_digest"), (10, "unverified_tls_context")])
        for candidate in (b"fixture-canary-text", b"fixture-value-never-in-report"):
            self.assertNotIn(candidate, canonical(report))

    def test_parameter_binding_and_secret_from_environment_not_flagged(self):
        data = b'''import os
import subprocess
def get(cur):
    password = os.environ.get("APP_PASSWORD")
    cur.execute("SELECT ? AS tag", (password,))
    subprocess.run(["/usr/bin/true"], shell=False, check=True)
'''
        root, manifest = fixture(self, {"module.py": data})
        result = security_scanner.scan(root, manifest, identity(manifest))
        self.assertEqual(result["status"], "no_rule_matches")
        self.assertEqual(result["findings"], [])

    def test_parse_failures_prevent_no_matches_verdict(self):
        root, manifest = fixture(self, {"module.py": b"def missing("})
        report = security_scanner.scan(root, manifest, identity(manifest))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["unscanned"][0]["line"], 1)
