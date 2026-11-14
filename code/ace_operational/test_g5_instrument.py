"""Synthetic tests for the G5 instrument
(ace_operational.g5_instrument).

Every fixture is invented: synthetic summaries written
by synthetic authors and synthetic owner messages about
them. No real chat content appears anywhere in this
file, even anonymised (brief Task 12a section 8).

Run directly:
    PYTHONPATH=code python3 \
        code/ace_operational/test_g5_instrument.py
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ace_operational.g5_instrument import assess_g5

PERIOD_START = "2026-11-12T19:00:00+07:00"
PERIOD_END = "2026-11-13T19:00:00+07:00"
UNIT_TS = "2026-11-12T20:00:00+07:00"
EVENT_TS = "2026-11-12T21:00:00+07:00"


def _canonical(data) -> str:
    blob = json.dumps(data, sort_keys=True,
                      separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _unit(unit_id, *, fields=None, delivered=True,
          contained=True, timestamp=UNIT_TS):
    rubric = {"dicoba": True, "hasil": True,
              "keyakinan": True, "batas": True}
    if fields:
        rubric.update(fields)
    return {
        "unit_id": unit_id,
        "message_ref": f"synthetic-msg-{unit_id}",
        "timestamp": timestamp,
        "author_id": "ila-main",
        "content_digest": hashlib.sha256(
            f"invented summary text {unit_id}".encode()
        ).hexdigest(),
        "fields": rubric,
        "delivered_in_channel": delivered,
        "self_contained": contained,
    }


def _units(count, **kwargs):
    return [_unit(f"u-{i + 1:03d}", **kwargs)
            for i in range(count)]


def _event(event_id, *, unit="u-001", action="decision",
           domain="operations", timestamp=EVENT_TS):
    return {
        "event_id": event_id,
        "message_ref": f"synthetic-msg-{event_id}",
        "timestamp": timestamp,
        "content_digest": hashlib.sha256(
            f"invented owner message {event_id}".encode()
        ).hexdigest(),
        "references_unit": unit,
        "action_type": action,
        "domain": domain,
    }


def _qualifying_events():
    return [
        _event("e-001", unit="u-001", action="decision",
               domain="operations"),
        _event("e-002", unit="u-002", action="correction",
               domain="finance"),
        _event("e-003", unit="u-001", action="direction",
               domain="operations"),
    ]


def _harvest(**overrides):
    report = {
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "c1_threshold": 0.90,
        "c2_threshold": 0.90,
        "c3_min_events": 3,
        "c3_min_domains": 2,
        "c3_requires_correction": True,
        "harvester_id": "ops-post",
        "summary_author_ids": ["ila-main", "ila-bench"],
    }
    report.update(overrides)
    return report


class AssessG5Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_dossier(self, units, events, harvest=None,
                      *, seal=True):
        units_data = {"units": units}
        events_data = {"events": events}
        report = _harvest() if harvest is None else harvest
        if seal:
            report = dict(report)
            report["sealed_digests"] = {
                "units": _canonical(units_data),
                "use_events": _canonical(events_data),
            }
        (self.root / "harvest_report.json").write_text(
            json.dumps(report), encoding="utf-8")
        (self.root / "units.json").write_text(
            json.dumps(units_data), encoding="utf-8")
        (self.root / "use_events.json").write_text(
            json.dumps(events_data), encoding="utf-8")
        (self.root / "dossier.json").write_text(json.dumps({
            "harvest": "harvest_report.json",
            "units": "units.json",
            "use_events": "use_events.json",
        }), encoding="utf-8")
        return self.root

    def assess(self, units, events, harvest=None):
        return assess_g5(
            dossier=self.write_dossier(units, events, harvest))

    # -- brief section 8, item 1 ------------------------------------
    def test_complete_dossier_access_demonstrated(self):
        result = self.assess(_units(4), _qualifying_events())
        self.assertEqual(result["gate"], "G5")
        self.assertEqual(result["criteria_version"], 1)
        self.assertEqual(result["overall"], "ACCESS_DEMONSTRATED")
        self.assertEqual(result["integrity_failures"], [])
        for clause in ("C1", "C2", "C3"):
            self.assertEqual(
                result["clauses"][clause]["verdict"], "PASS")

    # -- item 2 -------------------------------------------------------
    def test_c1_fraction_below_threshold(self):
        units = _units(8) + [
            _unit("u-009", fields={"batas": False}),
            _unit("u-010", fields={"batas": False}),
        ]
        result = self.assess(units, _qualifying_events())
        c1 = result["clauses"]["C1"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(any("u-009" in m for m in c1["missing"]))
        self.assertTrue(any("fraction_below_threshold" in m
                            for m in c1["missing"]))

    # -- item 3: the HASIL floor is decisive -------------------------
    def test_c1_hasil_floor_beats_fraction(self):
        units = _units(19) + [_unit("u-020",
                                    fields={"hasil": False})]
        result = self.assess(units, _qualifying_events())
        c1 = result["clauses"]["C1"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(any("u-020.fields.hasil" in m
                            for m in c1["missing"]))
        self.assertTrue(any("hasil_floor" in m
                            for m in c1["missing"]))

    # -- item 4 -------------------------------------------------------
    def test_c1_missing_keyakinan_named_per_unit(self):
        units = _units(8) + [
            _unit("u-009", fields={"keyakinan": False}),
            _unit("u-010", fields={"keyakinan": False}),
        ]
        result = self.assess(units, _qualifying_events())
        c1 = result["clauses"]["C1"]
        self.assertEqual(c1["verdict"], "FAIL")
        for uid in ("u-009", "u-010"):
            self.assertTrue(any(
                f"{uid}.fields.keyakinan" in m
                for m in c1["missing"]))

    # -- item 5 -------------------------------------------------------
    def test_c2_fraction_below_threshold(self):
        units = _units(8) + [
            _unit("u-009", contained=False),
            _unit("u-010", contained=False),
        ]
        result = self.assess(units, _qualifying_events())
        c2 = result["clauses"]["C2"]
        self.assertEqual(c2["verdict"], "FAIL")
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(any("u-009.self_contained" in m
                            for m in c2["missing"]))

    # -- item 6 -------------------------------------------------------
    def test_c3_only_two_qualifying_events(self):
        result = self.assess(_units(4), _qualifying_events()[:2])
        self.assertEqual(result["clauses"]["C3"]["verdict"],
                         "FAIL")
        self.assertEqual(result["overall"], "DELIVERY_ONLY")
        self.assertTrue(any("events_below_min" in m for m in
                            result["clauses"]["C3"]["missing"]))

    # -- item 7 -------------------------------------------------------
    def test_c3_single_domain_fails(self):
        events = [
            _event("e-001", action="decision",
                   domain="operations"),
            _event("e-002", action="correction",
                   domain="operations"),
            _event("e-003", action="direction",
                   domain="operations"),
        ]
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertEqual(result["overall"], "DELIVERY_ONLY")
        self.assertTrue(any("domains_below_min" in m
                            for m in c3["missing"]))

    # -- item 8 -------------------------------------------------------
    def test_c3_no_correction_when_required(self):
        events = [
            _event("e-001", action="decision",
                   domain="operations"),
            _event("e-002", action="direction",
                   domain="finance"),
            _event("e-003", action="resource_commitment",
                   domain="operations"),
        ]
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertEqual(result["overall"], "DELIVERY_ONLY")
        self.assertTrue(any("correction_absent" in m
                            for m in c3["missing"]))

    # -- item 9 -------------------------------------------------------
    def test_acknowledgement_never_qualifies(self):
        events = [_event(f"e-00{i}", action="acknowledgement")
                  for i in (1, 2, 3)]
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertTrue(any("action" in w
                            for w in c3["warnings"]))

    # -- item 10 ------------------------------------------------------
    def test_owner_initiative_never_qualifies(self):
        events = [_event(f"e-00{i}", unit=None,
                         action="owner_initiative")
                  for i in (1, 2, 3)]
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertTrue(any("reference" in w
                            for w in c3["warnings"]))

    # -- item 11 ------------------------------------------------------
    def test_event_before_unit_never_qualifies(self):
        events = _qualifying_events()[:2] + [
            _event("e-003", action="direction",
                   domain="finance",
                   timestamp="2026-11-12T19:30:00+07:00"),
        ]
        # e-003 predates u-001 (20:00): sequence test fails.
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertTrue(any("e-003" in w and "sequence" in w
                            for w in c3["warnings"]))

    # -- item 12 ------------------------------------------------------
    def test_bare_approval_never_qualifies(self):
        events = [_event(f"e-00{i}", action="bare_approval")
                  for i in (1, 2, 3)]
        result = self.assess(_units(4), events)
        self.assertEqual(result["clauses"]["C3"]["verdict"],
                         "FAIL")
        self.assertEqual(result["overall"], "DELIVERY_ONLY")

    # -- item 13: tamper probe ----------------------------------------
    def test_tampered_unit_breaks_seal_named_once(self):
        dossier = self.write_dossier(_units(4),
                                     _qualifying_events())
        units_path = dossier / "units.json"
        data = json.loads(units_path.read_text(encoding="utf-8"))
        data["units"][0]["fields"]["batas"] = False
        units_path.write_text(json.dumps(data), encoding="utf-8")
        result = assess_g5(dossier=dossier)
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertEqual(result["integrity_failures"],
                         ["units.digest_mismatch"])
        blob = json.dumps(result)
        self.assertEqual(blob.count("digest_mismatch"), 1)

    # -- item 14 ------------------------------------------------------
    def test_harvester_is_author_named(self):
        harvest = _harvest(harvester_id="ila-main")
        result = self.assess(_units(4), _qualifying_events(),
                             harvest)
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertIn("harvest.harvester_is_author",
                      result["integrity_failures"])

    # -- item 15 ------------------------------------------------------
    def test_out_of_period_records_warn_not_counted(self):
        units = _units(4) + [
            _unit("u-900", fields={"hasil": False,
                                   "batas": False},
                  timestamp="2026-11-11T10:00:00+07:00"),
        ]
        events = _qualifying_events() + [
            _event("e-900", action="decision",
                   timestamp="2026-11-14T10:00:00+07:00"),
        ]
        result = self.assess(units, events)
        self.assertEqual(result["overall"], "ACCESS_DEMONSTRATED")
        self.assertTrue(any("u-900" in w and "out_of_period" in w
                            for w in
                            result["clauses"]["C1"]["warnings"]))
        self.assertTrue(any("e-900" in w and "out_of_period" in w
                            for w in
                            result["clauses"]["C3"]["warnings"]))

    # -- item 16 ------------------------------------------------------
    def test_missing_threshold_fails_clause_by_name(self):
        harvest = _harvest()
        del harvest["c3_min_events"]
        result = self.assess(_units(4), _qualifying_events(),
                             harvest)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "FAIL")
        self.assertTrue(any("c3_min_events" in m
                            for m in c3["missing"]))
        self.assertEqual(result["clauses"]["C1"]["verdict"],
                         "PASS")

    # -- item 17 ------------------------------------------------------
    def test_missing_dossier_fails_closed(self):
        for bad in (None, self.root / "does-not-exist"):
            result = assess_g5(dossier=bad)
            self.assertEqual(result["overall"],
                             "NOT_DEMONSTRATED")
            self.assertEqual(result["criteria_version"], 1)
            for clause in ("C1", "C2", "C3"):
                self.assertEqual(
                    result["clauses"][clause]["verdict"], "FAIL")

    # -- item 18 ------------------------------------------------------
    def test_malformed_json_named_no_exception(self):
        dossier = self.write_dossier(_units(4),
                                     _qualifying_events())
        (dossier / "units.json").write_text(
            "{ this is not json", encoding="utf-8")
        result = assess_g5(dossier=dossier)
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(any("units" in m for m in
                            result["clauses"]["C1"]["missing"]))

    # -- item 19 ------------------------------------------------------
    def test_non_numeric_threshold_named_fail(self):
        harvest = _harvest(c1_threshold="high")
        result = self.assess(_units(4), _qualifying_events(),
                             harvest)
        c1 = result["clauses"]["C1"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertTrue(any("c1_threshold" in m
                            and "not_numeric" in m
                            for m in c1["missing"]))

    def test_non_boolean_field_named_fail(self):
        units = _units(4)
        units[1]["fields"]["hasil"] = "yes"
        result = self.assess(units, _qualifying_events())
        c1 = result["clauses"]["C1"]
        self.assertEqual(c1["verdict"], "FAIL")
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertTrue(any("u-002.fields.hasil" in m
                            and "not_boolean" in m
                            for m in c1["missing"]))

    # -- item 20: Lesson 2 ---------------------------------------------
    def test_invalid_extras_degrade_to_warnings(self):
        events = _qualifying_events() + [
            _event("e-101", action="acknowledgement"),
            _event("e-102", unit="u-999", action="decision"),
        ]
        result = self.assess(_units(4), events)
        c3 = result["clauses"]["C3"]
        self.assertEqual(c3["verdict"], "PASS")
        self.assertEqual(result["overall"], "ACCESS_DEMONSTRATED")
        self.assertTrue(any("e-101" in w
                            for w in c3["warnings"]))
        self.assertTrue(any("e-102" in w and "reference" in w
                            for w in c3["warnings"]))

    # -- checklist C.5: a false requirement genuinely relaxes ---------
    def test_correction_not_required_relaxes_c3(self):
        events = [
            _event("e-001", action="decision",
                   domain="operations"),
            _event("e-002", action="direction",
                   domain="finance"),
            _event("e-003", action="resource_commitment",
                   domain="operations"),
        ]
        harvest = _harvest(c3_requires_correction=False)
        result = self.assess(_units(4), events, harvest)
        self.assertEqual(result["clauses"]["C3"]["verdict"],
                         "PASS")
        self.assertEqual(result["overall"], "ACCESS_DEMONSTRATED")


if __name__ == "__main__":
    unittest.main()
