"""Bake-off 02 tests for the hardened citation validator (design §2).

These pin V-1…V-6: per-fact-id granularity with per-proposal
survival, the structured ``ace.citation_rejection.v1`` record,
packet binding, the pinned validator identity, the hash-chained
rejection ledger, and deterministic replay — including the
regression fixture bake-off 01 earned: a reply in which one
decision cites the fabricated id ``nimbus-gate``, the exact shape
whose whole-reply rejection scored a candidate 0/4.
"""
from __future__ import annotations

import unittest

from ace_operational.citation_validator import (
    PacketBindingError,
    RejectionLedger,
    canonical_report_bytes,
    citable_id_set_digest,
    packet_digest,
    packet_fact_ids,
    validate_reply,
    validator_identity,
)

TS = 1762920000.0  # pinned timestamp: replay must not depend on the clock

# A B2A-style dossier packet (instrument B surface). Note what is
# NOT here: any "nimbus-gate" fact — that absence is the fixture.
DOSSIER_PACKET = {
    "fact_ids": ["stabilo-price", "stabilo-stock", "stabilo-lead",
                 "nimbus-price", "nimbus-stock", "nimbus-lead",
                 "budget-cap", "delivery-window"],
}

# The bake-off 01 failure shape, rebuilt: decision 0 cites a valid
# id set plus the one fabricated id; decisions 1 and 2 cite only
# facts the packet actually offered.
BAKEOFF01_REPLY = [
    {"id": "decision-0", "cites": ["nimbus-price", "nimbus-gate"]},
    {"id": "decision-1", "cites": ["stabilo-price", "stabilo-stock"]},
    {"id": "decision-2", "cites": ["budget-cap", "delivery-window"]},
]


class TestPerFactIdGranularity(unittest.TestCase):
    """V-1: every id enumerated; only offending proposals rejected."""

    def test_only_offending_proposal_rejected_rest_survive(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY,
                                experiment_id="brain-bakeoff-02",
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])
        self.assertEqual(report["accepted_proposals"], [1, 2])

    def test_surface_enumerates_every_cited_id_of_every_proposal(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY, timestamp=TS)
        surface = report["citation_surface"]
        self.assertEqual(len(surface), 3)
        self.assertEqual(surface[0]["citations"],
                         [{"fact_id": "nimbus-price", "status": "known"},
                          {"fact_id": "nimbus-gate", "status": "unknown"}])
        self.assertTrue(all(
            e["status"] == "known"
            for s in surface[1:] for e in s["citations"]))

    def test_multi_fabrication_all_unknown_ids_enumerated(self):
        reply = [{"based_on": ["stabilo-price", "ghost-a", "ghost-b"]},
                 {"based_on": ["nimbus-price"]}]
        report = validate_reply(packet=DOSSIER_PACKET, proposals=reply,
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])
        self.assertEqual(report["accepted_proposals"], [1])
        offending = [r["fact_id"] for r in report["rejections"]]
        self.assertEqual(offending, ["ghost-a", "ghost-b"])

    def test_proposal_citing_nothing_is_rejected(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=[{"based_on": []},
                                           {"based_on": ["nimbus-price"]}],
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])
        self.assertEqual(report["rejections"][0]["reason"], "no_citations")
        self.assertIsNone(report["rejections"][0]["fact_id"])

    def test_all_known_citations_accept_whole_reply(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY[1:], timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [])
        self.assertEqual(report["rejections"], [])
        self.assertFalse(report["legacy_whole_reply_rejected"])


class TestStructuredRejectionObject(unittest.TestCase):
    """V-2: rejections are versioned schema objects, not strings."""

    def test_rejection_object_fields(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY,
                                experiment_id="brain-bakeoff-02",
                                timestamp=TS)
        self.assertEqual(len(report["rejections"]), 1)
        rej = report["rejections"][0]
        self.assertEqual(rej["schema"], "ace.citation_rejection.v1")
        self.assertEqual(rej["experiment_id"], "brain-bakeoff-02")
        self.assertEqual(rej["proposal_index"], 0)
        self.assertEqual(rej["proposal_id"], "decision-0")
        self.assertEqual(rej["fact_id"], "nimbus-gate")
        self.assertEqual(rej["status"], "unknown")
        self.assertEqual(rej["reason"], "unknown_fact_id")
        self.assertEqual(rej["packet_digest"], report["packet_digest"])
        self.assertEqual(rej["citable_id_set_digest"],
                         citable_id_set_digest(
                             packet_fact_ids(DOSSIER_PACKET)))
        self.assertEqual(rej["timestamp"], TS)
        self.assertEqual(rej["validator"]["name"], "ace.citation_validator")


