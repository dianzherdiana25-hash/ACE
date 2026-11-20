"""Uji bahwa manifest mengikat byte masukan sebelum runner dipanggil."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import inheritance_probe


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.manifest = root / "manifest.json"
        self.args = ["--dry-run"]
        self.paths = {}
        for flag, data in (("inherited", {"passes": {"t": True}}),
                           ("cold", {"passes": {"t": False}}),
                           ("tasks", [{"id": "t"}]),
                           ("runner-argv", ["fixture", "{snapshot}", "{tasks}"])):
            path = root / f"{flag}.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.paths[flag.replace("-", "_")] = path
            self.args.extend([f"--{flag}", str(path)])

    def generate_manifest(self):
        with redirect_stdout(StringIO()) as output:
            code = inheritance_probe.main([*self.args, "--manifest", str(self.manifest)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["delta"], 1.0)

    def test_matching_manifest_runs_and_has_every_hash(self):
        self.generate_manifest()
        result = json.loads(self.manifest.read_bytes())
        for label, path in self.paths.items():
            self.assertEqual(result["inputs"][label]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(inheritance_probe.main([*self.args, "--verify-manifest", str(self.manifest)]), 0)
        self.assertEqual(json.loads(output.getvalue())["delta"], 1.0)

    def test_one_changed_byte_names_file_before_runner(self):
        self.generate_manifest()
        path = self.paths["inherited"]
        path.write_bytes(path.read_bytes().replace(b'"t"', b'"u"', 1))
        with patch.object(inheritance_probe, "compare") as run, redirect_stderr(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                inheritance_probe.main([*self.args, "--verify-manifest", str(self.manifest)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("inherited.json", output.getvalue())
        run.assert_not_called()

    def test_manifest_binds_task_set_hash_and_rejects_single_task_change(self):
        # Perluas fixture dengan dua tugas agar perubahan satu tugas terbukti terdeteksi
        self.paths["inherited"].write_text(json.dumps({"passes": {"t1": True, "t2": True}}), encoding="utf-8")
        self.paths["cold"].write_text(json.dumps({"passes": {"t1": False, "t2": False}}), encoding="utf-8")
        self.paths["tasks"].write_text(
            json.dumps([{"id": "t1", "prompt": "awal"}, {"id": "t2", "prompt": "stabil"}]),
            encoding="utf-8",
        )
        self.generate_manifest()

        manifest_data = json.loads(self.manifest.read_bytes())
        expected_tasks_sha = hashlib.sha256(self.paths["tasks"].read_bytes()).hexdigest()
        self.assertEqual(manifest_data["inputs"]["tasks"]["sha256"], expected_tasks_sha)
        self.assertEqual(manifest_data["task_set"]["sha256"], expected_tasks_sha)
        self.assertEqual(manifest_data["task_set"]["task_count"], 2)
        self.assertEqual(sorted(manifest_data["task_set"]["task_sha256s"].keys()), ["t1", "t2"])

        # Ubah tepat satu tugas setelah manifest dibuat
        self.paths["tasks"].write_text(
            json.dumps([{"id": "t1", "prompt": "berubah"}, {"id": "t2", "prompt": "stabil"}]),
            encoding="utf-8",
        )
        with patch.object(inheritance_probe, "compare") as run, redirect_stderr(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                inheritance_probe.main([*self.args, "--verify-manifest", str(self.manifest)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("tasks.json", output.getvalue())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
