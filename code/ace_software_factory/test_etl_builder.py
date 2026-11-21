"""Periksa ETL yang dihasilkan sebagai proses, beserta keluaran dan receipt."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import etl_builder
from ace_software_factory._contracts import decode, identity
from ace_software_factory.repo_scaffolder import materialize


def plan(strict):
    return {"schema": "ace.factory-etl-plan.v1", "id": "example_etl", "max_rows": 4, "max_bytes": 256,
            "delimiter": ",", "strict": strict, "columns": ["Nama", "Jumlah", "Tanggal"],
            "mapping": [{"source": source, "target": target, "type": kind, "trim": True,
                         "nullable": kind == "date", "max_chars": 40, "source_ref": "fixture/mapping"}
                        for source, target, kind in [("Nama", "name", "text"), ("Jumlah", "units", "integer"),
                                                     ("Tanggal", "date", "date")]]}


class ETLTests(unittest.TestCase):
    def execute(self, data, strict):
        directory = Path(self.enterContext(TemporaryDirectory())) / "pipeline"
        raw = plan(strict)
        files, product = etl_builder.build(raw, identity(raw))
        materialize(directory, files)
        return subprocess.run([sys.executable, "-B", product["runtime"]["path"], "--report"],
                              input=data, capture_output=True, timeout=5, cwd=directory)

    def test_csv_reordering_quotes_iso_date_and_receipt_provenance(self):
        data = 'Tanggal,Nama,Jumlah\n2024-02-29,"Gelas, kecil", 2\n,Cat,-1\n'.encode()
        completed = self.execute(data, strict=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([decode(line) for line in completed.stdout.splitlines()], [
            {"date": "2024-02-29", "name": "Gelas, kecil", "units": 2},
            {"date": None, "name": "Cat", "units": -1}])
        self.assertEqual(decode(completed.stderr)["output_sha256"], sha256(completed.stdout).hexdigest())

    def test_invalid_row_holds_strict_and_partial_mode_reports_row(self):
        data = b"Nama,Jumlah,Tanggal\nCat,2,\nGelas,03,2023-02-29\n"
        strict = self.execute(data, strict=True)
        partial = self.execute(data, strict=False)
        self.assertEqual((strict.returncode, partial.returncode), (1, 0))
        self.assertEqual(strict.stdout, b"")
        self.assertEqual(decode(partial.stdout)["name"], "Cat")
        self.assertEqual(decode(strict.stderr)["rejected"], [{"record": 2, "issues": [
            {"column": "date", "reason": "invalid_date"}, {"column": "units", "reason": "invalid_integer"}]}])

    def test_duplicate_header_fails_before_loading_records(self):
        completed = self.execute(b"Nama,Jumlah,Jumlah\nCat,2,1\n", strict=False)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(decode(completed.stderr)["reason"], "invalid_header")
        self.assertFalse(completed.stdout)
