"""Uji replay, lineage, review, dan pencatatan yang tidak mengubah berkas."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import model_registry_v2 as model
from ace_forge._forge_io import canonical, identity


BASE, CHILD = "a" * 64, "b" * 64


def event(key, kind="base", parents=None, *, at="2026-11-20T13:00:00Z"):
    return {"type": "register", "artifact_sha256": key, "event_ref": f"fixture/event/{key[:4]}", "at": at,
            "values": {"kind": kind, "artifact_ref": f"fixture/artifact/{key[:4]}",
                       "recipe_ref": "fixture/recipe", "parent_sha256": parents or [], "domain": "fixture/domain"}}


def review(key=CHILD, verdict="qualified"):
    return {"type": "review", "artifact_sha256": key, "event_ref": f"fixture/review/{key[:4]}",
            "at": "2026-11-20T13:30:00Z", "values": {
                "verdict": verdict, "result_ref": f"fixture/result/{key[:4]}",
                "regression_ref": f"fixture/guard/{key[:4]}", "held_out_sha256": "f" * 64,
            }}


def records(*actions):
    log, head = [], model.GENESIS
    for action in actions:
        row = model.propose(log, head, action)
        head = row["sha256"]
        log.append(row)
    return log, head


def action_entry(event_raw, *, previous=model.GENESIS, sequence=1):
    values = {"sequence": sequence, "previous_sha256": previous, "event": event_raw}
    return {**values, "sha256": identity(values)}


class RegistryTests(unittest.TestCase):
    def test_registered_and_qualified_lineage_keep_both_provenance_sources(self):
        raw, head = records(event(BASE), event(CHILD, "adapter", [BASE]), review())
        result = model.inspect(raw, head)
        self.assertEqual(result["head_sha256"], head)
        self.assertEqual(result["events"], 3)
        base, child = result["artifacts"]
        self.assertEqual((base["status"], child["status"]), ("registered", "qualified"))
        self.assertEqual(child["parent_sha256"], [BASE])
        self.assertEqual(child["review"]["result_ref"], "fixture/result/bbbb")
        self.assertEqual(child["review"]["regression_ref"], "fixture/guard/bbbb")
        self.assertEqual(child["last_event_at"], "2026-11-20T13:30:00+00:00")
        self.assertNotIn("active", child)

    def test_retire_preserves_rejection_and_evidence(self):
        retire = {"type": "retire", "artifact_sha256": CHILD, "event_ref": "fixture/retired",
                  "at": "2026-11-20T15:10:00Z", "values": {"reason_ref": "fixture/reason"}}
        raw, head = records(event(BASE), event(CHILD, "adapter", [BASE]), review(verdict="rejected"), retire)
        child = model.inspect(raw, head)["artifacts"][1]
        self.assertEqual(child["status"], "retired")
        self.assertEqual(child["status_before_retire"], "rejected")
        self.assertEqual(child["review"]["held_out_sha256"], "f" * 64)
        self.assertEqual(child["reason_ref"], "fixture/reason")

    def test_parent_has_to_be_present_and_have_correct_arity(self):
        raw, head = records(event(BASE))
        for kind, parents in (("adapter", []), ("adapter", ["f" * 64]), ("merged", [BASE, BASE]), ("base", [BASE])):
            with self.subTest(kind=kind, parents=parents), self.assertRaisesRegex(model.InputError, "lineage"):
                model.propose(raw, head, event(CHILD, kind, parents))

    def test_invalid_transition_and_wrong_time_cannot_add_records(self):
        raw, head = records(event(BASE), event(CHILD, "adapter", [BASE]), review())
        for altered in (event(CHILD, "adapter", [BASE]), {**review(), "event_ref": "fixture/another"},
                        event("c" * 64, at="2026-11-20T13:01:00Z")):
            with self.subTest(altered=altered), self.assertRaises(model.InputError):
                model.propose(raw, head, altered)
        with self.assertRaisesRegex(model.InputError, "cap waktu|Cap waktu"):
            model.propose(raw, head, event("d" * 64, at="2026-11-20T15:01:00"))

    def test_truncation_rehash_and_reordering_fail_for_the_trusted_anchor(self):
        raw, head = records(event(BASE), event(CHILD, "adapter", [BASE]))
        with self.assertRaisesRegex(model.InputError, "Head"):
            model.inspect(raw[:-1], head)
        with self.assertRaisesRegex(model.InputError, "Urutan"):
            model.inspect(raw[::-1], head)
        altered = event(CHILD, "adapter", [BASE])
        altered["values"]["domain"] = "fixture/new"
        alternative, alt_head = records(event(BASE), altered)
        self.assertEqual(model.inspect(alternative, alt_head)["artifacts"][1]["domain"], "fixture/new")
        with self.assertRaisesRegex(model.InputError, "Head"):
            model.inspect(alternative, head)

    def test_rejected_apply_cannot_poison_the_next_attempt_by_consuming_refs(self):
        registry = model.Registry()
        invalid = event(BASE)
        invalid["values"]["domain"] = ""
        with self.assertRaises(model.InputError):
            registry.apply(action_entry(invalid))
        self.assertEqual((registry.head, registry.length, registry.seen_refs), (model.GENESIS, 0, set()))
        registry.apply(action_entry(event(BASE)))
        self.assertEqual(registry.export()["artifacts"][0]["status"], "registered")

    def test_propose_cli_emits_canonical_line_and_keeps_empty_ledger(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        log, path = root / "registry.jsonl", root / "event.json"
        log.touch()
        path.write_bytes(canonical(event(BASE)))
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(log), "--expect-head", model.GENESIS, "--propose-event", str(path)]), 0)
        line = output.getvalue().encode()
        self.assertEqual(log.read_bytes(), b"")
        entry = json.loads(line)
        self.assertEqual(line, canonical(entry) + b"\n")
        log.write_bytes(line)
        with redirect_stdout(StringIO()) as audit:
            self.assertEqual(model.main([str(log), "--expect-head", entry["sha256"]]), 0)
        self.assertEqual(json.loads(audit.getvalue()), model.inspect([entry], entry["sha256"]))
        self.assertEqual(log.read_bytes(), line)

    def test_incomplete_or_noncanonical_log_is_rejected_before_propose(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        log = root / "registry.jsonl"
        valid = canonical(action_entry(event(BASE)))
        for data in (valid, b" " + valid + b"\n", valid + b"\n\n"):
            log.write_bytes(data)
            with self.subTest(data=data), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                model.main([str(log), "--expect-head", model.GENESIS])
            self.assertEqual(error.exception.code, 2)

    def test_utc_offsets_of_equal_instants_preserve_monotonic_order(self):
        rows, head = records(event(BASE), event(CHILD, "adapter", [BASE], at="2026-11-20T20:00:00+07:00"))
        first, second = model.inspect(rows, head)["artifacts"]
        self.assertEqual(first["last_event_at"], second["last_event_at"])
        self.assertEqual(second["last_event_at"], "2026-11-20T13:00:00+00:00")
