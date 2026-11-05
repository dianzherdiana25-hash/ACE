#!/usr/bin/env python3
"""Fail-closed exact-head unittest runner for ACE PR checks (stdlib only)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

TESTS = (
    "ace_loop.test_source_evolution",
    "ace_loop.test_engine",
    "ace_loop.test_portfolio",
)

def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--report", default="ace-ci-report.json")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    expected = args.expected_sha.strip().lower()
    report = {"schema": 1, "expected_sha": expected, "actual_sha": None,
              "tests": list(TESTS), "status": "FAIL", "exit_code": None}
    output = Path(args.report)
    try:
        if len(expected) != 40 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("expected SHA must be a full 40-digit commit hash")
        actual = subprocess.check_output(
            ["git", "rev-parse", "--verify", "HEAD"], text=True
        ).strip().lower()
        report["actual_sha"] = actual
        if actual != expected:
            raise ValueError("checked-out commit differs from expected PR head")
        for module in TESTS:
            path = Path("code") / Path(*module.split(".")).with_suffix(".py")
            if not path.is_file():
                raise ValueError(f"required test module absent: {path}")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            ["code", ".", env.get("PYTHONPATH", "")]
        )
        completed = subprocess.run(
            [args.python, "-m", "unittest", *TESTS, "-v"], env=env, check=False
        )
        report["exit_code"] = completed.returncode
        if completed.returncode != 0:
            raise RuntimeError("required unittest command failed")
        report["status"] = "PASS"
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        report["error"] = str(exc)
    finally:
        output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(run())
