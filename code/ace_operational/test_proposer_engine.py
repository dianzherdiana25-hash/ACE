"""Tests for the Stage-1 proposer engine (simulation-first)."""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ace_operational.proposer_episodes import build_prompt, load_episodes
from ace_operational.proposer_rubric import score_package
from ace_operational.proposer_schema import empty_package_template
from ace_operational.proposer_simulation import extract_package
from ace_operational.proposer_validator import validate_package

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTCOMES = os.path.join(ROOT, "evidence", "proposer_stage1", "outcomes.json")


def valid_package(episode):
    pkg = empty_package_template()
    pkg["proposal_id"] = "test-1"
    pkg["task_kind"] = "task"
    pkg["claim"] = "Index >= 0 with control margin at least 0pp; below 0 fails."
    pkg["rationale"] = "From the at-time record."
    pkg["options_considered"] = [
        {"name": n, "assessment": "assessed"} for n in episode["options_available"]
    ]
    pkg["recommended_option"] = episode["options_available"][0]
    env = episode["budget_envelope"]
    pkg["cost_estimate"] = {"calls": env["calls"], "wall_seconds": env["wall_seconds"] // 2, "cost_units": 0.5}
    pkg["cost_ceiling"] = {"max_calls": max(env["calls"], 1), "max_wall_seconds": env["wall_seconds"], "max_cost_units": 1.0}
    pkg["evidence"] = [dict(e) for e in episode["evidence_scope"]]
    pkg["preregistration"] = {"link": "evidence/proposer_stage1/episodes.json",
                               "artifact_sha256": episode["evidence_scope"][0]["sha256"]}
    pkg["risks"] = ["control regression risk", "saturation risk"]
    pkg["uncertainties"] = ["effect size unknown"]
    pkg["stop_controls"]["abort_conditions"] = ["ceiling hit", "calibration gate fails"]
    pkg["stop_controls"]["sealed_target_status"] = episode["sealed_target_status_at_time"]
    return pkg


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episodes = load_episodes()
        cls.ep = cls.episodes[0]

    def test_valid_package_accepted(self):
        ok, reasons = validate_package(valid_package(self.ep))
        self.assertTrue(ok, reasons)

    def test_missing_ceiling_rejected(self):
        pkg = valid_package(self.ep)
        del pkg["cost_ceiling"]
        ok, reasons = validate_package(pkg)
        self.assertFalse(ok)
        self.assertTrue(any("cost_ceiling" in r for r in reasons))

    def test_zero_ceiling_rejected(self):
        pkg = valid_package(self.ep)
        pkg["cost_ceiling"]["max_wall_seconds"] = 0
        ok, _ = validate_package(pkg)
        self.assertFalse(ok)

    def test_estimate_above_ceiling_rejected(self):
        pkg = valid_package(self.ep)
        pkg["cost_estimate"]["wall_seconds"] = pkg["cost_ceiling"]["max_wall_seconds"] + 1
        ok, _ = validate_package(pkg)
        self.assertFalse(ok)

    def test_missing_stop_controls_rejected(self):
        pkg = valid_package(self.ep)
        pkg["stop_controls"]["abort_conditions"] = []
        ok, reasons = validate_package(pkg)
        self.assertFalse(ok)
        self.assertTrue(any("abort_conditions" in r for r in reasons))

    def test_auto_retry_rejected(self):
        pkg = valid_package(self.ep)
        pkg["stop_controls"]["no_auto_retry"] = False
        ok, _ = validate_package(pkg)
        self.assertFalse(ok)

    def test_missing_evidence_hash_rejected(self):
        pkg = valid_package(self.ep)
        pkg["evidence"][0]["sha256"] = "not-a-hash"
        ok, reasons = validate_package(pkg)
        self.assertFalse(ok)
        self.assertTrue(any("sha256" in r for r in reasons))

    def test_missing_prereg_hash_rejected(self):
        pkg = valid_package(self.ep)
        pkg["preregistration"]["artifact_sha256"] = ""
        ok, _ = validate_package(pkg)
        self.assertFalse(ok)

    def test_no_do_not_run_rejected(self):
        pkg = valid_package(self.ep)
        pkg["options_considered"] = [o for o in pkg["options_considered"] if o["name"] != "do_not_run"]
        pkg["recommended_option"] = pkg["options_considered"][0]["name"]
        ok, reasons = validate_package(pkg)
        self.assertFalse(ok)
        self.assertTrue(any("do_not_run" in r for r in reasons))

    def test_owner_approval_vocabulary_rejected(self):
        pkg = valid_package(self.ep)
        pkg["ratification"] = {"type": "internal_ratification",
                                "audience": ["hub", "kernel", "evidence"],
                                "owner_approval": "pending"}
        ok, reasons = validate_package(pkg)
        self.assertFalse(ok)
        self.assertTrue(any("owner approval" in r for r in reasons))

    def test_unknown_field_rejected(self):
        pkg = valid_package(self.ep)
        pkg["dispatch_now"] = True
        ok, _ = validate_package(pkg)
        self.assertFalse(ok)


class SeparationTests(unittest.TestCase):
    def test_prompts_contain_no_outcome_text(self):
        with open(OUTCOMES, encoding="utf-8") as fh:
            outcomes = json.load(fh)["outcomes"]
        for ep in load_episodes():
            prompt = build_prompt(ep)
            outcome = outcomes[ep["episode_id"]]["outcome"]
            # No distinctive outcome fragment may leak into the prompt.
            for frag in outcome.replace(",", " ").split():
                if len(frag) > 12 and frag.isupper():
                    self.assertNotIn(frag, prompt)
            self.assertNotIn(outcome[:60], prompt)

    def test_every_episode_has_prior_exposure_declaration(self):
        for ep in load_episodes():
            self.assertTrue(ep["prior_exposure_declaration"].strip())

    def test_historical_packages_are_valid(self):
        with open(OUTCOMES, encoding="utf-8") as fh:
            outcomes = json.load(fh)["outcomes"]
        for ep in load_episodes():
            hist = outcomes[ep["episode_id"]]["historical_package"]
            ok, reasons = validate_package(hist)
            self.assertTrue(ok, (ep["episode_id"], reasons))


class RubricTests(unittest.TestCase):
    def test_rejected_package_scores_zero(self):
        ep = load_episodes()[0]
        pkg = valid_package(ep)
        pkg["stop_controls"]["no_auto_retry"] = False
        total, _ = score_package(pkg, ep)
        self.assertEqual(total, 0.0)

    def test_valid_package_scores_high(self):
        ep = load_episodes()[0]
        total, breakdown = score_package(valid_package(ep), ep)
        self.assertGreaterEqual(total, 70.0, breakdown)

    def test_extract_package_from_noisy_generation(self):
        raw = 'thinking...\n{"a": {"b": 1}, "c": [1,2]}\ntrailing'
        self.assertEqual(extract_package(raw), {"a": {"b": 1}, "c": [1, 2]})
        self.assertIsNone(extract_package("no json here"))


if __name__ == "__main__":
    unittest.main()
