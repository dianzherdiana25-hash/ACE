"""Verifier izin yang diperiksa saat render dan saat dispatch aksi."""
import importlib.util
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from ace_software_factory import admin_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": "ace.factory-admin-plan.v1", "id": "inventory", "source_ref": "fixture/admin",
                     "views": [{"id": "items", "title": "Barang", "key": "id", "permission": "read_items",
                                "columns": [{"id": "id", "label": "ID"}, {"id": "name", "label": "Nama"}],
                                "actions": [{"id": "freeze", "label": "Bekukan", "permission": "edit_items",
                                             "route": "/admin/items/freeze", "source_ref": "fixture/action"}],
                                "source_ref": "fixture/view"}]}
        root = Path(self.enterContext(TemporaryDirectory())) / "fixture"
        files, report = admin_builder.build(self.plan, identity(self.plan))
        materialize(root, files)
        spec = importlib.util.spec_from_file_location("generated_admin_fixture", root / report["runtime"]["path"])
        self.runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runtime)
        self.allowed = {"owner": {"read_items", "edit_items"}, "observer": {"read_items"}}
        self.session = self.runtime.Panel(lambda token, permission: permission in self.allowed.get(token, ()))
        self.nonce = secrets.token_urlsafe(24)

    def test_render_filters_data_and_actions_per_permission(self):
        rows = [{"id": "i10", "name": "<uji>", "private": "hidden-fixture-value"}]
        owner = self.session.render("items", "owner", rows, self.nonce)
        reader = self.session.render("items", "observer", rows, self.nonce)
        self.assertIn("/admin/items/freeze", owner)
        self.assertNotIn("/admin/items/freeze", reader)
        self.assertIn("&lt;uji&gt;", reader)
        self.assertNotIn("hidden-fixture-value", owner)
        with self.assertRaises(PermissionError):
            self.session.render("items", "unknown", rows, self.nonce)

    def test_callback_untouched_on_csrf_or_permission_failure(self):
        handler = Mock(return_value={"changed": "i10"})
        for token, nonce in (("observer", self.nonce), ("owner", secrets.token_urlsafe(24))):
            with self.subTest(token=token), self.assertRaises(PermissionError):
                self.session.dispatch("items", "freeze", token, "i10", nonce, self.nonce, handler)
        handler.assert_not_called()
        self.assertEqual(self.session.dispatch("items", "freeze", "owner", "i10", self.nonce, self.nonce, handler),
                         {"changed": "i10"})
        handler.assert_called_once_with("items", "freeze", "i10")

    def test_does_not_generate_offsite_action_route(self):
        self.plan["views"][0]["actions"][0]["route"] = "//outside.invalid/"
        with self.assertRaises(ContractError):
            admin_builder.build(self.plan, identity(self.plan))
