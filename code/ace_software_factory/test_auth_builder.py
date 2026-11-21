"""Jalankan runtime yang dihasilkan dengan akun sementara dan waktu injeksi."""
import importlib.util
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from ace_software_factory import auth_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": "ace.factory-auth-plan.v1", "id": "fixture", "session_seconds": 30,
                     "iterations": 120_000, "max_accounts": 2, "max_sessions": 2,
                     "permissions": [{"id": key, "source_ref": f"fixture/policy/{key}"} for key in ("read", "edit")],
                     "roles": [{"id": "reader", "permissions": ["read"], "source_ref": "fixture/reader"},
                               {"id": "editor", "permissions": ["edit", "read"], "source_ref": "fixture/editor"}]}
        self.root = Path(self.enterContext(TemporaryDirectory())) / "example"
        files, report = auth_builder.build(self.plan, identity(self.plan))
        materialize(self.root, files)
        path = self.root / report["runtime"]["path"]
        spec = importlib.util.spec_from_file_location("fixture_generated_product_auth", path)
        module = importlib.util.module_from_spec(spec)
        self.enterContext(patch.dict(sys.modules, {spec.name: module}))
        spec.loader.exec_module(module)
        self.now = 100
        self.login = module.Login(clock=lambda: self.now)
        self.password = secrets.token_bytes(24)

    def test_access_default_denied_and_expiry_right_on_boundary(self):
        self.login.enroll("visitor", self.password, "reader")
        self.assertIsNone(self.login.login("unknown", self.password))
        self.assertIsNone(self.login.login("visitor", secrets.token_bytes(24)))
        token = self.login.login("visitor", self.password)
        self.assertTrue(self.login.permits(token, "read"))
        self.assertFalse(self.login.permits(token, "edit"))
        self.assertFalse(self.login.permits(token, "unlisted"))
        self.now += 30
        self.assertFalse(self.login.permits(token, "read"))

    def test_password_change_revokes_existing_sessions(self):
        self.login.enroll("operator", self.password, "editor")
        token = self.login.login("operator", self.password)
        change = secrets.token_bytes(24)
        self.assertTrue(self.login.permits(token, "edit"))
        self.assertTrue(self.login.change_password("operator", self.password, change))
        self.assertFalse(self.login.permits(token, "edit"))
        self.assertIsNone(self.login.login("operator", self.password))
        token = self.login.login("operator", change)
        self.assertTrue(self.login.revoke(token))
        self.assertFalse(self.login.permits(token, "read"))

    def test_undefined_role_permission_fails_before_emitting(self):
        self.plan["roles"][0]["permissions"] = ["unknown"]
        with self.assertRaisesRegex(ContractError, "permission"):
            auth_builder.build(self.plan, identity(self.plan))
