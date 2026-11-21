"""Jalankan CLI hasil pabrik terhadap masukan sah, rusak, dan terlalu besar."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import cli_builder
from ace_software_factory._contracts import ContractError, decode, identity
from ace_software_factory.repo_scaffolder import materialize


def config():
    fields = [{"name": "name", "type": "text"}, {"name": "units", "type": "integer"}]
    return {"schema": "ace.factory-cli-plan.v1", "id": "stock_report", "description": "Ringkasan inventaris.",
            "max_input_bytes": 128, "commands": [
                {"id": "total", "operation": "sum", "help": "Jumlah unit", "fields": fields, "select": ["units"],
                 "source_ref": "fixture/total"},
                {"id": "names", "operation": "project", "help": "Daftar nama", "fields": fields, "select": ["name"],
                 "source_ref": "fixture/name"},
                {"id": "check", "operation": "validate", "help": "Periksa data", "fields": fields, "select": [],
                 "source_ref": "fixture/check"},
            ]}


class CLITests(unittest.TestCase):
    def setUp(self):
        raw = config()
        self.root = Path(self.enterContext(TemporaryDirectory())) / "product"
        files, self.report = cli_builder.build(raw, identity(raw))
        materialize(self.root, files)

    def run_product(self, mode, payload):
        return subprocess.run([sys.executable, "-B", "-m", self.report["product_id"], mode], input=payload,
                              cwd=self.root, capture_output=True, timeout=6)

    def test_generated_project_and_total_read_real_stdin(self):
        data = '[{"name":"paku","units":9},{"name":"kaca","units":-2}]'.encode()
        result = self.run_product("total", data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decode(result.stdout), {"records": 2, "total": 7})
        result = self.run_product("names", data)
        self.assertEqual(decode(result.stdout), [{"name": "paku"}, {"name": "kaca"}])
        self.assertEqual([row["id"] for row in self.report["commands"]], ["check", "names", "total"])

    def test_check_marks_bool_as_wrong_integer_and_rejects_ambiguous_json(self):
        result = self.run_product("check", b'[{"name":"paku","units":true},{"name":"kaca","units":2}]')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(decode(result.stdout), {"records": 2, "valid": 1, "rejected_indices": [0]})
        for value in (b'[{"name":"paku","units":1,"units":2}]', b"[" + b" " * 128 + b"]"):
            with self.subTest(value=value):
                result = self.run_product("total", value)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")

    def test_rejects_a_noninteger_operand_before_generating_files(self):
        raw = config()
        raw["commands"][0]["select"] = ["name"]
        with self.assertRaisesRegex(ContractError, "operasi"):
            cli_builder.build(raw, identity(raw))
