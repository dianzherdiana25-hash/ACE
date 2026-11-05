"""Fail-closed Issue #13 engineering readiness gate (never claims scientific GO).

Run from repo root with PYTHONPATH=code:. . Missing native isolation, an
unfrozen bank, or absent independent scoring always yield SCIENTIFIC_OPEN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

MODULES = (
    "e14.test_e14_integrated_graph",
    "e14.test_e14_integrated_policy",
    "e14.test_e14_issue13_smoke",
    "e14.test_e14_integrated_isolation",
    "e14.test_e14t_extension",
)
REQUIRED = (
    "code/e14/e14_integrated_graph.py",
    "code/e14/e14_integrated_policy.py",
    "code/e14/e14_integrated_isolation.py",
    "code/e14/e14t_extension.py",
    "design/e1.4/E14T_INTEGRATED_GRAPH_PROTOCOL_DRAFT_v0.md",
)


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate(root):
    root = Path(root).resolve()
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(root/"code"),str(root)))}
    missing = [name for name in REQUIRED if not (root/name).is_file()]
    if missing:
        return {"status":"BLOCKED_MISSING_SOURCE","missing":missing,
                "scientific_decision":"OPEN"}
    command = [sys.executable,"-W","error::ResourceWarning","-m","unittest",*MODULES,"-v"]
    try:
        result = subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,
                                timeout=120,check=False)
        tests = {"status":"PASS" if result.returncode == 0 else "FAIL",
                 "returncode":result.returncode,
                 "stdout_tail":result.stdout[-4096:],
                 "stderr_tail":result.stderr[-4096:]}
    except subprocess.TimeoutExpired:
        tests = {"status":"TIMEOUT","returncode":None}
    try:
        from e14.e14g_isolation import validate_boundary
        boundary = validate_boundary()
        isolation = {"status":"PASS","checks":boundary["checks"],
                     "binary_sha256":boundary["sha256"]}
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        isolation = {"status":"BLOCKED_ENV","reason":type(exc).__name__}
    files = {p:file_sha(root/p) for p in REQUIRED}
    return {"status":"ENGINEERING_READY" if tests["status"]=="PASS"
            and isolation["status"]=="PASS" else "ENGINEERING_INCOMPLETE",
            "scientific_decision":"OPEN","isolation":isolation,"tests":tests,
            "source_sha256":files,
            "not_verified":["worker exact-head end-to-end science",
                            "representation expansion in isolated worker",
                            "new frozen bank and thresholds",
                            "full repository regression",
                            "independent score/replay/audit"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    report = gate(args.root)
    encoded = json.dumps(report,sort_keys=True,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        temp = args.output.with_name(args.output.name+".tmp")
        temp.write_text(encoded,encoding="utf-8")
        os.replace(temp,args.output)
    print(encoded,end="")
    return 0 if report["status"]=="ENGINEERING_READY" else 2


if __name__ == "__main__":
    sys.exit(main())
