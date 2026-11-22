"""Verifier bench Chromium tertutup, arsip setiap tugas, dan red control."""
from pathlib import Path
import unittest

from ace_web_operator import web_ops_bench
from ace_web_operator._contracts import ContractError,decode,identity
from ace_web_operator.test_browser_engine import browser_available


FIXTURE=Path(__file__).with_name("fixtures")/"web_operator_bench.json"


class WebBenchTests(unittest.TestCase):
    def setUp(self):
        self.plan=decode(FIXTURE.read_bytes())

    def test_real_closed_bench_all_tasks_have_archived_proofs(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        files,result=web_ops_bench.run(self.plan,identity(self.plan))
        self.assertEqual((result["tasks"],result["completed"],result["with_snapshot_proof"]),(7,7,7),result)
        self.assertEqual(result["mutating_requests_observed"],0)
        self.assertEqual(result["status"],"passed")
        for case in result["cases"]:
            evidence=web_ops_bench.verify_case(files,case["manifest"],case["manifest_sha256"])
            self.assertEqual(evidence["task_id"],case["id"])
        case=result["cases"][0]
        evidence=web_ops_bench.verify_case(files,case["manifest"],case["manifest_sha256"])
        files[evidence["files"][0]["path"]]+=b"x"
        with self.assertRaisesRegex(ContractError,"tidak utuh"):
            web_ops_bench.verify_case(files,case["manifest"],case["manifest_sha256"])

    def test_false_witness_holds_benchmark_but_keeps_proof(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        case=self.plan["cases"][0]
        self.plan["cases"]=[case]
        case["stages"][1]["steps"][-1]["expected"]="Teks salah"
        _,result=web_ops_bench.run(self.plan,identity(self.plan))
        self.assertEqual((result["completed"],result["with_snapshot_proof"],result["status"]),(0,1,"failed"))

    def test_saved_fixture_proofs_verify_from_repository_bytes(self):
        base=FIXTURE.parent / "operator_bench_evidence"
        files={path.relative_to(base).as_posix(): path.read_bytes() for path in base.rglob("*") if path.is_file()}
        report=decode(files["operator_bench_report.json"])
        self.assertEqual(report["plan_sha256"],identity(self.plan))
        self.assertEqual((report["tasks"],report["completed"],report["with_snapshot_proof"]),(7,7,7))
        self.assertEqual(report["mutating_requests_observed"],0)
        for row in report["cases"]:
            evidence=web_ops_bench.verify_case(files,row["manifest"],row["manifest_sha256"])
            self.assertEqual(evidence["task_id"],row["id"])

    def test_no_checkout_route_is_registered(self):
        self.plan["pages"].append({"path":"/checkout","media_type":"text/html","body":"fake","source_ref":"fixture/no"})
        with self.assertRaisesRegex(ContractError,"transaksi"):
            web_ops_bench.run(self.plan,identity(self.plan))
