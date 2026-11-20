"""Tes regresi fixture-only untuk tools.specialization_delta (AG41)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from tools import specialization_delta


def _make_report(seed: int, solver_id: str, domains: dict[str, tuple[int, int, float]]) -> dict:
    by_domain = {}
    total_all = 0
    passed_all = 0
    weighted_sum = 0.0
    for name, (passed, total, avg_score) in domains.items():
        by_domain[name] = {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 4),
            "avg_score": avg_score,
        }
        total_all += total
        passed_all += passed
        weighted_sum += avg_score * total
    return {
        "schema": "ace.owner-benchmark.v1",
        "seed": seed,
        "solver_id": solver_id,
        "summary": {
            "total_tasks": total_all,
            "passed_tasks": passed_all,
            "pass_rate": round(passed_all / total_all, 4),
            "avg_score": round(weighted_sum / total_all, 4),
            "domain_count": len(domains),
        },
        "by_domain": by_domain,
    }


class SpecializationDeltaTest(unittest.TestCase):
    def test_exact_delta_single_seed_pair(self) -> None:
        base = _make_report(
            11,
            "base-solver",
            {
                "coding": (2, 4, 0.5),
                "language": (3, 4, 0.75),
                "safety": (4, 4, 1.0),
            },
        )
        cand = _make_report(
            11,
            "specialized-solver",
            {
                "coding": (4, 4, 1.0),
                "language": (2, 4, 0.5),
                "safety": (4, 4, 1.0),
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b_path = root / "base.json"
            c_path = root / "cand.json"
            o_path = root / "delta.json"
            b_path.write_text(json.dumps(base), encoding="utf-8")
            c_path.write_text(json.dumps(cand), encoding="utf-8")

            rc = specialization_delta.main(
                ["--baseline", str(b_path), "--candidate", str(c_path), "--out", str(o_path)]
            )
            self.assertEqual(rc, 0)
            out = json.loads(o_path.read_text(encoding="utf-8"))

        self.assertEqual(out["schema"], specialization_delta.SCHEMA)
        self.assertEqual(out["shared_seeds"], [11])
        self.assertEqual(out["by_domain"]["coding"]["pass_rate_delta"], 0.5)
        self.assertEqual(out["by_domain"]["language"]["pass_rate_delta"], -0.25)
        self.assertEqual(out["by_domain"]["safety"]["pass_rate_delta"], 0.0)
        self.assertEqual(out["summary"]["improved_domains"], ["coding"])
        self.assertEqual(out["summary"]["regressed_domains"], ["language"])
        self.assertEqual(out["summary"]["unchanged_domains"], ["safety"])
        self.assertTrue(out["summary"]["all_domains_stable"])

    def test_multiseed_stability_detects_flaky_vs_consistent_domains(self) -> None:
        base_series = [
            _make_report(1, "base", {"coding": (2, 4, 0.5), "ops": (2, 4, 0.5)}),
            _make_report(2, "base", {"coding": (2, 4, 0.5), "ops": (1, 4, 0.25)}),
            _make_report(3, "base", {"coding": (2, 4, 0.5), "ops": (3, 4, 0.75)}),
        ]
        cand_series = [
            _make_report(1, "cand", {"coding": (3, 4, 0.75), "ops": (4, 4, 1.0)}),
            _make_report(2, "cand", {"coding": (3, 4, 0.75), "ops": (2, 4, 0.5)}),
            _make_report(3, "cand", {"coding": (3, 4, 0.75), "ops": (1, 4, 0.25)}),
        ]

        out = specialization_delta.compare_reports(base_series, cand_series)
        self.assertEqual(out["baseline_seeds"], [1, 2, 3])
        self.assertEqual(out["shared_seeds"], [1, 2, 3])

        coding = out["by_domain"]["coding"]
        self.assertEqual(coding["pass_rate_delta"], 0.25)
        self.assertTrue(coding["stable"])
        self.assertEqual(coding["sign_flips"], 0)
        self.assertEqual(coding["direction"], "improved")

        ops = out["by_domain"]["ops"]
        self.assertFalse(ops["stable"])
        self.assertEqual(ops["sign_flips"], 1)
        self.assertEqual(ops["direction"], "mixed_across_seeds")
        self.assertEqual(out["summary"]["unstable_domains"], ["ops"])
        self.assertFalse(out["summary"]["all_domains_stable"])

    @unittest.skipUnless(
        importlib.util.find_spec("tools.owner_benchmark") is not None,
        "memerlukan tools.owner_benchmark (AG39) terpasang untuk uji integrasi langsung",
    )
    def test_compatible_with_owner_benchmark_v1_output(self) -> None:
        from tools import owner_benchmark

        pack = {
            "pack_id": "owner-mini-v1",
            "pack_version": "1.0",
            "tasks": [
                {"id": "t1", "domain": "coding", "prompt": "p1", "expected": "ans1"},
                {"id": "t2", "domain": "language", "prompt": "p2", "expected": "ans2"},
            ],
        }
        r_base = owner_benchmark.run_benchmark(
            pack, answers={"t1": "wrong", "t2": "ans2"}, seed=7, solver_id="base"
        )
        r_cand = owner_benchmark.run_benchmark(
            pack, answers={"t1": "ans1", "t2": "ans2"}, seed=7, solver_id="cand"
        )
        out = specialization_delta.compare_reports(r_base, r_cand)
        self.assertEqual(out["by_domain"]["coding"]["pass_rate_delta"], 1.0)
        self.assertEqual(out["by_domain"]["language"]["pass_rate_delta"], 0.0)


if __name__ == "__main__":
    unittest.main()
