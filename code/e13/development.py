"""Run E1.3 public fixtures through the development evaluator."""

import argparse
import json
from dataclasses import asdict

from .contract import parse_fit_request
from .dsl import Fuel, predict
from .isolation import IsolatedFit, WorkerError, fit_isolated
from .public_bank import public_fixtures


def run_fixture(fixture, solver=fit_isolated):
    request = parse_fit_request(fixture.fit_request)
    result = solver(fixture.fit_request)
    if result.program.family != request.family:
        raise ValueError("solver returned a different family")

    fuel = Fuel(2_000)
    predictions = tuple(predict(result.program.ast, probe.input, fuel)
                        for probe in fixture.probes)
    summary = {
        "family": request.family,
        "task_id": request.task_id,
        "seed": request.seed,
        "program_sha256": result.program.sha256,
        "candidates": result.candidates,
        "fit_steps": result.steps,
        "predict_steps": fuel.used,
        "correct": sum(prediction == probe.expected
                       for prediction, probe in zip(predictions, fixture.probes, strict=True)),
        "total": len(fixture.probes),
    }
    if isinstance(result, IsolatedFit):
        summary["worker"] = asdict(result.metrics)
    return summary


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        results = [run_fixture(fixture) for fixture in public_fixtures()]
    except WorkerError as error:
        print(json.dumps({"mode": "development", "passed": False, "error": str(error)}))
        return 1
    passed = all(result["correct"] == result["total"] for result in results)
    print(json.dumps({"mode": "development", "passed": passed, "fixtures": results}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
