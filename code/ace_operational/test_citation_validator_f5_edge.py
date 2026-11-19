"""F5 — tes tepi tebal untuk citation_validator (kasus tambahan di luar
suite dasar V-1…V-6): bentuk paket alternatif, presedensi field sitasi,
koersi tipe, digest yang peka-urutan vs himpunan yang tak peka-urutan,
dan rantai ledger pada kondisi batas. Tes saja — tanpa mengubah modul.
"""
from __future__ import annotations

import unittest

from ace_operational.citation_validator import (
    CitationValidatorError,
    PacketBindingError,
    RejectionLedger,
    canonical_report_bytes,
    citable_id_set_digest,
    packet_digest,
    packet_fact_ids,
    validate_reply,
    validator_identity,
)

TS = 1762920000.0

PACKET = {"fact_ids": ["alpha", "beta", "gamma"]}


class TestPacketShapes(unittest.TestCase):
    def test_bare_list_packet_sorted_and_deduped(self):
        self.assertEqual(packet_fact_ids(["beta", "alpha", "beta", "gamma"]),
                         ["alpha", "beta", "gamma"])

    def test_tuple_and_set_packets_accepted(self):
        self.assertEqual(packet_fact_ids(("b", "a")), ["a", "b"])
        self.assertEqual(packet_fact_ids({"b", "a"}), ["a", "b"])

    def test_non_iterable_packet_rejected(self):
        with self.assertRaises(CitationValidatorError):
            packet_fact_ids(42)

    def test_fact_ids_coerced_to_str_and_deduped(self):
        self.assertEqual(packet_fact_ids({"fact_ids": [1, "1", 2]}), ["1", "2"])

    def test_observation_packet_with_partial_sections(self):
        self.assertEqual(packet_fact_ids({"open_gaps": [{"id": "g1"}]}), ["g1"])
        self.assertEqual(packet_fact_ids({"gates": {"G1": "PASS"}}), ["G1"])
        self.assertEqual(packet_fact_ids({}), [])

    def test_empty_packet_rejects_every_citing_proposal(self):
        report = validate_reply(packet={"fact_ids": []},
                                proposals=[{"based_on": ["alpha"]},
                                           {"cites": ["beta"]}],
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0, 1])
        self.assertEqual(report["citable_fact_ids"], [])


class TestCitationFieldSemantics(unittest.TestCase):
    def test_based_on_takes_precedence_over_cites_even_when_empty(self):
        # Kehadiran field menentukan, bukan isi: based_on=[] menang atas
        # cites yang sah, sehingga proposal ditolak no_citations.
        report = validate_reply(packet=PACKET,
                                proposals=[{"based_on": [], "cites": ["alpha"]}],
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])
        self.assertEqual(report["rejections"][0]["reason"], "no_citations")

    def test_cites_used_when_based_on_absent(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"cites": ["alpha", "beta"]}],
                                timestamp=TS)
        self.assertEqual(report["accepted_proposals"], [0])

    def test_proposal_without_any_citation_field_rejected(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"title": "tanpa sitasi"}],
                                timestamp=TS)
        self.assertEqual(report["rejected_proposals"], [0])
        self.assertIsNone(report["rejections"][0]["status"])
        self.assertIsNone(report["rejections"][0]["fact_id"])

    def test_non_dict_proposal_rejected_as_malformed(self):
        with self.assertRaises(CitationValidatorError):
            validate_reply(packet=PACKET, proposals=["bukan-objek"], timestamp=TS)

    def test_non_list_citation_field_rejected_as_malformed(self):
        with self.assertRaises(CitationValidatorError):
            validate_reply(packet=PACKET,
                           proposals=[{"based_on": "alpha"}], timestamp=TS)

    def test_non_string_citations_coerced_to_str(self):
        report = validate_reply(packet={"fact_ids": ["123"]},
                                proposals=[{"based_on": [123]}], timestamp=TS)
        self.assertEqual(report["accepted_proposals"], [0])
        self.assertEqual(report["citation_surface"][0]["citations"],
                         [{"fact_id": "123", "status": "known"}])

    def test_duplicate_unknown_citations_each_produce_a_rejection(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"based_on": ["ghost", "ghost"]}],
                                timestamp=TS)
        self.assertEqual([r["fact_id"] for r in report["rejections"]],
                         ["ghost", "ghost"])
        self.assertEqual(len(report["citation_surface"][0]["citations"]), 2)

    def test_empty_reply_validates_to_empty_report(self):
        report = validate_reply(packet=PACKET, proposals=[], timestamp=TS)
        self.assertEqual(report["citation_surface"], [])
        self.assertEqual(report["rejections"], [])
        self.assertEqual(report["accepted_proposals"], [])
        self.assertFalse(report["legacy_whole_reply_rejected"])


