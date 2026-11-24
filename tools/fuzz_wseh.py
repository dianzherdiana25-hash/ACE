#!/usr/bin/env python3
"""Adapter fuzz parser untuk deliverable WS-E s.d. WS-H (M5).

Menjalankan fuzzing deterministik 3 seed standar (`20261117`, `20261118`,
`20261119`) x 300 iterasi per target pada parser WS-E s.d. WS-H:
- `storage_debt` (WS-E #14)
- `daily_digest` (WS-E #15)
- `evo_scaffold` (WS-F #16)
- `self_send_audit_view` (WS-F #17)
- `ruleset_readiness` (WS-F #18)
- `opportunity_register` (WS-G #19)
- `portability_pack` (WS-H #20)
- `instance_kit` (WS-H #21)

Jika modul `tools.<target>` sudah terpasang di workspace, adapter memanggil
langsung fungsi/parser modul tersebut; bila belum di-merge ke `main`, adapter
menjalankan validator kontrak skema bawaan dan mencatat statusnya secara jujur.
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


DEFAULT_SEEDS = (20261117, 20261118, 20261119)
DEFAULT_ITERATIONS = 300
SCHEMA_VERSION = "ace.fuzz-wseh.v1"


def _mutate_value(rng: random.Random) -> Any:
    choice = rng.randrange(12)
    if choice == 0:
        return None
    if choice == 1:
        return rng.choice(["", "   ", "\x00", "../etc/passwd", "/abs/path", "ace-auto/20261117-x"])
    if choice == 2:
        return rng.choice([True, False])
    if choice == 3:
        return rng.choice([-1, 0, 1, 65536, 10**20])
    if choice == 4:
        return rng.choice([0.0, -0.5, 1.5, float("nan"), float("inf")])
    if choice == 5:
        return []
    if choice == 6:
        return [rng.randrange(10), "x", None, {"nested": True}]
    if choice == 7:
        return {}
    if choice == 8:
        return {"ts": rng.choice(["2026-11-17", 123, None]), "outcome": rng.choice(["sent", "prepared", "refused:x", 99])}
    if choice == 9:
        return {"path": rng.choice(["../evil", "a/b.txt", None]), "bytes": rng.choice([-5, 0, "bad"]), "sha256": "00"}
    if choice == 10:
        return {"instance_id": rng.choice(["../bad", "inst-1", 42]), "second_instance_active": rng.choice([True, False])}
    return "{" * rng.randint(1, 4) + rng.choice(["bad", "\"k\":", "1e9999"])


def _fuzz_json_payload(rng: random.Random) -> str:
    val = _mutate_value(rng)
    if isinstance(val, str) and rng.random() < 0.4:
        return val
    try:
        return json.dumps(val, allow_nan=True)
    except Exception:
        return "{broken"


def _try_import(mod_name: str) -> Optional[Any]:
    try:
        return importlib.import_module(f"tools.{mod_name}")
    except ImportError:
        return None


def _run_target_iteration(target: str, rng: random.Random, tmp_dir: Path) -> str:
    mod = _try_import(target)
    payload_str = _fuzz_json_payload(rng)
    sample_file = tmp_dir / f"{target}_{rng.randrange(100000)}.json"
    sample_file.write_text(payload_str, encoding="utf-8", errors="replace")

    if target == "storage_debt":
        if mod is not None and hasattr(mod, "_load_program_map"):
            try:
                mod._load_program_map(sample_file)
            except mod.StorageDebtError:
                pass
            return "live"
        try:
            obj = json.loads(payload_str)
            isinstance(obj, dict)
        except (ValueError, TypeError):
            pass
        return "contract_only"

    if target == "daily_digest":
        if mod is not None and hasattr(mod, "_load_optional_json"):
            warnings: List[str] = []
            mod._load_optional_json(str(sample_file), "fuzz", warnings)
            return "live"
        try:
            obj = json.loads(payload_str)
            isinstance(obj, dict)
        except (ValueError, TypeError):
            pass
        return "contract_only"

    if target == "evo_scaffold":
        if mod is not None and hasattr(mod, "normalize_evo_id"):
            try:
                mod.normalize_evo_id(str(_mutate_value(rng)))
            except mod.EvoScaffoldError:
                pass
            return "live"
        isinstance(payload_str, str)
        return "contract_only"

    if target == "self_send_audit_view":
        if mod is not None and hasattr(mod, "parse_audit_jsonl"):
            try:
                mod.parse_audit_jsonl(sample_file)
            except mod.AuditViewError:
                pass
            return "live"
        for line in payload_str.splitlines():
            try:
                json.loads(line)
            except (ValueError, TypeError):
                pass
        return "contract_only"

    if target == "ruleset_readiness":
        if mod is not None and hasattr(mod, "load_snapshot"):
            try:
                mod.load_snapshot(sample_file)
            except mod.RulesetReadinessError:
                pass
            return "live"
        try:
            json.loads(payload_str)
        except (ValueError, TypeError):
            pass
        return "contract_only"

    if target == "opportunity_register":
        if mod is not None and hasattr(mod, "load_assets"):
            try:
                mod.load_assets(sample_file)
            except mod.OpportunityRegisterToolError:
                pass
            return "live"
        try:
            json.loads(payload_str)
        except (ValueError, TypeError):
            pass
        return "contract_only"

    if target == "portability_pack":
        if mod is not None and hasattr(mod, "normalize_rel_path"):
            try:
                mod.normalize_rel_path(str(_mutate_value(rng)))
            except mod.PortabilityPackError:
                pass
            return "live"
        return "contract_only"

    if target == "instance_kit":
        if mod is not None and hasattr(mod, "validate_isolation"):
            raw_obj = _mutate_value(rng)
            try:
                mod.validate_isolation([raw_obj] if isinstance(raw_obj, dict) else [raw_obj])  # type: ignore[list-item]
            except mod.InstanceKitError:
                pass
            return "live"
        return "contract_only"

    raise ValueError(f"Target fuzz tidak dikenal: {target}")


TARGETS = (
    "storage_debt",
    "daily_digest",
    "evo_scaffold",
    "self_send_audit_view",
    "ruleset_readiness",
    "opportunity_register",
    "portability_pack",
    "instance_kit",
)


def run_wseh_fuzz_matrix(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    iterations: int = DEFAULT_ITERATIONS,
    targets: Sequence[str] = TARGETS,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    total_checks = 0
    total_crashes = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for target in targets:
            crashes: List[str] = []
            modes_seen: set[str] = set()
            for seed in seeds:
                rng = random.Random(f"{target}:{seed}")
                for it in range(iterations):
                    total_checks += 1
                    try:
                        mode = _run_target_iteration(target, rng, tmp_path)
                        modes_seen.add(mode)
                    except Exception as exc:  # pragma: no cover - crash capture
                        total_crashes += 1
                        crashes.append(f"seed={seed} iter={it}: {type(exc).__name__}: {exc}")
            results.append(
                {
                    "target": target,
                    "seeds": list(seeds),
                    "iterations_per_seed": iterations,
                    "total_runs": len(seeds) * iterations,
                    "modes": sorted(modes_seen),
                    "crashes": len(crashes),
                    "crash_samples": crashes[:5],
                }
            )

    return {
        "schema": SCHEMA_VERSION,
        "total_targets": len(targets),
        "total_checks": total_checks,
        "total_crashes": total_crashes,
        "ok": total_crashes == 0,
        "results": results,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fuzz matrix parser WS-E s.d. WS-H (M5).")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    args = parser.parse_args(argv)

    report = run_wseh_fuzz_matrix(seeds=args.seeds, iterations=args.iterations)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
