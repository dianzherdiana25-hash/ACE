"""Jalankan produk hasil pabrik dan bongkar evidence penerimaannya."""
from pathlib import Path
import unittest

from ace_software_factory import factory_bench
from ace_software_factory._contracts import ContractError, decode, identity


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "factory_product_bench.json"


class FactoryBenchTests(unittest.TestCase):
    def setUp(self):
        self.raw = decode(FIXTURE.read_bytes())

    def test_three_generated_products_cover_every_acceptance_criterion(self):
        evidence, report = factory_bench.run(self.raw, identity(self.raw))
        self.assertEqual((report["product_count"], report["passed"]), (3, 3), report)
        committed = FIXTURE.parent / "bench_evidence"
        self.assertEqual(set(evidence), {path.relative_to(committed).as_posix()
                                        for path in committed.rglob("*.json")})
        for path, payload in evidence.items():
            self.assertEqual(payload, (committed / path).read_bytes())
        self.assertEqual({row["surface"] for row in report["products"]}, {"web", "cli", "service"})
        for row in report["products"]:
            with self.subTest(surface=row["surface"]):
                receipt = decode(evidence[row["acceptance"]])
                observed = decode(evidence[row["acceptance"].replace("acceptance.json", "observations.json")])
                self.assertEqual(receipt["observations_sha256"], identity(observed))
                self.assertEqual(receipt["artifact_sha256"], row["artifact_sha256"])
                self.assertEqual(receipt["counts"]["passed"], 3)

    def test_wrong_deliverable_marks_one_product_failed_without_hiding_other_results(self):
        web = next(row for row in self.raw["products"] if row["brief"]["surface"] == "web")
        web["rules"][-1]["expected"] = 401
        _, result = factory_bench.run(self.raw, identity(self.raw))
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(next(row for row in result["products"] if row["surface"] == "web")["counts"]["failed"], 1)

    def test_anchor_mismatch_refuses_before_starting_any_product(self):
        with self.assertRaisesRegex(ContractError, "anchor"):
            factory_bench.run(self.raw, "a" * 64)


class BrowserProductTests(unittest.TestCase):
    def test_generated_form_in_chromium_commits_record_via_generated_api(self):
        from importlib.util import module_from_spec, spec_from_file_location
        import shutil
        import subprocess
        from tempfile import TemporaryDirectory
        from threading import Thread

        from ace_software_factory import repo_scaffolder, spec_writer

        node, chromium = shutil.which("node"), shutil.which("chromium")
        if not (node and chromium):
            self.skipTest("Node dan Chromium lokal diperlukan untuk verifier browser")
        check = subprocess.run([node, "-e", 'require.resolve("playwright")'], capture_output=True, timeout=5)
        if check.returncode:
            self.skipTest("Playwright lokal tidak tersedia")
        raw = decode(FIXTURE.read_bytes())
        row = next(item for item in raw["products"] if item["brief"]["surface"] == "web")
        product = spec_writer.write(row["brief"])
        files = factory_bench._assemble(product, row["recipe"], row["architecture"])
        root = Path(self.enterContext(TemporaryDirectory())) / "product"
        repo_scaffolder.materialize(root, files)
        specs = spec_from_file_location("ace_factory_browser_backend", root / "backend.py")
        module = module_from_spec(specs)
        specs.loader.exec_module(module)
        server = self.enterContext(module.server(root / "test.sqlite", home_page=files["index.html"]))
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 4)
        self.addCleanup(server.shutdown)
        script = FIXTURE.parent / "verify_generated_web.cjs"
        result = subprocess.run([node, str(script), str(server.server_port), chromium],
                                capture_output=True, timeout=20, cwd=script.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decode(result.stdout), {"submitted": 201, "fetch": 200, "returned": "Kotak alat"})
