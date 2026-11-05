"""Issue #13 worker-only Bubblewrap adapter; no evaluator or oracle in mount.

This is an integration boundary, not a scientific scorer. A native Bubblewrap
runtime is mandatory: never fall back to in-process execution.
"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, integer, read_json, require_fields
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_isolation import validate_boundary
from .e14_integrated_graph import graph_cost
from .e14_shared_budget import BudgetContractError

HERE = Path(__file__).resolve().parent
WORKER_FILES = (
    "e14_integrated_policy.py",
    "e14r_worker.py", "e14s_worker.py", "e14p_worker.py",
)
# e14p_worker imports only e13.contract. No trusted evaluator code is copied.
FORBIDDEN = (
    "e14.e14_integrated_graph", "e14.e14p_graph", "e14.e14_integrated_isolation",
    "e14.e14o_run", "e14.e14q_run", "e14.e14g_bank",
)


@contextmanager
def worker_stage():
    with tempfile.TemporaryDirectory(prefix="ace-e14t-solver-") as temp:
        root = Path(temp)
        for package in ("e13", "e14"):
            (root / package).mkdir()
            (root / package / "__init__.py").write_text("", encoding="utf-8")
        shutil.copyfile(HERE.parent / "e13/contract.py", root / "e13/contract.py")
        for name in WORKER_FILES:
            shutil.copyfile(HERE / name, root / "e14" / name)
        yield root


def worker_invoke(root, packet):
    script = (
        "import sys,resource; sys.path.insert(0, '/solver'); "
        "from e13.contract import canonical_json,read_json,require_fields; "
        "from e14.e14_integrated_policy import mapped_only_policy; "
        "p=read_json(sys.stdin.buffer.read(65537),65536); "
        "require_fields(p,'artifact','mode','view'); "
        "a=mapped_only_policy(p['artifact'],p['mode'])(p['view']); "
        "u=resource.getrusage(resource.RUSAGE_SELF); "
        "r={'action':a,'cpu_us':round(1000000*(u.ru_utime+u.ru_stime)),"
        "'rss_kib':u.ru_maxrss}; "
        "sys.stdout.buffer.write(canonical_json(r))"
    )
    raw, wall = _sandbox_python(["-c", script], canonical_json(packet), solver=root)
    response = read_json(raw, 24_576)
    require_fields(response, "action", "cpu_us", "rss_kib")
    cpu = integer(response.pop("cpu_us"), 0, 1_000_000)
    rss = integer(response.pop("rss_kib"), 1, 131_072)
    wall = integer(wall, 0, 3_000_000)
    action = response.pop("action")
    if type(action) is not dict or action.get("action") not in ("query", "reuse", "abstain", "accept"):
        raise BudgetContractError("invalid isolated worker action")
    if action["action"] == "query":
        if set(action) != {"action", "stage", "graph"}:
            raise BudgetContractError("invalid worker query shape")
        graph_cost(action["graph"])  # evaluator-side topology verification
    elif action["action"] == "reuse":
        if set(action) != {"action", "stage", "receipt_id"}:
            raise BudgetContractError("invalid worker reuse shape")
    elif action["action"] == "abstain":
        if set(action) != {"action"}:
            raise BudgetContractError("invalid worker abstention shape")
    else:
        if (set(action) != {"action", "word"} or type(action["word"]) is not list
                or not 1 <= len(action["word"]) <= 12
                or any(type(x) is not int or x not in (1, 2) for x in action["word"])):
            raise BudgetContractError("invalid worker acceptance shape")
    return action, {"cpu_us": cpu, "rss_kib": rss, "wall_us": wall}


def validate_worker_mount(root):
    """Exercise native sandbox and explicitly test import denial."""
    validate_boundary()
    probe = (
        "import importlib.util,sys,json;sys.path.insert(0,'/solver');"
        f"print(json.dumps({{name:importlib.util.find_spec(name) is None for name in {FORBIDDEN!r}}}))"
    )
    raw, _ = _sandbox_python(["-c", probe], solver=root)
    checks = read_json(raw, 4096)
    if set(checks) != set(FORBIDDEN) or not all(v is True for v in checks.values()):
        raise RuntimeError("integrated worker can import trusted evaluator")
    return checks


def execute_isolated(journal, artifact, mode, oracle, *, max_actions=16):
    """Run policy in a new sandbox for every action; evaluator alone calls oracle."""
    from .e14_integrated_graph import purchase

    if type(max_actions) is not int or not 1 <= max_actions <= 32:
        raise BudgetContractError("invalid action cap")
    with worker_stage() as root:
        checks = validate_worker_mount(root)
        actions, meters = [], []
        for _ in range(max_actions):
            snapshot = journal.snapshot()
            # Minimal observation view: no hidden target, oracle, bank or probes.
            view = {"receipts": snapshot["receipts"], "remaining": snapshot["remaining"]}
            action, meter = worker_invoke(root, {"artifact": artifact, "mode": mode, "view": view})
            meters.append(meter)
            kind = action["action"]
            if kind == "query":
                rid, label = purchase(journal, action["stage"], action["graph"], oracle)
                actions.append({"action": "query", "stage": action["stage"],
                                "receipt_id": rid, "label": label})
            elif kind == "reuse":
                label = journal.reuse(action["receipt_id"], action["stage"])
                actions.append({**action, "label": label})
            else:
                journal.assert_complete()
                actions.append(action)
                return {"status": "completed", "decision": kind, "actions": actions,
                        "journal": journal.snapshot(), "resources": meters,
                        "isolation_checks": checks}
    raise BudgetContractError("isolated action cap exhausted")
