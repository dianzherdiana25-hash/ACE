from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import GuardianError, canonical, identity
from ._snapshots import build_manifest, verify
from .counterfactual_protocol import experiment
from .migration_rehearsal import rehearse
from .promotion_gate import screen
from .rollback_engine import restore
from .snapshot_scheduler import schedule
from .state_forker import fork
from .twin_chaos import drill
from .twin_diff import compare
from .twin_registry import index
from .twin_runner import run


def plan(name, **entries):
    return {"schema": f"ace.guardian.{name}.v1", **entries}


def call(operation, document, *args):
    return operation(document, identity(document), *args)


def scenario():
    return plan("twin-run", initial={"cycle": 0, "frozen": 23}, cycles=[
        [{"op": "add", "field": "cycle", "value": 2}],
        [{"op": "add", "field": "cycle", "value": 3}]], must_keep=["frozen"])


class TwinsTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "sub").mkdir()
        self.original = self.source / "sub/model.json"
        self.raw = b'{"ready":true}'
        self.original.write_bytes(self.raw)
        self.manifest = build_manifest(self.source, ["sub/model.json"])

    def test_01_fork_has_separate_inode_and_refuses_symlink_and_nested_destination(self):
        target = self.root / "twin"
        result = fork(self.source, target, self.manifest, identity(self.manifest))
        local = target / "sub/model.json"
        self.assertEqual(result["files"], 1)
        self.assertNotEqual(local.stat().st_ino, self.original.stat().st_ino)
        local.write_bytes(b"twin-only")
        self.assertEqual(self.original.read_bytes(), self.raw)
        (self.source / "symlink").symlink_to(self.original)
        with self.assertRaises(OSError):
            build_manifest(self.source, ["symlink"])
        with self.assertRaises(GuardianError):
            fork(self.source, self.source / "nested", self.manifest, identity(self.manifest))

    def test_02_cycle_is_bounded_and_protected_state_unchanged(self):
        original = scenario()
        self.assertEqual(call(run, original)["state"], {"cycle": 5, "frozen": 23})
        self.assertEqual(original["initial"]["cycle"], 0)
        original["cycles"][1][0]["field"] = "frozen"
        with self.assertRaises(GuardianError):
            call(run, original)

    def test_03_diff_finds_first_split_and_signed_deltas(self):
        left = scenario()
        right = deepcopy(left)
        right["cycles"][1][0]["value"] = 2
        diff = plan("twin-diff", baseline=call(run, left), candidate=call(run, right))
        report = call(compare, diff)
        self.assertEqual(report["first_difference_cycle"], 2)
        self.assertEqual([row["delta"] for row in report["deltas"]], [-1, 0])
        diff["candidate"]["state"]["cycle"] = 100
        with self.assertRaises(GuardianError):
            call(compare, diff)

    def test_04_single_treatment_baseline_input_remains_exact(self):
        reference = scenario()
        original = identity(reference)
        result = call(experiment, plan("counterfactual", runner=reference,
                                      treatment={"cycle": 2, "action": 1, "replacement": 5}))
        self.assertEqual(result["baseline_sha256"], original)
        self.assertEqual(identity(reference), original)
        self.assertEqual(result["comparison"]["deltas"][0]["delta"], 2)
        seal = result.pop("seal_sha256")
        self.assertEqual(seal, identity(result))

    def test_05_replay_recovers_exact_final_state_in_both_fault_phases(self):
        result = call(drill, plan("chaos-plan", runner=scenario(),
                                 faults=[{"cycle": 1, "mode": mode} for mode in ("before_commit", "after_commit")]))
        self.assertEqual([row["committed"] for row in result["cases"]], [1, 0])
        self.assertTrue(all(row["resumed_sha256"] == result["baseline"] for row in result["cases"]))

    def test_06_promotion_holds_worse_metric_despite_green_verifier(self):
        item = {"id": "latency", "baseline": 10, "candidate": 12, "baseline_ref": "a"*64,
                "candidate_ref": "b"*64, "direction": "lower", "minimum_gain": 1}
        probe = plan("promotion-plan", metrics=[item], validations=[{"id": "custody", "passed": True, "source": "c"*64}])
        result = call(screen, probe)
        self.assertEqual((result["recommendation"], result["metrics"][0]["gain"]), ("hold", "-2"))
        item["candidate"] = 9
        self.assertEqual(call(screen, probe)["recommendation"], "eligible")
        item["candidate_ref"] = item["baseline_ref"]
        self.assertEqual(call(screen, probe)["metrics"][0]["status"], "same_evidence")

    def test_07_rollback_restores_verified_bytes_only_to_fresh_path(self):
        current = self.root / "current"
        current.mkdir()
        (current / "temp.json").write_bytes(b"rejected")
        current_snapshot = build_manifest(current, ["temp.json"])
        target = self.root / "restored"
        result = call(restore, plan("rollback-plan", verified_snapshot=self.manifest,
                                    current_snapshot=current_snapshot), self.source, current, target)
        self.assertEqual(result["added"], ["sub/model.json"])
        self.assertEqual(result["removed"], ["temp.json"])
        self.assertEqual(verify(target, self.manifest, reject_extras=True)["sub/model.json"], self.raw)
        self.assertEqual((current / "temp.json").read_bytes(), b"rejected")

    def test_08_registry_rejects_bad_transition_or_snapshot_replacement(self):
        row = {"twin": "fixture", "event": "created", "snapshot": "a"*64, "source": "fixture:1",
               "previous": identity({"kind": "ace.guardian.twin-registry.v1"})}
        broken = {**row, "event": "tested", "previous": identity(row)}
        with self.assertRaises(GuardianError):
            call(index, plan("twin-registry-plan", events=[row, broken]))
        result = call(index, plan("twin-registry-plan", events=[row, {**broken, "event": "running"}]))
        self.assertEqual(result["twins"]["fixture"]["state"], "running")

    def test_09_rehearsal_checks_target_schema_and_capacity_before_copy(self):
        target = self.root / "migrated"
        probe = plan("migration", manifest=self.manifest, max_bytes=1,
                     json_checks=[{"path": "sub/model.json", "fields": ["ready"]}])
        self.assertEqual(call(rehearse, probe, self.source, target)["status"], "held")
        self.assertFalse(target.exists())
        probe["max_bytes"] = 100
        probe["json_checks"][0]["fields"] = ["absent"]
        self.assertEqual(call(rehearse, probe, self.source, target)["format_checks"][0]["missing_fields"], ["absent"])
        probe["json_checks"][0]["fields"] = ["ready"]
        self.assertEqual(call(rehearse, probe, self.source, target)["status"], "fixture_rehearsed")

    def test_10_schedule_honors_catchup_dedup_and_retention(self):
        probe = plan("snapshot-schedule", schedule={"origin": "2025-07-01T00:00:00Z", "every_minutes": 60, "keep": 2},
                     now="2025-07-01T05:00:00Z", completed=[], max_catch_up=1)
        report = call(schedule, probe)
        self.assertEqual((report["outside_retention_slots"], report["pending_after_cap"]), (4, 1))
        self.assertEqual(report["due"][0]["index"], 4)
        probe["completed"].append(report["due"][0]["idempotency_key"])
        self.assertEqual(call(schedule, probe)["due"][0]["index"], 5)
