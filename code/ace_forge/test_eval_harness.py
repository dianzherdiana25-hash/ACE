"""Uji gerbang kandidat, pemisahan kasus, dan frontier kualitas/biaya."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import brain_bench, eval_harness as model, forgetting_guard
from ace_forge._forge_io import canonical, identity
from ace_forge.test_brain_bench import BEFORE, fixture as bench_fixture
from ace_forge.test_forgetting_guard import case, observation, q


FAST, ACCURATE, DOMINATED, MISSING = ("2" * 64, "3" * 64, "4" * 64, "5" * 64)


def packet(key, gain, duration, memory):
    bench, _ = bench_fixture()
    bench["after_sha256"] = key
    for row in bench["results"]:
        base = row["before"]
        row["after"].update(score_bp=base["score_bp"] + gain,
                            elapsed_us=base["elapsed_us"] + duration, peak_bytes=base["peak_bytes"] + memory,
                            artifact_sha256=key)
    guard = {"protocol": {"protocol_ref": "fixture/general", "cases": [case("outside", "general", True)]},
             "results": [observation("outside", True, True)]}
    return {"artifact_sha256": key, "source_ref": f"fixture/evidence/{key[:4]}", "benchmark": bench,
            "general": {"candidate_sha256": key, "baseline_sha256": BEFORE, "input": guard}}


def fixture():
    candidates = [
        packet(FAST, 500, 0, -5), packet(ACCURATE, 1200, 2, 10), packet(DOMINATED, 500, 3, 15),
    ]
    target = candidates[0]["benchmark"]
    guard = candidates[0]["general"]["input"]
    plan = {
        "gate_ref": "fixture/gate", "baseline_sha256": BEFORE, "rubric_ref": target["rubric_ref"],
        "target_protocol_sha256": forgetting_guard.protocol_digest(target["protocol"]),
        "general_protocol_sha256": forgetting_guard.protocol_digest(guard["protocol"]),
        "target_floors": [{"domain": name, "min_gain_bp": 500} for name in ("reading", "writing")],
        "candidates": [
            {"artifact_sha256": row["artifact_sha256"], "registry_ref": f"fixture/registry/{row['artifact_sha256'][0]}",
             "bench_sha256": brain_bench.bench_digest(row["benchmark"])} for row in candidates
        ] + [{"artifact_sha256": MISSING, "registry_ref": "fixture/registry/missing", "bench_sha256": "0" * 64}],
    }
    return plan, candidates


def evaluate(plan, evidence):
    return model.evaluate(plan, evidence, identity(plan))


class GateTests(unittest.TestCase):
    def test_frontier_keeps_quality_time_tradeoff_and_does_not_rank_missing_evidence(self):
        plan, evidence = fixture()
        report = evaluate(plan, evidence)
        self.assertEqual(report["frontier"], [FAST, ACCURATE])
        first, second, third, fourth = report["candidate_results"]
        self.assertEqual([row["status"] for row in (first, second, third)], ["qualified"] * 3)
        self.assertEqual(fourth["status"], "missing_evidence")
        self.assertEqual(first["target_domains"][0]["gain_bp"], q(500))
        self.assertEqual(second["mean_delta"]["elapsed_us"], q(2))
        self.assertEqual(second["source_ref"], "fixture/evidence/3333")
        self.assertEqual(third["registry_ref"], "fixture/registry/4")

    def test_low_target_gain_and_general_regression_trigger_independent_blockers(self):
        plan, data = fixture()
        plan["target_floors"][0]["min_gain_bp"] = 600
        data[0]["general"]["input"]["results"][0]["candidate"]["passed"] = False
        report = evaluate(plan, data)
        self.assertEqual(report["candidate_results"][0]["blockers"], [
            {"domain": "reading", "reason": "below_gain_floor"},
            {"domain": "general", "reason": "general_guard_hold"},
        ])
        self.assertEqual(report["frontier"], [ACCURATE])

    def test_invalid_evidence_for_one_candidate_is_localized(self):
        plan, data = fixture()
        data[0]["general"]["candidate_sha256"] = ACCURATE
        report = evaluate(plan, data)
        first, second, *_ = report["candidate_results"]
        self.assertEqual(first["status"], "invalid_evidence")
        self.assertIn("artefak berbeda", first["detail"])
        self.assertEqual(second["status"], "qualified")

    def test_same_case_pointer_in_both_protocols_is_always_invalid(self):
        plan, data = fixture()
        guard = data[0]["general"]["input"]
        guard["protocol"]["cases"][0]["case_ref"] = " q/a "
        plan["general_protocol_sha256"] = forgetting_guard.protocol_digest(guard["protocol"])
        result = evaluate(plan, data)["candidate_results"][0]
        self.assertEqual(result["status"], "invalid_evidence")
        self.assertIn("tumpang tindih", result["detail"])

    def test_bench_individual_config_cannot_override_shared_rubric_or_case_roster(self):
        for patch in ("rubric", "cases"):
            plan, data = fixture()
            bench = data[0]["benchmark"]
            if patch == "rubric":
                bench["rubric_ref"] = "fixture/different"
            else:
                bench["protocol"]["cases"][0]["domain"] = "shared-only-by-name"
            plan["candidates"][0]["bench_sha256"] = brain_bench.bench_digest(bench)
            with self.subTest(patch=patch):
                rejected = evaluate(plan, data)["candidate_results"][0]
                self.assertEqual(rejected["status"], "invalid_evidence")
                self.assertIn("bersama", rejected["detail"])

    def test_insufficient_target_pairs_report_absence_without_zero_uplift(self):
        plan, data = fixture()
        data[0]["benchmark"]["results"][0]["after"] = None
        row = evaluate(plan, data)["candidate_results"][0]
        self.assertEqual(row["status"], "hold")
        self.assertIsNone(row["target_domains"][0]["gain_bp"])
        self.assertEqual(row["blockers"][0]["reason"], "insufficient_target_pairs")

    def test_different_authorized_candidate_inputs_work_in_any_order(self):
        plan, data = fixture()
        result = evaluate(plan, data)
        self.assertEqual(result, evaluate(plan, data[::-1]))
        for malformed in ([data[0], data[0]], [{**data[0], "artifact_sha256": "9" * 64}]):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(model.InputError, "ganda|terdaftar"):
                evaluate(plan, malformed)

    def test_anchor_must_bind_all_candidates_rubric_and_floor(self):
        plan, data = fixture()
        expected = identity(plan)
        plan["target_floors"][0]["min_gain_bp"] = 1000
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.evaluate(plan, data, expected)

    def test_cli_computes_and_keeps_canonical_report_read_only(self):
        plan, data = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        p, src = root / "policy.json", root / "scores.json"
        p.write_bytes(canonical(plan))
        src.write_bytes(canonical(data))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(p), str(src), "--expect-plan-sha256", identity(plan)]), 0)
        self.assertEqual(json.loads(out.getvalue()), evaluate(plan, data))
        self.assertEqual(src.read_bytes(), canonical(data))
