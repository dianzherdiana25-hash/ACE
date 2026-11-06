"""ACE chat request envelope and real research/runtime worker contract tests."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest

from . import task_runner as task


def basic(mode="research_v03"):
    return {"schema":task.SCHEMA, "request_id":"ace_chat_fixture_001",
            "mode":mode, "tasks":[]}


class ChatRunnerTests(unittest.TestCase):
    def test_predefined_protocol_envelope(self):
        for mode in task.MODES:
            with self.subTest(mode=mode):
                obj=basic(mode)
                if mode=="task_batch":
                    from ace_capability_evolution.compositional import bank
                    t,v,h=bank("equal",20261106)
                    obj["tasks"]=[{"name":"example","train":t,"validation":v,"terminal":h}]
                self.assertEqual(json.loads(task.canonical(obj)),task.parse_request(task.canonical(obj)))

    def test_extraneous_fields_and_invalid_modes(self):
        for changes in ({"additional":1},{"mode":"shell"},{"mode":"eval"},
                        {"request_id":"task with spaces"},{"request_id":True},
                        {"schema":"legacy"}):
            with self.subTest(changes=changes):
                obj={**basic(),**changes}
                with self.assertRaises(task.RequestError):
                    task.parse_request(task.canonical(obj))

    def test_research_cannot_hide_user_data(self):
        obj=basic()
        obj["tasks"]=[{"name":"a","train":[],"validation":[],"terminal":[]}]
        with self.assertRaises(task.RequestError):
            task.parse_request(task.canonical(obj))

    def test_too_many_tasks_and_oversize_request(self):
        obj=basic("task_batch")
        obj["tasks"]=[{}]*5
        with self.assertRaises(task.RequestError):
            task.parse_request(task.canonical(obj))
        with self.assertRaises(task.RequestError):
            task.parse_request(b"x"*(task.MAX_TASK_BYTES+1))

    def test_terminal_overlap_or_type_mismatch(self):
        from ace_capability_evolution.compositional import bank
        train,validation,terminal=bank("equal",20261106)
        x=basic("task_batch")
        x["tasks"]=[{"name":"example","train":train,
                     "validation":validation,"terminal":terminal}]
        self.assertEqual(json.loads(task.canonical(x)),task.parse_request(task.canonical(x)))
        bad=copy.deepcopy(x)
        bad["tasks"][0]["terminal"][0]=train[0]
        with self.assertRaises(task.RequestError):
            task.parse_request(task.canonical(bad))
        bad=copy.deepcopy(x)
        bad["tasks"][0]["train"][0]=[train[0][0],1]
        with self.assertRaises(ValueError):
            task.parse_request(task.canonical(bad))

    def test_runtime_demo_actual_receipts_and_reuse(self):
        obj=basic("runtime_demo")
        with tempfile.TemporaryDirectory() as root:
            receipt=task.execute(obj,workspace=Path(root)/"state")
        self.assertFalse(receipt["candidate_deployed"])
        self.assertEqual("NOT_ASSESSED",receipt["scientific_status"])
        self.assertEqual("BLOCK_RELEASE",receipt["release_decision"])
        self.assertEqual(3,receipt["demo"]["status"]["completed"])
        self.assertEqual(2,receipt["demo"]["status"]["capabilities"])
        self.assertTrue(any(x["phase"]=="REUSE_VALIDATED" for x in receipt["demo"]["outcomes"]))
        self.assertTrue(all(x["correct"]==128 for x in receipt["demo"]["evaluation"].values()))

    def test_runtime_user_batch_real_ace_evaluation(self):
        from ace_capability_evolution.compositional import bank
        train,validation,terminal=bank("equal",20261106)
        obj=basic("task_batch")
        obj["tasks"]=[{"name":"equal_counts","train":train,"validation":validation,
                       "terminal":terminal}]
        obj=task.parse_request(task.canonical(obj))
        with tempfile.TemporaryDirectory() as root:
            receipt=task.execute(obj,workspace=Path(root)/"state")
        self.assertEqual(1,len(receipt["tasks"]))
        self.assertTrue(receipt["tasks"][0]["staged"])
        self.assertEqual(128,receipt["tasks"][0]["terminal"]["correct"])
        self.assertEqual(1,receipt["runtime"]["capabilities"])

    def test_public_research_baseline_never_claims_novelty(self):
        obj=task.parse_request(task.canonical(basic()))
        with tempfile.TemporaryDirectory() as root:
            result=task.execute(obj,workspace=Path(root)/"state")
        self.assertEqual(24,result["research"]["trial_count"])
        self.assertFalse(result["research"]["beats_fixed_library"])
        self.assertFalse(result["research"]["open_world_safe"])
        self.assertFalse(result["research"]["compute_matched"])
        self.assertFalse(result["oaie_established"])
        self.assertEqual(64,len(result["research"]["full_report_sha256"]))
        self.assertEqual(24,len(result["_research_evidence"]["trials"]))

    def test_identical_complete_run_digest_and_staging(self):
        obj=basic("runtime_demo")
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            first=task.execute(obj,workspace=Path(a)/"state")
            second=task.execute(obj,workspace=Path(b)/"state")
        self.assertEqual(task.canonical(first),task.canonical(second))
        self.assertEqual(first["request_sha256"],task.sha256(task.canonical(obj)))


if __name__=="__main__":
    unittest.main()
