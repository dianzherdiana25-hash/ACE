"""Synthetic validation of the standalone E1.4b report-consistency auditor."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_replication_audit import AuditError, audit


def sample_report(kind="replication"):
    regimes = ("unconditioned_pool",) if kind == "replication" else (
        "witness_pool", "low_information", "out_of_basis")
    episodes_per_group = 6 if kind == "replication" else 3
    rows, summary = [], []
    for family in ("S", "G"):
        for regime in regimes:
            for _ in range(episodes_per_group):
                i = len(rows)
                task_id = f"{i:032x}"
                def arm(correct, question=None):
                    data = {"task_id": task_id, "family": family, "regime": regime,
                            "correct": correct, "total": 8, "fit_status": "fit",
                            "cap_reached": False, "scores": {"in_distribution":
                               {"correct": correct // 2, "total": 4},
                               "extrapolation": {"correct": correct - correct // 2,
                                                  "total": 4}}}
                    if question is not None:
                        data.update(question=question, labels=1, oracle_cpu_us=2)
                    return data
                rows.append({"task_id": task_id, "family": family, "regime": regime,
                             "selector": {"index": 0, "disagreements": [0],
                                          "reason": "disagreement", "steps": 40,
                                          "cpu_us": 10, "wall_us": 20},
                             "initial": arm(4),
                             "hypotheses": [{"status": "fit", "fit_steps": 10},
                                            {"status": "fit", "fit_steps": 20}],
                             "active_question": 0,
                             "uniform_one_label_arms": [arm(8 if j == 0 else 4, j)
                                                         for j in range(8)]})
            summary.append({"family": family, "regime": regime,
                            "episodes": episodes_per_group,
                            "total_per_policy": episodes_per_group * 8,
                            "initial_correct": episodes_per_group * 4,
                            "active_correct": episodes_per_group * 8,
                            "uniform_expected_correct": episodes_per_group * 4.5,
                            "active_vs_uniform": {"wins": episodes_per_group,
                                                  "ties": 0, "losses": 0},
                            "selection_reasons": {"disagreement": episodes_per_group}})
    return {"mode": "public_development_replication" if kind == "replication"
                    else "public_development", "bank_sha256": "a" * 64,
            "source_sha256": "b" * 64, "episodes": len(rows),
            "isolated_fits": len(rows) * 11,
            "rows": rows, "summary": summary,
            "limits": {"query_cpu_us": 100_000, "query_wall_us": 250_000},
            "budget": {"selector_caps": 0, "fit_caps": 0, "prediction_caps": 0},
            "decision": "go_to_cross_episode_development" if kind == "replication"
                        else "go_to_public_replication"}


class EvidenceAuditTests(unittest.TestCase):
    def test_valid_replication(self):
        value = audit(sample_report())
        self.assertEqual((value["episodes"], value["one_label_control_arms"]), (12, 96))
        self.assertEqual(value["decision"], "go_to_cross_episode_development")

    def test_valid_old_pilot(self):
        self.assertEqual(audit(sample_report("pilot"), kind="pilot")["episodes"], 18)

    def reject(self, change, fragment):
        data = sample_report()
        change(data)
        with self.assertRaisesRegex(AuditError, fragment):
            audit(data)

    def test_duplicate_task(self):
        self.reject(lambda d: d["rows"][1].__setitem__("task_id", d["rows"][0]["task_id"]),
                    "duplicate task ID")

    def test_selector_mismatch(self):
        self.reject(lambda d: d["rows"][0].__setitem__("active_question", 1),
                    "active question inconsistent")

    def test_missing_one_label(self):
        self.reject(lambda d: d["rows"][0]["uniform_one_label_arms"][0].__setitem__("labels", 2),
                    "exactly one oracle label")

    def test_tampered_score(self):
        self.reject(lambda d: d["rows"][0]["uniform_one_label_arms"][0].__setitem__("correct", 7),
                    "subtotal mismatch")

    def test_tampered_aggregate(self):
        self.reject(lambda d: d["summary"][0].__setitem__("active_correct", 1),
                    "active_correct mismatch")

    def test_forged_go(self):
        self.reject(lambda d: d.__setitem__("decision", "hold_for_diagnosis"),
                    "decision mismatch")

    def test_unreported_selector_timing_cap(self):
        self.reject(lambda d: d["rows"][0]["selector"].__setitem__("cpu_us", 200_000),
                    "budget selector_caps mismatch")

    def test_unreported_cap(self):
        self.reject(lambda d: d["rows"][0]["initial"].__setitem__("cap_reached", True),
                    "budget prediction_caps mismatch")

    def test_selector_did_not_choose_disagreement(self):
        self.reject(lambda d: d["rows"][0]["selector"].__setitem__("disagreements", [1]),
                    "did not choose a disagreement")

    def test_no_duplicate_question_slots(self):
        self.reject(lambda d: d["rows"][0]["uniform_one_label_arms"][1].__setitem__("question", 0),
                    "question slot mismatch")

    def test_wrong_number_of_arms(self):
        self.reject(lambda d: d["rows"][0]["uniform_one_label_arms"].pop(),
                    "eight uniform one-label branches")

    def test_wrong_episode_count(self):
        self.reject(lambda d: d.__setitem__("episodes", 11),
                    "wrong number of episodes")

    def test_wrong_report_kind(self):
        self.reject(lambda d: d.__setitem__("mode", "public_development"),
                    "mismatched mode")

    def test_inconsistent_reason(self):
        self.reject(lambda d: d["rows"][0]["selector"].__setitem__("reason", "agreement"),
                    "unexpected disagreement indices")

    def test_detect_false_boolean_integer(self):
        self.reject(lambda d: d["rows"][0]["uniform_one_label_arms"][0].__setitem__("correct", True),
                    "expected integer")


if __name__ == "__main__":
    unittest.main()
