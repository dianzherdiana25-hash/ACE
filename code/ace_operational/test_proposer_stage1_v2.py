"""Unit tests for Proposer Engine Stage 1 v2 (grammar + 1-shot repair)."""

import json
import os
import tempfile
import unittest

from ace_operational.proposer_episodes import load_episodes
from ace_operational.proposer_schema import PACKAGE_FIELDS
from ace_operational.proposer_stage1_v2 import (
    PROPOSER_JSON_SCHEMA,
    build_repair_messages,
    build_v2_messages,
    evaluate_arm,
    schema_digest,
)
from ace_operational.proposer_validator import validate_package
from ace_operational.test_proposer_engine import valid_package

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTCOMES = os.path.join(ROOT, "evidence", "proposer_stage1", "outcomes.json")


class Stage1V2Tests(unittest.TestCase):
    def test_schema_matches_package_fields_and_strict(self):
        self.assertEqual(set(PROPOSER_JSON_SCHEMA["required"]), set(PACKAGE_FIELDS))
        self.assertEqual(set(PROPOSER_JSON_SCHEMA["properties"]), set(PACKAGE_FIELDS))
        self.assertFalse(PROPOSER_JSON_SCHEMA["additionalProperties"])
        self.assertEqual(PROPOSER_JSON_SCHEMA["properties"]["uncertainties"]["type"], "array")
        self.assertGreaterEqual(PROPOSER_JSON_SCHEMA["properties"]["uncertainties"]["minItems"], 1)
        self.assertEqual(PROPOSER_JSON_SCHEMA["properties"]["risks"]["minItems"], 2)
        self.assertEqual(len(schema_digest()), 64)

    def test_v2_messages_contain_no_outcome_text(self):
        with open(OUTCOMES, encoding="utf-8") as fh:
            outcomes = json.load(fh)["outcomes"]
        for ep in load_episodes():
            msgs = build_v2_messages(ep)
            joined = "\n".join(m["content"] for m in msgs)
            outcome = outcomes[ep["episode_id"]]["outcome"]
            for frag in outcome.replace(",", " ").split():
                if len(frag) > 12 and frag.isupper():
                    self.assertNotIn(frag, joined)
            self.assertNotIn(outcome[:60], joined)

    def test_repair_messages_carry_validator_reasons_only(self):
        ep = load_episodes()[0]
        reasons = ["options_considered must include 'do_not_run'"]
        msgs = build_repair_messages(ep, '{"bad": true}', reasons)
        self.assertEqual(len(msgs), 4)
        self.assertIn("do_not_run", msgs[-1]["content"])
        self.assertNotIn("rubric", msgs[-1]["content"].lower())

    def test_evaluate_arm_handles_passing_and_failing_synthetic_runs(self):
        eps = load_episodes()
        with tempfile.TemporaryDirectory() as td:
            for ep in eps:
                pkg = valid_package(ep)
                ok, reasons = validate_package(pkg)
                self.assertTrue(ok, reasons)
                with open(os.path.join(td, ep["episode_id"] + ".txt"), "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(pkg))
            rep = evaluate_arm(td, OUTCOMES, arm_label="synthetic_pass")
            self.assertEqual(rep["quality_clause"], "PASS")
            self.assertEqual(rep["exit_gate_verdict"], "PARTIAL")

        with tempfile.TemporaryDirectory() as td:
            rep = evaluate_arm(td, OUTCOMES, arm_label="synthetic_empty")
            self.assertEqual(rep["quality_clause"], "FAIL")
            self.assertEqual(rep["exit_gate_verdict"], "NOT_PASSED")


if __name__ == "__main__":
    unittest.main()
