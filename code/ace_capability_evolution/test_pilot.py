"""Cross-lane multi-generation pilot mechanics, falsifiers and provenance."""
import copy
import json
import unittest
from . import pilot, verify


class PilotContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ace_research_primitives import primitive_discovery as r1
        from ace_candidate_search import search as s2search
        from ace_candidate_search import model as s2model
        cls.r1,cls.search,cls.model=r1,s2search,s2model
        cls.report=pilot.run_pilot(r1,s2search,s2model)
        cls.data=pilot.canonical(cls.report)

    def test_sequence_splits_and_holdout_disjoint(self):
        for i,name in enumerate(("a_mod4","b_mod4","late_rule_inversion")):
            bank=pilot.sequence_bank(name,0 if i==2 else i)
            self.assertEqual([63,192,256],[len(bank[k]) for k in ("train","validation","terminal")])
            wordsets=[set(w for w,_ in bank[k]) for k in ("train","validation","terminal")]
            self.assertFalse(wordsets[0]&wordsets[1])
            self.assertFalse(wordsets[0]&wordsets[2])
            self.assertFalse(wordsets[1]&wordsets[2])

    def test_arithmetic_disjoint_and_bounded(self):
        for i,name in enumerate(("x_minus_y","product_plus_two")):
            bank=pilot.arithmetic_bank(name,i,self.model)
            self.assertEqual([6,4,16],[len(bank[k]) for k in ("train","validation","terminal")])
            coordinates=[(z.x,z.y) for part in bank.values() for z in part]
            self.assertEqual(len(coordinates),len(set(coordinates)))
            self.assertTrue(all(-7<=x<=7 and -7<=y<=7 for x,y in coordinates))

    def test_drift_world_indistinguishable_until_terminal(self):
        stable=pilot.sequence_bank("a_mod4",0)
        drift=pilot.sequence_bank("late_rule_inversion",0)
        self.assertEqual(stable["train"],drift["train"])
        self.assertEqual(stable["validation"],drift["validation"])
        self.assertEqual([not y for _,y in stable["terminal"]],
                         [y for _,y in drift["terminal"]])

    def test_three_generations_and_no_live_promotion(self):
        self.assertEqual([0,1,2],[x["generation"] for x in self.report["generations"]])
        self.assertEqual(4,len(self.report["tasks"]))
        self.assertEqual("BLOCK_RELEASE",self.report["release_decision"])
        self.assertEqual("NOT_ASSESSED",self.report["scientific_status"])
        self.assertIs(self.report["candidate_deployed"],False)
        self.assertIs(self.report["oaie_not_established"],True)

    def test_all_sources_pinned_and_models_immutable(self):
        self.assertEqual({"R1":pilot.R1_HEAD,"S2":pilot.S2_HEAD},self.report["pinned_sources"])
        self.assertEqual(pilot.PROTOCOL,self.report["protocol_commit"])
        for r in self.report["tasks"]:
            self.assertEqual(64,len(r["model_fingerprint"]))
            self.assertIs(type(r["staged"]),bool)
            if r["domain"]=="arithmetic":
                self.assertLessEqual(r["searched_candidates"],800)
                self.assertLessEqual(r["search_work"],100000)
            if r["domain"]=="sequence":
                self.assertLessEqual(r["merges"],10000)
        for gen in self.report["generations"][1:]:
            self.assertTrue(gen["retention"]["validation_retested_without_refit"])

    def test_terminal_not_used_for_staging(self):
        for row in self.report["tasks"]:
            self.assertIn(row["stage_reason"],("validation_gain","validation_gate_not_met"))
            self.assertEqual(row["terminal"]["total"],256 if row["domain"]=="sequence" else 16)
        self.assertIs(self.report["gates"]["G4_indistinguishable_drift_safely_detected"],False)

    def test_canonical_determinism(self):
        rerun=pilot.run_pilot(self.r1,self.search,self.model)
        self.assertEqual(self.data,pilot.canonical(rerun))

    def test_full_receipt_independent_rerun_accepts(self):
        receipt=verify.verify_bytes(self.data,self.r1,self.search,self.model)
        self.assertEqual("PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO",receipt["decision"])

    def test_forged_staged_decision_is_rejected(self):
        bad=copy.deepcopy(self.report)
        bad["tasks"][0]["staged"]=not bad["tasks"][0]["staged"]
        with self.assertRaises(verify.EvidenceError):
            verify.verify_bytes(pilot.canonical(bad),self.r1,self.search,self.model)

    def test_forged_terminal_score_is_rejected(self):
        bad=copy.deepcopy(self.report)
        bad["tasks"][0]["terminal"]["candidate_correct"]+=1
        with self.assertRaises(verify.EvidenceError):
            verify.verify_bytes(pilot.canonical(bad),self.r1,self.search,self.model)

    def test_false_bool_int_alias_rejected(self):
        bad=copy.deepcopy(self.report)
        bad["candidate_deployed"]=0
        with self.assertRaises(verify.EvidenceError):
            verify.verify_bytes(pilot.canonical(bad),self.r1,self.search,self.model)

    def test_forged_promotion_rejected(self):
        bad=copy.deepcopy(self.report)
        bad["scientific_status"]="ACCEPTED"
        bad["release_decision"]="ALLOW_RELEASE"
        with self.assertRaises(verify.EvidenceError):
            verify.verify_bytes(pilot.canonical(bad),self.r1,self.search,self.model)

    def test_noncanonical_json_rejected(self):
        raw=json.dumps(self.report).encode()
        with self.assertRaises(verify.EvidenceError):
            verify.verify_bytes(raw,self.r1,self.search,self.model)


if __name__=="__main__":
    unittest.main()
