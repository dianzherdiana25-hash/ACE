#!/usr/bin/env python3
"""Preregistered public W3 diagnostic; no provider calls or terminal selection."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from ace_capability_evolution import compositional as c
from ace_core_repair.admission import AdmissionAwareSelector, fit_with_admission

PROTOCOL = "a225037c8cdfa9f98155ca3122efc8d048e72246"


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def legacy_status(fn, train, max_errors=0):
    """The old decision rule, retained as data analysis, not a fallback gate."""
    errors = sum(fn(w) != label for w, label in train)
    return "ADMITTED" if errors == 0 else "ADMITTED_WITH_ERRORS" if errors <= max_errors else "REJECTED"


def score(program, rows):
    if program is None:
        return {"correct": 0, "total": len(rows), "abstained": len(rows), "predictions": []}
    predictions = [program.predict(word) for word, _ in rows]
    # Separate serialized interpreter; no terminal information goes back to fit.
    if predictions != [c.replay(program.data(), word) for word, _ in rows]:
        raise ValueError("serialized replay mismatch")
    return {"correct": sum(p == y for p, (_, y) in zip(predictions, rows)),
            "total": len(rows), "abstained": 0, "predictions": predictions}


def run():
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    profiles, adversarial, cells = [], [], []
    words = ["".join(chars) for n in range(8) for chars in itertools.product("ab", repeat=n)]
    for name, rule in (("equal", lambda w: w.count("a") == w.count("b")),
                       ("starts", lambda w: w.startswith("a")),
                       ("parity", lambda w: len(w) % 2 == 0)):
        train = [(w, rule(w)) for w in words if len(w) <= 3]
        val = [(w, rule(w)) for w in words if 4 <= len(w) <= 5]
        terminal = [(w, rule(w)) for w in words if len(w) >= 6]
        seen = dict(train)
        for candidate_name, fn in (("true_rule", rule), ("training_memorizer", lambda w: seen.get(w, False))):
            before = legacy_status(fn, train)
            after = AdmissionAwareSelector().evaluate_and_select(fn, train, val)
            # Terminal scored only after both decisions are fixed.
            terminal_correct = sum(fn(w) == y for w, y in terminal)
            adversarial.append({"family": name, "candidate": candidate_name,
                                "train": train, "validation": val, "terminal": terminal,
                                "legacy_status": before, "current": after,
                                "candidate_terminal_correct": terminal_correct})
    fit_impl = c.fit
    for seed in c.SEEDS:
        for task_name in c.TASKS:
            if time.perf_counter() - start_wall > 900:
                raise TimeoutError("900-second study budget exceeded")
            train, val, terminal = c.bank(task_name, seed)
            captured, fit_profile = [], []
            def capture_fit(tr, va):
                # Instrument the actual existing fit once. No labels, candidates
                # or scores are replaced. The same objects serve all controls.
                t, cpu = time.perf_counter(), time.process_time()
                result = fit_impl(tr, va)
                fit_profile.append({"wall_seconds": time.perf_counter() - t,
                                    "cpu_seconds": time.process_time() - cpu})
                captured.append(result)
                return result
            t, cpu = time.perf_counter(), time.process_time()
            with patch.object(c, "fit", side_effect=capture_fit):
                chosen, admission = fit_with_admission(train, val)
            if len(captured) != 1:
                raise ValueError("fit was not called exactly once")
            learned, fit_report = captured[0]
            new_profile = {"wall_seconds_including_fit": time.perf_counter() - t,
                           "cpu_seconds_including_fit": time.process_time() - cpu}
            old_candidate = learned["composition"]
            old_decision = legacy_status(old_candidate.predict, train)
            old = old_candidate if old_decision.startswith("ADMITTED") else None
            best, strong_selection = c.select(list(learned.values()), train, val)
            strong = best if strong_selection["admitted"] else None
            # Freeze ALL selections before terminal scoring. Existing bank is
            # public, so this is code-level separation, not evaluator custody.
            cell = {"family": task_name, "seed": seed,
                    "train": train, "validation": val, "terminal": terminal,
                    "admission": admission,
                    "legacy": {"status": old_decision,
                               "observed_validation_errors": len(val) - c.correct(old_candidate, val, c.Work())},
                    "strong_selection": strong_selection,
                    "programs": {"current": chosen.data() if chosen else None,
                                 "legacy": old.data() if old else None,
                                 "strong": strong.data() if strong else None},
                    "terminal_scores": {"current": score(chosen, terminal), "legacy": score(old, terminal),
                                        "strong": score(strong, terminal), "always_abstain": score(None, terminal)},
                    "nominal_labels": {"train": len(train), "validation": len(val), "terminal": len(terminal)}}
            cells.append(cell)
            profiles.append({"family": task_name, "seed": seed,
                             "fit_shared": fit_profile[0], "current": new_profile,
                             "fit_work": {k: fit_report[k] for k in (
                                 "base_merge_attempts", "residual_merge_attempts", "proposal_work")},
                             "admission_work": admission["admission_work"],
                             "strong_selection_work": strong_selection["work"]})
    first = cells[0]
    ordinary = first["terminal_scores"]["current"]
    hidden_flip = {"development_identical_to": {"family": first["family"], "seed": first["seed"]},
                   "decision_unchanged": first["admission"]["status"],
                   "inverted_terminal_correct": ordinary["total"] - ordinary["correct"],
                   "total": ordinary["total"], "semantic_safety_established": False}
    summary = {arm: {"correct": sum(cell["terminal_scores"][arm]["correct"] for cell in cells),
                     "total": sum(cell["terminal_scores"][arm]["total"] for cell in cells),
                     "covered_tasks": sum(cell["programs"].get(arm) is not None for cell in cells)}
               for arm in ("current", "legacy", "strong", "always_abstain")}
    false_admission = sum(cell["legacy"]["status"].startswith("ADMITTED") and
                          cell["legacy"]["observed_validation_errors"] > 0 for cell in cells)
    unique_labels = {}
    for split in ("train", "validation", "terminal"):
        unique_labels[split] = len({(cell["family"], w, y) for cell in cells for w, y in cell[split]})
    gates = {
        "H1_all_validation_failures_rejected": all(
            r["current"]["status"] == "REJECTED" for r in adversarial if r["candidate"] == "training_memorizer"),
        "H2_all_positive_controls_admitted": all(
            r["current"]["status"] == "ADMITTED" for r in adversarial if r["candidate"] == "true_rule"),
        "H3_starts_all_seeds_admitted": all(
            cell["admission"]["status"] == "ADMITTED" for cell in cells if cell["family"] == "starts"),
        "H4_hidden_flip_still_fails": hidden_flip["inverted_terminal_correct"] < hidden_flip["total"],
    }
    report = {"schema": "ace.w3-admission.public.v1", "protocol_commit": PROTOCOL,
              "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
                  "code/ace_core_repair/admission.py", "code/ace_runtime/cli.py",
                  "code/ace_capability_evolution/compositional.py", "tools/ace_w3_admission_benchmark.py")},
              "adversarial": adversarial, "cells": cells, "summary": summary,
              "legacy_observed_false_admission_tasks": false_admission,
              "current_observed_false_admission_tasks": sum(
                  cell["admission"]["status"].startswith("ADMITTED") and cell["admission"]["validation_errors"] > 0
                  for cell in cells),
              "hidden_flip": hidden_flip, "gates": gates,
              "nominal_label_slots": {split: sum(len(cell[split]) for cell in cells)
                                      for split in ("train", "validation", "terminal")},
              "unique_family_word_label_observations": unique_labels,
              "adversarial_nominal_label_slots_per_candidate": {split: sum(
                  len(r[split]) for r in adversarial if r["candidate"] == "true_rule")
                  for split in ("train", "validation", "terminal")},
              "adversarial_candidates_per_family": 2,
              "actual_prediction_calls": {
                  "current_admission": sum(cell["admission"]["candidate_predictions"] for cell in cells),
                  "legacy_training_gate": sum(len(cell["train"]) for cell in cells),
                  "legacy_validation_diagnostic": sum(len(cell["validation"]) for cell in cells),
                  "strong_development_selection": sum(cell["strong_selection"]["work"]["predictions"] for cell in cells),
                  "terminal_per_interpreter": sum(
                      len(cell["terminal_scores"][arm]["predictions"])
                      for cell in cells for arm in ("current", "legacy", "strong")),
                  "terminal_interpreters": 2},
              "label_accounting_note": "Integration slots shared across controls; adversarial slots shared across two candidates. "
                  "Predictions reuse existing labels; fit internals are not completely metered.",
              "external_ai_calls": 0, "paid_labels": 0, "additional_api_cost_idr": 0,
              "compute_matched_end_to_end": False, "full_inference_accounting": False,
              "new_primitive_discovered": False, "scientific_status": "NOT_ASSESSED",
              "release_gate": "BLOCK_RELEASE", "candidate_deployed": False}
    profile = {"cpu_seconds": time.process_time() - start_cpu,
               "wall_seconds": time.perf_counter() - start_wall,
               "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "unit_note": "Linux ru_maxrss; shared process peak, not per-task memory", "tasks": profiles}
    return report, profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    report, profile = run()
    for path, value in ((args.output, report), (args.profile, profile)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"summary": report["summary"], "gates": report["gates"],
                      "legacy_false_admission": report["legacy_observed_false_admission_tasks"],
                      "current_false_admission": report["current_observed_false_admission_tasks"],
                      "profile": {k: v for k, v in profile.items() if k != "tasks"}}, sort_keys=True))
    return 0 if all(report["gates"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
