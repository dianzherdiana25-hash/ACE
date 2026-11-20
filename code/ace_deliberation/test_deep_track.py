"""Verifier kelima ronde, rantai hash, batas waktu dan catatan dissent."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import deep_track as model


def at(second):
    return f"2026-11-20T00:00:{second:02}Z"


def seal(raw):
    parent = model.plan_digest(raw["plan"])
    raw["anchor_sha256"] = parent
    for row in raw["rounds"]:
        row["payload"]["parent_sha256"] = parent
        parent = row["sha256"] = model.round_digest(row["payload"])
    return raw


def fixture():
    plan = {"case_id": "case", "case_ref": "fixture/case", "opens_at": at(0), "closes_at": at(30),
            "budget": 20, "round_caps": {phase: 5 for phase, _ in model.PHASES},
            "roster": {role: {"participant": f"person/{role}", "family": f"family/{role}"}
                       for _, role in model.PHASES}}
    records = []
    for index, (phase, role) in enumerate(model.PHASES):
        sources = [records[-1]["payload"]["ref"]] if records else [plan["case_ref"]]
        sources.append(f"evidence/{phase}")
        records.append({"payload": {"phase": phase, "participant": f"person/{role}", "at": at(index * 5),
                                    "ref": f"round/{phase}", "summary": f"Catatan {phase}", "cost": 4,
                                    "source_refs": sources, "new_objections": [], "responses": []}})
    records[2]["payload"]["new_objections"] = [
        {"id": "specific", "summary": "Uji asumsi utama.", "evidence_ref": "evidence/challenge"},
        {"id": "timing", "summary": "Periksa sumber yang tertunda.", "evidence_ref": "evidence/challenge"},
    ]
    records[3]["payload"]["responses"] = [
        {"id": key, "disposition": "mitigated", "ref": "evidence/response"} for key in ("specific", "timing")
    ]
    return seal({"plan": plan, "rounds": records})


class DeepTests(unittest.TestCase):
    def test_five_rounds_are_reviewable_when_dissent_remains_traced(self):
        raw = fixture()
        report = model.rehearse(raw)
        self.assertEqual(report["status"], "reviewable")
        self.assertIsNone(report["next_round"])
        self.assertEqual(report["head_sha256"], raw["rounds"][-1]["sha256"])
        self.assertEqual(report["anchor_sha256"], raw["anchor_sha256"])
        self.assertEqual(report["spent"], 20)
        self.assertEqual([row["phase"] for row in report["rounds"]], [phase for phase, _ in model.PHASES])
        self.assertEqual(report["rounds"][2]["open_objections"], ["specific", "timing"])
        self.assertEqual(report["rounds"][3]["open_objections"], [])
        self.assertEqual(report["dissent"][0], {
            "id": "specific", "summary": "Uji asumsi utama.", "evidence_ref": "evidence/challenge",
            "raised_by": "round/challenge",
            "response": {"disposition": "mitigated", "source_ref": "evidence/response", "responded_by": "round/response"},
        })

    def test_incomplete_prefixes_are_replayable_and_expose_next_round(self):
        raw = fixture()
        for count, (phase, _) in enumerate(model.PHASES):
            report = model.rehearse({**raw, "rounds": raw["rounds"][:count]})
            self.assertEqual(report["status"], "held")
            self.assertEqual(report["next_round"], phase)
            self.assertEqual(report["head_sha256"],
                             raw["rounds"][count - 1]["sha256"] if count else raw["anchor_sha256"])
            self.assertIn("incomplete", report["blockers"])

    def test_unaddressed_and_sustained_objections_prevent_review_readiness(self):
        raw = fixture()
        replies = raw["rounds"][3]["payload"]["responses"]
        replies.pop()
        replies[0]["disposition"] = "sustained"
        report = model.rehearse(seal(raw))
        self.assertEqual(report["status"], "held")
        self.assertEqual(report["blockers"], ["objections_open", "objections_sustained"])
        self.assertIsNone(report["dissent"][1]["response"])
        self.assertEqual(report["dissent"][0]["response"]["disposition"], "sustained")

    def test_round_mutation_or_recomputed_record_without_descendant_update_fails(self):
        raw = fixture()
        changed = raw["rounds"][1]
        changed["payload"]["summary"] = "Sumber berubah"
        with self.assertRaisesRegex(model.InputError, "Rantai"):
            model.rehearse(raw)
        changed["sha256"] = model.round_digest(changed["payload"])
        with self.assertRaisesRegex(model.InputError, "Rantai"):
            model.rehearse(raw)

    def test_roster_and_both_cost_caps_are_bound_to_plan_anchor(self):
        raw = fixture()
        raw["plan"]["roster"]["reviewer"]["participant"] = "person/new"
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.rehearse(raw)
        raw = fixture()
        raw["rounds"][0]["payload"]["cost"] = 6
        with self.assertRaises(model.InputError):
            model.rehearse(seal(raw))
        raw = fixture()
        raw["rounds"][-1]["payload"]["cost"] = 5
        with self.assertRaisesRegex(model.InputError, "kumulatif"):
            model.rehearse(seal(raw))

    def test_claimed_role_wrong_phase_or_sixth_round_is_refused(self):
        raw = fixture()
        raw["rounds"][4]["payload"]["participant"] = "person/respondent"
        with self.assertRaisesRegex(model.InputError, "rencana"):
            model.rehearse(seal(raw))
        raw = fixture()
        raw["rounds"].append(raw["rounds"][-1])
        with self.assertRaises(model.InputError):
            model.rehearse(raw)

    def test_evidence_cannot_be_the_round_itself_or_an_unpublished_round(self):
        raw = fixture()
        raw["rounds"][0]["payload"]["source_refs"].append("round/synthesis")
        with self.assertRaisesRegex(model.InputError, "tersedia"):
            model.rehearse(seal(raw))
        raw = fixture()
        raw["rounds"][4]["payload"]["source_refs"].append("round/synthesis")
        with self.assertRaisesRegex(model.InputError, "tersedia"):
            model.rehearse(seal(raw))

    def test_mitigation_requires_own_source_and_preceding_round(self):
        raw = fixture()
        item = raw["rounds"][3]["payload"]
        item["source_refs"].remove("round/challenge")
        with self.assertRaisesRegex(model.InputError, "sebelumnya"):
            model.rehearse(seal(raw))
        item["source_refs"].append("round/challenge")
        item["responses"][0]["ref"] = "round/challenge"
        with self.assertRaisesRegex(model.InputError, "tidak sah"):
            model.rehearse(seal(raw))

    def test_unknown_duplicate_and_early_replies_are_rejected(self):
        for index, new in ((3, [{"id": "ghost", "disposition": "mitigated", "ref": "evidence/response"}]),
                           (2, [{"id": "specific", "disposition": "mitigated", "ref": "evidence/challenge"}])):
            raw = fixture()
            raw["rounds"][index]["payload"]["responses"].extend(new)
            with self.subTest(index=index), self.assertRaises(model.InputError):
                model.rehearse(seal(raw))
        raw = fixture()
        raw["rounds"][3]["payload"]["responses"] *= 2
        with self.assertRaisesRegex(model.InputError, "terbuka"):
            model.rehearse(seal(raw))

    def test_final_time_boundary_and_backdated_rows(self):
        raw = fixture()
        raw["rounds"][-1]["payload"]["at"] = at(30)
        self.assertEqual(model.rehearse(seal(raw))["status"], "reviewable")
        for second in (14, 31):
            raw["rounds"][-1]["payload"]["at"] = at(second)
            with self.subTest(second=second), self.assertRaisesRegex(model.InputError, "Waktu"):
                model.rehearse(seal(raw))

    def test_cli_report_matches_replay(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "deep.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main([str(path)]), 0)
        self.assertEqual(json.loads(result.getvalue()), model.rehearse(raw))
