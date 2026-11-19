#!/usr/bin/env python3
"""Unit tests for C2: Self-Model Continuity Probe across organ-label swaps."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from tools.narrative_self_model import build_narrative_self_model
from tools.self_model_continuity_probe import (
    DEFAULT_ORGAN_SLATES,
    SCHEMA,
    render_markdown,
    run_continuity_probe,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ContinuityProbeTests(unittest.TestCase):
    def test_real_c1_intact_across_three_organ_slates_and_styles(self) -> None:
        report = run_continuity_probe(REPO_ROOT)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["continuity_passed"])
        self.assertEqual(report["verdict"], "CONTINUITY_INTACT")
        self.assertEqual(report["variants_tested"], len(DEFAULT_ORGAN_SLATES) - 1)
        self.assertGreater(report["baseline_fact_count"], 5)
        for comp in report["comparisons"]:
            self.assertTrue(comp["passed"])
            self.assertEqual(comp["missing_facts"], [])
            self.assertEqual(comp["added_facts"], [])
            self.assertEqual(comp["value_mismatches"], [])
            self.assertEqual(comp["organ_contamination"], [])
        md = render_markdown(report)
        self.assertIn("CONTINUITY_INTACT", md)

    def test_wording_paraphrase_still_passes_fact_continuity(self) -> None:
        def paraphrased_gen(root: Path, mem_path: Path | None, org: dict, style: str) -> dict:
            base = build_narrative_self_model(root, memory_path=mem_path, organ_context=org, narrative_style=style)
            out = copy.deepcopy(base)
            if org.get("front") != "local/Qwen3.5-4B-MTP":
                for sec in ("identity", "proven", "unproven"):
                    for clm in out["sections"][sec]:
                        clm["statement"] = f"Parafrase gaya organ {style}: {clm['fact_key']}."
            return out

        report = run_continuity_probe(REPO_ROOT, generator=paraphrased_gen)
        self.assertTrue(report["continuity_passed"])
        self.assertEqual(report["verdict"], "CONTINUITY_INTACT")

    def test_detects_value_mutation_and_added_dropped_facts(self) -> None:
        def drifting_gen(root: Path, mem_path: Path | None, org: dict, style: str) -> dict:
            out = copy.deepcopy(build_narrative_self_model(root, memory_path=mem_path, organ_context=org))
            if org.get("coder") == "groq/qwen/qwen3.8-27b":
                out["sections"]["proven"] = [
                    c for c in out["sections"]["proven"] if c["fact_key"] != "gate:G3"
                ]
                for c in out["sections"]["unproven"]:
                    if c["fact_key"] == "gate:G2":
                        c["fact_value"] = "FABRICATED_PASS"
                # Rebuild facts like external generator
                from tools.narrative_self_model import extract_facts
                out["facts"] = extract_facts(out)
            return out

        slates = DEFAULT_ORGAN_SLATES[:2]
        report = run_continuity_probe(REPO_ROOT, organ_slates=slates, generator=drifting_gen)
        self.assertFalse(report["continuity_passed"])
        self.assertEqual(report["verdict"], "FACT_DRIFT_DETECTED")
        comp = report["comparisons"][0]
        self.assertIn("proven::gate:G3", comp["missing_facts"])
        self.assertEqual(comp["value_mismatches"][0]["key"], "unproven::gate:G2")

    def test_detects_organ_label_contamination_and_sourceless_drift(self) -> None:
        def leaky_gen(root: Path, mem_path: Path | None, org: dict, style: str) -> dict:
            out = copy.deepcopy(build_narrative_self_model(root, memory_path=mem_path, organ_context=org))
            if org.get("coder") == "groq/qwen/qwen3.8-27b":
                # Bocorkan nama organ ke klaim identitas yang ada, beserta sumber sah
                target = out["sections"]["identity"][0]
                target["statement"] = f"Identitas saya adalah {org['coder']}"
                target["fact_value"] = org["coder"]
                from tools.narrative_self_model import extract_facts
                out["facts"] = extract_facts(out)
            elif org.get("judge") == "gonka/DeepSeek-V4-Flash-0731":
                out["sections"]["proven"].append(
                    {
                        "claim_id": "clm_sourceless",
                        "section": "proven",
                        "fact_key": "imaginary_win",
                        "fact_value": True,
                        "statement": "Klaim tanpa sumber",
                        "sources": [],
                    }
                )
                from tools.narrative_self_model import extract_facts
                out["facts"] = extract_facts(out)
            return out

        report = run_continuity_probe(REPO_ROOT, generator=leaky_gen)
        self.assertFalse(report["continuity_passed"])
        c1, c2 = report["comparisons"]
        self.assertTrue(len(c1["organ_contamination"]) >= 1)
        self.assertTrue(len(c2["sourceless_errors"]) >= 1)
        self.assertIn("proven::imaginary_win", c2["added_facts"])

    def test_readonly_custom_memory_fixture_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / "snap.jsonl"
            mem.write_text(
                '{"id": "rec_01", "kind": "semantic", "source_kind": "evidence", "content": {"event": "uji L3"}}\n',
                encoding="utf-8",
            )
            report = run_continuity_probe(REPO_ROOT, memory_path=mem)
            self.assertTrue(report["continuity_passed"])


if __name__ == "__main__":
    unittest.main()