class TestPacketBinding(unittest.TestCase):
    """V-3: validation is bound to the exact packet."""

    def test_pinned_digest_match_validates(self):
        report = validate_reply(
            packet=DOSSIER_PACKET, proposals=BAKEOFF01_REPLY,
            expected_packet_digest=packet_digest(DOSSIER_PACKET),
            timestamp=TS)
        self.assertEqual(report["packet_digest"],
                         packet_digest(DOSSIER_PACKET))

    def test_pinned_digest_mismatch_is_refused(self):
        other = {"fact_ids": ["stabilo-price"]}
        with self.assertRaises(PacketBindingError):
            validate_reply(packet=DOSSIER_PACKET, proposals=BAKEOFF01_REPLY,
                           expected_packet_digest=packet_digest(other),
                           timestamp=TS)

    def test_observation_packet_ids_derived_like_director_loop(self):
        observation = {
            "gates": {"G0": "PASS", "G1": "NOT_ASSESSED"},
            "open_gaps": [{"id": "gap-a"}],
            "recent_results": [{"id": "res-1"}],
        }
        self.assertEqual(packet_fact_ids(observation),
                         ["G0", "G1", "gap-a", "res-1"])
        report = validate_reply(
            packet=observation,
            proposals=[{"based_on": ["gap-a", "G2"]}], timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])


class TestValidatorIdentity(unittest.TestCase):
    """V-4: the validator's identity is pinnable and carried."""

    def test_identity_fields_present_and_stable(self):
        identity = validator_identity()
        self.assertEqual(identity["name"], "ace.citation_validator")
        self.assertEqual(identity["version"], "1.0.0")
        self.assertEqual(identity["schema"], "ace.citation_rejection.v1")
        self.assertEqual(len(identity["ruleset_digest"]), 64)
        self.assertEqual(len(identity["code_digest"]), 64)
        self.assertEqual(validator_identity(), identity)

    def test_identity_carried_in_report_and_rejections(self):
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY, timestamp=TS)
        self.assertEqual(report["validator"], validator_identity())
        self.assertEqual(report["rejections"][0]["validator"],
                         validator_identity())


class TestRejectionLedger(unittest.TestCase):
    """V-5: sealed rejection entries form a verifiable hash chain."""

    def _sealed(self):
        ledger = RejectionLedger()
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY, timestamp=TS)
        ledger.append_report(report)
        multi = validate_reply(
            packet=DOSSIER_PACKET,
            proposals=[{"based_on": ["ghost-a", "ghost-b"]}], timestamp=TS)
        ledger.append_report(multi)
        return ledger

    def test_chain_verifies_clean(self):
        ledger = self._sealed()
        self.assertEqual(len(ledger.entries), 3)
        result = ledger.verify()
        self.assertEqual(result["status"], "CLEAN")
        self.assertEqual(result["entries_verified"], 3)
        self.assertEqual(ledger.entries[0]["prev"], "GENESIS")
        self.assertEqual(ledger.entries[1]["prev"],
                         ledger.entries[0]["hash"])

    def test_tampered_record_breaks_chain_at_that_entry(self):
        ledger = self._sealed()
        ledger.entries[1]["record"]["fact_id"] = "nimbus-price"
        result = ledger.verify()
        self.assertEqual(result["status"], "BROKEN")
        self.assertEqual(result["chain_break_at"], 2)

    def test_tampered_prev_link_breaks_chain(self):
        ledger = self._sealed()
        ledger.entries[2]["prev"] = "0" * 64
        result = ledger.verify()
        self.assertEqual(result["status"], "BROKEN")
        self.assertEqual(result["chain_break_at"], 3)


class TestDeterministicReplay(unittest.TestCase):
    """V-6: same packet + reply + timestamp → byte-identical report."""

    def test_replay_is_byte_identical(self):
        first = validate_reply(packet=DOSSIER_PACKET,
                               proposals=BAKEOFF01_REPLY,
                               experiment_id="brain-bakeoff-02",
                               timestamp=TS)
        second = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY,
                                experiment_id="brain-bakeoff-02",
                                timestamp=TS)
        self.assertEqual(canonical_report_bytes(first),
                         canonical_report_bytes(second))

    def test_bakeoff01_regression_fixture(self):
        """The fabricated id is unknown under any granularity, the
        legacy whole-reply rule would still have rejected the reply
        (bake-off 01's outcome unchanged) — and under the hardened
        semantics the clean decisions survive to be scored."""
        report = validate_reply(packet=DOSSIER_PACKET,
                                proposals=BAKEOFF01_REPLY,
                                experiment_id="brain-bakeoff-01-replay",
                                timestamp=TS)
        self.assertEqual([r["fact_id"] for r in report["rejections"]],
                         ["nimbus-gate"])
        self.assertTrue(report["legacy_whole_reply_rejected"])
        self.assertEqual(report["accepted_proposals"], [1, 2])


if __name__ == "__main__":
    unittest.main()
