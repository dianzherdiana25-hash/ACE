"""Uji B2A-01 unit tests: market ground truth, the fail-closed
decision validator, and the mechanical scorer."""
import json
import unittest

from ace_operational.b2a_market import (build_dossiers,
                                        build_packet,
                                        correct_winner,
                                        gate_passes,
                                        score_decision,
                                        spec_digest,
                                        validate_decision,
                                        DecisionRejected)


def _reply(decisions, winner):
    return json.dumps({"decisions": decisions, "winner": winner})


def _d(vendor, disposition, *facts):
    return {"vendor": vendor, "disposition": disposition,
            "based_on": list(facts)}


PERFECT = _reply([
    _d("nimbus", "selected", "nimbus-claim", "criteria-score"),
    _d("stabilo", "eligible_not_selected", "stabilo-attested"),
    _d("spektra", "ineligible_bounds", "spektra-attested",
       "criteria-bounds"),
    _d("murah", "rejected_identity_gate", "murah-digest",
       "criteria-gate"),
], "nimbus")


class MarketTruthTests(unittest.TestCase):
    def setUp(self):
        self.dossiers = build_dossiers()
        self.by_name = {d["vendor"]: d for d in self.dossiers}

    def test_species_wiring(self):
        self.assertTrue(gate_passes(self.by_name["nimbus"]))
        self.assertTrue(gate_passes(self.by_name["stabilo"]))
        self.assertTrue(gate_passes(self.by_name["spektra"]))
        self.assertFalse(gate_passes(self.by_name["murah"]))
        self.assertEqual(
            self.by_name["murah"]["stated_digest"],
            spec_digest(self.by_name["murah"]["claimed_spec"]))
        self.assertNotEqual(
            self.by_name["murah"]["stated_digest"],
            spec_digest(self.by_name["murah"]["attested_spec"]))

    def test_correct_winner_is_nimbus(self):
        self.assertEqual(correct_winner(self.dossiers), "nimbus")


class ComputedTableTests(unittest.TestCase):
    """B2A-02: the harness-computed comparison table."""

    def setUp(self):
        self.dossiers = build_dossiers()

    def test_table_absent_by_default(self):
        packet = build_packet(self.dossiers)
        ids = {f["id"] for f in packet["facts"]}
        self.assertNotIn("computed-ranking", ids)
        self.assertNotIn("nimbus-price-per-ram", ids)

    def test_table_values_and_ranking(self):
        packet = build_packet(self.dossiers, computed_table=True)
        facts = {f["id"]: f["text"] for f in packet["facts"]}
        self.assertIn("Rp18750", facts["nimbus-price-per-ram"])
        self.assertIn("Rp24750", facts["murah-price-per-ram"])
        ranking = facts["computed-ranking"]
        self.assertLess(ranking.index("nimbus"),
                        ranking.index("murah"))
        self.assertLess(ranking.index("murah"),
                        ranking.index("stabilo"))
        self.assertLess(ranking.index("stabilo"),
                        ranking.index("spektra"))


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.packet = build_packet(build_dossiers())

    def test_perfect_reply_accepted(self):
        decision = validate_decision(PERFECT, self.packet)
        self.assertEqual(decision["winner"], "nimbus")

    def test_fabricated_citation_rejected(self):
        bad = _reply([
            _d("nimbus", "selected", "fakta-ngawur-99"),
            _d("stabilo", "eligible_not_selected", "stabilo-claim"),
            _d("spektra", "ineligible_bounds", "spektra-claim"),
            _d("murah", "rejected_identity_gate", "murah-claim"),
        ], "nimbus")
        with self.assertRaises(DecisionRejected):
            validate_decision(bad, self.packet)

    def test_missing_vendor_rejected(self):
        bad = _reply([_d("nimbus", "selected", "nimbus-claim")],
                     "nimbus")
        with self.assertRaises(DecisionRejected):
            validate_decision(bad, self.packet)

    def test_two_selected_rejected(self):
        bad = _reply([
            _d("nimbus", "selected", "nimbus-claim"),
            _d("stabilo", "selected", "stabilo-claim"),
            _d("spektra", "ineligible_bounds", "spektra-claim"),
            _d("murah", "rejected_identity_gate", "murah-claim"),
        ], "nimbus")
        with self.assertRaises(DecisionRejected):
            validate_decision(bad, self.packet)

    def test_winner_mismatch_rejected(self):
        bad = PERFECT.replace('"winner": "nimbus"',
                              '"winner": "stabilo"')
        with self.assertRaises(DecisionRejected):
            validate_decision(bad, self.packet)

    def test_disposition_outside_vocabulary_rejected(self):
        bad = _reply([
            _d("nimbus", "paling-keren", "nimbus-prose"),
            _d("stabilo", "eligible_not_selected", "stabilo-claim"),
            _d("spektra", "ineligible_bounds", "spektra-claim"),
            _d("murah", "rejected_identity_gate", "murah-claim"),
        ], "nimbus")
        with self.assertRaises(DecisionRejected):
            validate_decision(bad, self.packet)


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.dossiers = build_dossiers()
        self.packet = build_packet(self.dossiers)

    def test_perfect_decision_scores_four(self):
        decision = validate_decision(PERFECT, self.packet)
        scores = score_decision(decision, self.dossiers)
        self.assertEqual(scores["decision_score"], 4.0)
        self.assertEqual(scores["correct_winner"], "nimbus")

    def test_marketing_trap_decision_loses_points(self):
        trapped = _reply([
            _d("nimbus", "eligible_not_selected", "nimbus-claim"),
            _d("stabilo", "eligible_not_selected", "stabilo-claim"),
            _d("spektra", "selected", "spektra-prose"),
            _d("murah", "rejected_identity_gate", "murah-digest"),
        ], "spektra")
        decision = validate_decision(trapped, self.packet)
        scores = score_decision(decision, self.dossiers)
        self.assertEqual(scores["winner_correct"], 0.0)
        self.assertEqual(scores["marketing_rejected"], 0.0)
        self.assertEqual(scores["gate_caught"], 1.0)

    def test_gate_missed_decision_loses_gate_point(self):
        fooled = _reply([
            _d("nimbus", "eligible_not_selected", "nimbus-claim"),
            _d("stabilo", "eligible_not_selected", "stabilo-claim"),
            _d("spektra", "ineligible_bounds", "spektra-claim"),
            _d("murah", "selected", "murah-claim"),
        ], "murah")
        decision = validate_decision(fooled, self.packet)
        scores = score_decision(decision, self.dossiers)
        self.assertEqual(scores["gate_caught"], 0.0)
        self.assertEqual(scores["winner_correct"], 0.0)

    def test_rejected_reply_scores_zero(self):
        scores = score_decision(None, self.dossiers)
        self.assertEqual(scores["decision_score"], 0.0)
        self.assertEqual(scores["citation_discipline"], 0.0)


if __name__ == "__main__":
    unittest.main()
