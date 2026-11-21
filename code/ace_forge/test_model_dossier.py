"""Verifier replay dossier lintas registry, bench, guard, smoke dan persetujuan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import brain_bench, forgetting_guard, model_dossier as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_activation_ladder import vote
from ace_forge.test_brain_bench import AFTER, BEFORE, fixture as bench_fixture
from ace_forge.test_forgetting_guard import fixture as guard_fixture
from ace_forge.test_model_registry_v2 import event, records, review
from ace_forge.test_smoke_test_model import fixture as smoke_fixture


def approvals(raw):
    anchors = {"held_out": identity(raw["held_out"]["data"]), "regression": identity(raw["regression"]),
               "smoke": identity(raw["smoke"])}
    stages, actions = [], []
    for sequence, (key, pointer) in enumerate(anchors.items(), 1):
        role = "review-" + key
        stages.append({"stage": key, "roles": [role], "evidence_sha256": pointer})
        actions.append(vote(key, role, sequence, pointer, artifact_sha256=AFTER))
    policy = {"policy_ref": "fixture/activation", "artifact_sha256": AFTER, "stages": stages}
    history = {"ledger_ref": "fixture/approval", "events": actions}
    return {"policy": policy, "history": history, "policy_sha256": identity(policy), "history_sha256": identity(history)}


def registry(raw, *, actual_parent=True):
    assessed = review(AFTER)
    assessed["values"]["held_out_sha256"] = identity(raw["held_out"]["data"])
    assessed["values"]["regression_ref"] = raw["regression"]["source_ref"]
    extra = [] if actual_parent else [event("e"*64)]
    child = event(AFTER, "adapter", [BEFORE] if actual_parent else ["e"*64])
    child["values"]["domain"] = "reading"
    log, head = records(event(BEFORE), *extra, child, assessed)
    return {"source_ref": "fixture/registry", "records": log, "head": head}


def fixture():
    bench, bench_sha = bench_fixture()
    guard, guard_sha = guard_fixture()
    guard["results"][0]["candidate"]["passed"] = True
    protocol, observations = smoke_fixture()
    protocol["artifact_sha256"] = AFTER
    for row in observations["observations"]:
        row["artifact_sha256"] = AFTER
    raw = {"dossier_ref": "fixture/dossier", "baseline_sha256": BEFORE, "candidate_sha256": AFTER,
           "target_domain": "reading", "minimum_gain_bp": 500,
           "held_out": {"data": bench, "bench_sha256": bench_sha, "source_ref": "fixture/bench"},
           "regression": {"data": guard, "protocol_sha256": guard_sha, "source_ref": "fixture/guard",
                          "baseline_sha256": BEFORE, "candidate_sha256": AFTER},
           "smoke": {"protocol": protocol, "receipts": observations, "protocol_sha256": identity(protocol)}}
    return {**raw, "approval": approvals(raw), "registry": registry(raw)}


def assemble(raw):
    return model.assemble(raw, identity(raw))


class DossierTests(unittest.TestCase):
    def test_all_evidence_agrees_for_one_artifact_and_ladder_anchors_exact_results(self):
        raw = fixture()
        result = assemble(raw)
        self.assertEqual(result["status"], "ready_for_review")
        self.assertEqual(result["candidate_sha256"], AFTER)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["registry"]["artifact"]["domain"], "reading")
        self.assertTrue(result["registry"]["baseline_in_lineage"])
        self.assertEqual(result["regression"]["report"]["status"], "pass")
        self.assertEqual(result["smoke"]["report"]["status"], "passed")
        self.assertEqual(result["approval"]["status"], "approvals_complete")
        self.assertEqual(result["held_out"]["evidence_sha256"], identity(raw["held_out"]["data"]))
        rendered = model.markdown(result)
        self.assertIn("fixture/approval", rendered)
        self.assertIn("fixture/bench", rendered)
        self.assertIn(identity(raw), rendered)

    def test_missing_components_remain_unknown_even_if_receipts_are_provided(self):
        raw = fixture()
        raw.update(held_out=None, registry=None)
        report = assemble(raw)
        self.assertEqual(report["status"], "hold")
        self.assertEqual(report["missing"], ["registry", "held_out"])
        self.assertEqual(report["blockers"], [])
        self.assertIn("held_out. TIDAK TAHU.", model.markdown(report))

    def test_target_threshold_and_lineage_hold_separately(self):
        raw = fixture()
        raw["minimum_gain_bp"] = 501
        raw["registry"] = registry(raw, actual_parent=False)
        report = assemble(raw)
        self.assertEqual(report["blockers"], ["registry_baseline_not_in_lineage", "target_gain_below_threshold"])
        self.assertEqual(report["status"], "hold")

    def test_guard_and_smoke_fail_independently_even_if_approved(self):
        raw = fixture()
        raw["regression"]["data"]["results"][0]["candidate"]["passed"] = False
        raw["smoke"]["receipts"]["observations"].pop()
        raw["approval"] = approvals(raw)
        result = assemble(raw)
        self.assertEqual(result["blockers"], ["regression_gate_held", "smoke_gate_held"])

    def test_incomplete_heldout_has_no_gain_and_invalidates_previous_registry_review(self):
        raw = fixture()
        raw["held_out"]["data"]["results"][0]["after"] = None
        raw["approval"] = approvals(raw)
        result = assemble(raw)
        self.assertEqual(result["blockers"], ["registry_review_bench_mismatch", "target_coverage_missing"])

    def test_guard_provenance_must_agree_with_registry_review_source(self):
        raw = fixture()
        raw["regression"]["source_ref"] += "-relocated"
        raw["approval"] = approvals(raw)
        self.assertEqual(assemble(raw)["blockers"], ["registry_review_regression_mismatch"])

    def test_does_not_accept_old_approval_when_new_evidence_looks_equivalent(self):
        raw = fixture()
        raw["smoke"]["receipts"]["batch_ref"] += "-changed"
        with self.assertRaisesRegex(model.InputError, "bukti dossier untuk smoke"):
            assemble(raw)

    def test_pending_approvals_keep_review_on_hold(self):
        raw = fixture()
        approval = raw["approval"]
        approval["history"]["events"].pop()
        approval["history_sha256"] = identity(approval["history"])
        report = assemble(raw)
        self.assertEqual(report["blockers"], ["approval_pending"])
        self.assertEqual(report["approval"]["pending_stage"], "smoke")

    def test_wrong_artifact_linkage_fails_before_status_render(self):
        raw = fixture()
        raw["held_out"]["data"]["after_sha256"] = "f"*64
        for row in raw["held_out"]["data"]["results"]:
            row["after"]["artifact_sha256"] = "f"*64
        raw["held_out"]["bench_sha256"] = brain_bench.bench_digest(raw["held_out"]["data"])
        with self.assertRaisesRegex(model.InputError, "kandidat berbeda"):
            assemble(raw)

    def test_registry_and_full_dossier_anchors_authenticate_different_inputs(self):
        raw = fixture()
        before = identity(raw)
        raw["registry"]["head"] = "0"*64
        with self.assertRaisesRegex(model.InputError, "Dossier.*anchor"):
            model.assemble(raw, before)
        with self.assertRaisesRegex(model.InputError, "Head registry"):
            assemble(raw)

    def test_cli_renders_json_and_markdown_without_modifying_input(self):
        raw = fixture()
        p = Path(self.enterContext(TemporaryDirectory())) / "dossier.json"
        source = canonical(raw)
        p.write_bytes(source)
        for fmt in ("json", "markdown"):
            with self.subTest(fmt=fmt), redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main([str(p), "--expect-sha256", identity(raw), "--format", fmt]), 0)
            expected = model.markdown(assemble(raw)) if fmt == "markdown" else canonical(assemble(raw)).decode() + "\n"
            self.assertEqual(out.getvalue(), expected)
            self.assertEqual(p.read_bytes(), source)
