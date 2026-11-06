"""Adversarial checks: a green science verification must still block release."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ace_science_release_gate as gate


class ScienceReleaseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths={name:Path(os.environ["ACE_"+name.upper()+"_EVIDENCE"])
                   for name in ("h7","r1","r8")}
        cls.docs={name:gate.pinned(path,name) for name,path in cls.paths.items()}

    def test_original_h7_independent_replay(self):
        report=gate.audit_h7(self.docs["h7"])
        self.assertEqual(report["h7_worlds_independently_recomputed"],24)
        self.assertEqual(report["h7_terminal_predictions_recomputed"],12288)

    def test_three_lane_evidence_is_blocked_for_science(self):
        decision=gate.assess(self.docs["h7"],self.docs["r1"],self.docs["r8"])
        self.assertEqual(decision["engineering_evidence"],"PASS_INDEPENDENT_PUBLIC_REPLAY")
        self.assertEqual(decision["promotion_decision"],"BLOCK_RELEASE")
        self.assertEqual(decision["scientific_decision"],"NOT_ASSESSED")

    def test_forged_per_task_performance_rejected(self):
        forged=copy.deepcopy(self.docs["h7"])
        forged["rows"][16]["methods"]["h7"]["balanced"]["correct"]=256
        with self.assertRaisesRegex(gate.IntegrityHalt,"forged h7/balanced score"):
            gate.audit_h7(forged)

    def test_high_natural_accuracy_does_not_create_a_new_feature(self):
        forged=copy.deepcopy(self.docs["h7"])
        forged["rows"][17]["h7_representation"]["accepted"]=True
        with self.assertRaisesRegex(gate.IntegrityHalt,"false source H7 feature"):
            gate.audit_h7(forged)

    def test_forged_abstention_receipt_rejected(self):
        forged=copy.deepcopy(self.docs["h7"])
        forged["rows"][9]["semantic_final_abstentions"]=512
        with self.assertRaisesRegex(gate.IntegrityHalt,"fake semantic abstention"):
            gate.audit_h7(forged)

    def test_summary_accuracy_inflation_rejected(self):
        forged=copy.deepcopy(self.docs["h7"])
        forged["summary"]["by_length"]["7"]["methods"]["h7"]["balanced_accuracy"]=0.932617
        with self.assertRaisesRegex(gate.IntegrityHalt,"fake precision"):
            gate.audit_h7(forged)

    def test_promoted_open_world_gate_rejected(self):
        forged=copy.deepcopy(self.docs["h7"])
        forged["summary"]["precommitted_gates"]["G4_open_world_safe_to_deploy"]=True
        with self.assertRaisesRegex(gate.IntegrityHalt,"science gate changed"):
            gate.audit_h7(forged)

    def test_r8_zero_false_pass_claim_rejected(self):
        changed=copy.deepcopy(self.docs["r8"])
        changed["counts"]["public_screen_pass"]=0
        with patch.object(gate,"audit_h7",return_value={"test":True}):
            with self.assertRaisesRegex(gate.IntegrityHalt,"R8 null"):
                gate.assess(self.docs["h7"],self.docs["r1"],changed)

    def test_r1_unverified_drift_promotion_rejected(self):
        changed=copy.deepcopy(self.docs["r1"])
        changed["metrics"]["unprotected_drift_tasks"]=0
        with patch.object(gate,"audit_h7",return_value={"test":True}):
            with self.assertRaisesRegex(gate.IntegrityHalt,"R1 claimed"):
                gate.assess(self.docs["h7"],changed,self.docs["r8"])

    def test_pinned_evidence_bytes_detect_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            fp=Path(d)/"h7.json"
            fp.write_bytes(self.paths["h7"].read_bytes()+b" ")
            with self.assertRaisesRegex(gate.IntegrityHalt,"SHA256 mismatch"):
                gate.pinned(fp,"h7")

    def test_missing_receipt_halts_instead_of_assuming_no_regression(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(gate.main(["--h7",str(Path(d)/"missing.json"),
                                        "--r1",str(self.paths["r1"]),
                                        "--r8",str(self.paths["r8"])]),2)


if __name__=="__main__":
    unittest.main()