class TestProposalIdFallback(unittest.TestCase):
    def test_title_used_when_id_missing_or_blank(self):
        report = validate_reply(
            packet=PACKET,
            proposals=[{"title": "Judul A", "based_on": ["ghost"]},
                       {"id": "   ", "title": "Judul B", "based_on": ["ghost"]},
                       {"id": 7, "title": "Judul C", "based_on": ["ghost"]}],
            timestamp=TS)
        self.assertEqual([r["proposal_id"] for r in report["rejections"]],
                         ["Judul A", "Judul B", "Judul C"])

    def test_proposal_id_none_when_no_id_and_no_title(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"based_on": ["ghost"]}],
                                timestamp=TS)
        self.assertIsNone(report["rejections"][0]["proposal_id"])


class TestDigestNuances(unittest.TestCase):
    def test_packet_digest_is_order_sensitive_but_id_set_digest_is_not(self):
        a = {"fact_ids": ["alpha", "beta"]}
        b = {"fact_ids": ["beta", "alpha"]}
        self.assertNotEqual(packet_digest(a), packet_digest(b))
        self.assertEqual(citable_id_set_digest(packet_fact_ids(a)),
                         citable_id_set_digest(packet_fact_ids(b)))

    def test_binding_refuses_reordered_packet(self):
        # Binding adalah atas objek paket persis (V-3): urutan berbeda
        # berarti digest berbeda berarti penolakan keras.
        with self.assertRaises(PacketBindingError):
            validate_reply(packet={"fact_ids": ["beta", "alpha"]},
                           proposals=[{"based_on": ["alpha"]}],
                           expected_packet_digest=packet_digest(
                               {"fact_ids": ["alpha", "beta"]}),
                           timestamp=TS)

    def test_unicode_fact_ids_round_trip(self):
        packet = {"fact_ids": ["café-id"]}
        report = validate_reply(packet=packet,
                                proposals=[{"based_on": ["café-id"]}],
                                timestamp=TS)
        self.assertEqual(report["accepted_proposals"], [0])
        self.assertEqual(packet_digest(packet), packet_digest(dict(packet)))

    def test_different_timestamp_changes_canonical_bytes(self):
        base = dict(packet=PACKET, proposals=[{"based_on": ["alpha"]}])
        first = validate_reply(**base, timestamp=TS)
        second = validate_reply(**base, timestamp=TS + 1)
        self.assertNotEqual(canonical_report_bytes(first),
                            canonical_report_bytes(second))

    def test_default_timestamp_is_wall_clock_float(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"based_on": ["alpha"]}])
        self.assertIsInstance(report["timestamp"], float)
        self.assertGreater(report["timestamp"], TS)


class TestLedgerBoundaries(unittest.TestCase):
    def test_empty_ledger_verifies_clean(self):
        result = RejectionLedger().verify()
        self.assertEqual(result, {"status": "CLEAN", "entries_verified": 0,
                                  "chain_break_at": None})

    def test_append_returns_chained_entry(self):
        ledger = RejectionLedger()
        entry = ledger.append({"fact_id": "ghost"})
        self.assertEqual(entry["seq"], 1)
        self.assertEqual(entry["prev"], "GENESIS")
        self.assertEqual(len(entry["hash"]), 64)
        self.assertEqual(ledger.entries, [entry])

    def test_ledger_continues_from_preloaded_entries(self):
        first = RejectionLedger()
        first.append({"fact_id": "a"})
        resumed = RejectionLedger(entries=first.entries)
        entry = resumed.append({"fact_id": "b"})
        self.assertEqual(entry["seq"], 2)
        self.assertEqual(entry["prev"], first.entries[0]["hash"])
        self.assertEqual(resumed.verify()["status"], "CLEAN")

    def test_tampered_seq_breaks_chain(self):
        ledger = RejectionLedger()
        ledger.append({"fact_id": "a"})
        ledger.append({"fact_id": "b"})
        ledger.entries[1]["seq"] = 99
        result = ledger.verify()
        self.assertEqual(result["status"], "BROKEN")
        self.assertEqual(result["chain_break_at"], 2)
        self.assertEqual(result["entries_verified"], 1)

    def test_tampered_hash_breaks_chain(self):
        ledger = RejectionLedger()
        ledger.append({"fact_id": "a"})
        ledger.entries[0]["hash"] = "0" * 64
        result = ledger.verify()
        self.assertEqual(result["status"], "BROKEN")
        self.assertEqual(result["chain_break_at"], 1)

    def test_append_report_with_no_rejections_seals_nothing(self):
        report = validate_reply(packet=PACKET,
                                proposals=[{"based_on": ["alpha"]}],
                                timestamp=TS)
        ledger = RejectionLedger()
        self.assertEqual(ledger.append_report(report), [])
        self.assertEqual(ledger.verify()["entries_verified"], 0)


class TestIdentityStability(unittest.TestCase):
    def test_identity_digest_fields_are_hex_sha256(self):
        identity = validator_identity()
        for key in ("ruleset_digest", "code_digest"):
            self.assertEqual(len(identity[key]), 64)
            int(identity[key], 16)  # meledak bila bukan hex


if __name__ == "__main__":
    unittest.main()
