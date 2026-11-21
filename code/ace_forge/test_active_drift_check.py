"""Verifier tiga arah antara selector, snapshot runtime, dan byte registry."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import active_drift_check as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_model_registry_v2 import event, records, review


WHEN = "2026-11-21T00:00:00Z"


def selector(key, slot="first", generation=1):
    obj = {"selector_ref": f"fixture/selector/{slot}", "active_sha256": key, "domain": "fixture/domain",
           "generation": generation, "history": [{"generation": generation, "artifact_sha256": key,
                                                 "activation_ref": f"fixture/activation/{slot}"}]}
    return {"slot": slot, "selector": obj, "selector_sha256": identity(obj)}


def fixture(root, *, register=True, qualified=True, relative=None):
    payload = b"frozen fixture bytes"
    key = hashlib.sha256(payload).hexdigest()
    registration = event(key)
    if relative:
        registration["values"]["artifact_ref"] = relative
    path = root / registration["values"]["artifact_ref"]
    if relative is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    items = [registration] if register else []
    if register and qualified:
        items.append(review(key))
    ledger, head = records(*items)
    raw = {"audit_ref": "fixture/audit", "as_of": WHEN, "max_age_seconds": 60, "registry_head_sha256": head,
           "selectors": [selector(key)], "observations": [
               {"slot": "first", "generation": 1, "artifact_sha256": key,
                "observed_at": "2026-11-20T23:59:30Z", "snapshot_ref": "fixture/runtime/first"},
           ]}
    return raw, ledger, path


def assess(raw, ledger, root):
    return model.assess(raw, ledger, root, identity(raw))


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))

    def test_matching_observation_and_file_produce_in_sync_with_provenance(self):
        raw, ledger, path = fixture(self.root)
        prior = path.read_bytes()
        product = assess(raw, ledger, self.root)
        self.assertEqual(product["status"], "in_sync")
        self.assertEqual(product["findings_by_kind"], {})
        item, = product["slots"]
        self.assertEqual(item["artifact_bytes"], {"bytes": len(prior), "sha256": hashlib.sha256(prior).hexdigest()})
        self.assertEqual(item["registry_artifact_ref"], path.relative_to(self.root).as_posix())
        self.assertEqual(item["registry_event_ref"], ledger[-1]["event"]["event_ref"])
        self.assertEqual(item["observation"]["snapshot_ref"], "fixture/runtime/first")
        self.assertEqual(path.read_bytes(), prior)

    def test_runtime_check_detects_both_stale_generation_and_wrong_artifact(self):
        raw, ledger, _ = fixture(self.root)
        seen = raw["observations"][0]
        seen.update(observed_at="2026-11-20T23:58:00Z", artifact_sha256="2"*64, generation=2)
        product = assess(raw, ledger, self.root)
        self.assertEqual(product["status"], "drift_or_incomplete")
        self.assertEqual(product["slots"][0]["findings"], ["observation_stale", "generation_drift", "runtime_artifact_drift"])
        self.assertEqual(product["findings_by_kind"]["runtime_artifact_drift"], 1)

    def test_exact_staleness_boundary_is_fresh_even_in_other_offset(self):
        raw, ledger, _ = fixture(self.root)
        observed = raw["observations"][0]
        for stamp, expected in (("2026-11-21T06:59:00+07:00", "in_sync"),
                                ("2026-11-21T06:58:59.999999+07:00", "drift_or_incomplete")):
            observed["observed_at"] = stamp
            with self.subTest(stamp=stamp):
                self.assertEqual(assess(raw, ledger, self.root)["status"], expected)

    def test_file_missing_modified_and_symlink_have_separate_diagnostics(self):
        raw, ledger, path = fixture(self.root)
        path.write_bytes(b"replacement")
        self.assertEqual(assess(raw, ledger, self.root)["slots"][0]["findings"], ["artifact_sha256_mismatch"])
        path.unlink()
        self.assertEqual(assess(raw, ledger, self.root)["slots"][0]["findings"], ["artifact_missing"])
        target = self.root / "outside-artifact"
        target.write_bytes(b"frozen fixture bytes")
        path.symlink_to(target)
        self.assertEqual(assess(raw, ledger, self.root)["slots"][0]["findings"], ["artifact_unreadable_or_unsafe"])

    def test_invalid_path_does_not_trigger_read_outside_artifact_root(self):
        raw, ledger, _ = fixture(self.root, relative="../unchecked")
        row = assess(raw, ledger, self.root)["slots"][0]
        self.assertEqual(row["findings"], ["invalid_artifact_path"])
        self.assertIsNone(row["artifact_bytes"])

    def test_absence_and_unqualified_findings_are_aggregated_in_slot_order(self):
        raw, ledger, _ = fixture(self.root, qualified=False)
        raw["selectors"].append(selector("f"*64, "another"))
        result = assess(raw, ledger, self.root)
        self.assertEqual([row["slot"] for row in result["slots"]], ["another", "first"])
        self.assertEqual(result["findings_by_kind"], {"not_registered": 1, "observation_missing": 1, "not_qualified": 1})
        self.assertIsNone(result["slots"][0]["observation"])

    def test_wrong_registry_domain_remains_a_finding_when_bytes_match(self):
        raw, ledger, _ = fixture(self.root)
        selection = raw["selectors"][0]
        selection["selector"]["domain"] = "other/domain"
        selection["selector_sha256"] = identity(selection["selector"])
        findings = assess(raw, ledger, self.root)["slots"][0]["findings"]
        self.assertEqual(findings, ["registry_domain_mismatch"])

    def test_refuses_future_registry_or_runtime_receipt(self):
        raw, ledger, _ = fixture(self.root)
        raw["observations"][0]["observed_at"] = "2026-11-21T00:00:01Z"
        with self.assertRaisesRegex(model.InputError, "masa depan"):
            assess(raw, ledger, self.root)
        raw["observations"].clear()
        raw["as_of"] = "2026-11-20T13:20:00Z"
        with self.assertRaisesRegex(model.InputError, "setelah waktu audit"):
            assess(raw, ledger, self.root)

    def test_external_and_nested_anchors_validate_different_sources(self):
        raw, ledger, _ = fixture(self.root)
        anchor = identity(raw)
        raw["selectors"][0]["selector"]["selector_ref"] = "test/changed"
        with self.assertRaisesRegex(model.InputError, "Rencana drift"):
            model.assess(raw, ledger, self.root, anchor)
        with self.assertRaisesRegex(model.InputError, "Selector berbeda"):
            assess(raw, ledger, self.root)
        raw["selectors"][0]["selector_sha256"] = identity(raw["selectors"][0]["selector"])
        with self.assertRaisesRegex(model.InputError, "Head registry"):
            assess(raw, ledger[:-1], self.root)

    def test_cli_exit_codes_distinguish_reported_drift_from_valid_consistency(self):
        raw, ledger, _ = fixture(self.root)
        plan_path, ledger_path = self.root / "audit.json", self.root / "registry.jsonl"
        ledger_path.write_bytes(b"".join(canonical(row) + b"\n" for row in ledger))
        for exit_code in (0, 1):
            if exit_code:
                raw["observations"].clear()
            plan_path.write_bytes(canonical(raw))
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(plan_path), str(ledger_path), str(self.root),
                                               "--expect-sha256", identity(raw)]), exit_code)
            self.assertEqual(json.loads(output.getvalue()), assess(raw, ledger, self.root))
            self.assertEqual(plan_path.read_bytes(), canonical(raw))

    def test_unexpected_and_duplicate_runtime_rows_cannot_enter_report(self):
        for change in ({"slot": "unknown"}, {}, {"slot": "second"}):
            raw, ledger, _ = fixture(self.root)
            key = raw["selectors"][0]["selector"]["active_sha256"]
            raw["selectors"].append(selector(key, "second"))
            raw["observations"].append({**raw["observations"][0], **change})
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "Observasi"):
                assess(raw, ledger, self.root)

    def test_requires_registered_slot_snapshot(self):
        raw, ledger, _ = fixture(self.root)
        raw["selectors"].clear()
        raw["observations"].clear()
        with self.assertRaisesRegex(model.InputError, "setidaknya satu selector"):
            assess(raw, ledger, self.root)
