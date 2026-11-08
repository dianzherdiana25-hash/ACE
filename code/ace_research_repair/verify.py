"""Fail-closed provenance, AST-custody, governance, and exact-replay verifier for `ace.repair.v1`."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .corpus import (
    ARMS,
    PRESCORE_COMMIT,
    PRESCORE_DOC_SHA256,
    canonical_json,
    sha256_digest,
)
from .runner import (
    REPORT_SCHEMA,
    compress_deterministic_gzip,
    decompress_gzip,
    run_benchmark,
)

ISOLATED_REPAIR_MODULES = (
    "__init__.py",
    "corpus.py",
    "sandbox.py",
    "operators.py",
    "represent.py",
    "memory.py",
    "engine.py",
)


class RepairVerificationError(ValueError):
    """Raised when a repair evidence bundle fails custody, schema, or replay verification."""


def verify_ast_isolation(package_dir: Path | None = None) -> int:
    """Ensure `evaluator.py` is never imported or dynamically loaded by non-evaluator modules."""
    pkg = (package_dir or Path(__file__).resolve().parent).resolve()
    checked = 0
    for filename in ISOLATED_REPAIR_MODULES:
        mod_path = pkg / filename
        source = mod_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(mod_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "evaluator" in alias.name.split("."):
                        raise RepairVerificationError(f"forbidden evaluator import in {filename}")
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                if "evaluator" in mod_name.split(".") or any(
                    a.name == "evaluator" for a in node.names
                ):
                    raise RepairVerificationError(f"forbidden evaluator from-import in {filename}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("__import__", "exec", "eval") and filename != "sandbox.py":
                    raise RepairVerificationError(f"forbidden dynamic code call in {filename}")
            elif isinstance(node, ast.Attribute) and node.attr == "import_module":
                raise RepairVerificationError(f"forbidden importlib usage in {filename}")
        checked += 1
    return checked


def verify_upstream_pins(repo_root: Path) -> int:
    manifest = json.loads((repo_root / "docs/UPSTREAM_SOURCES.json").read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if manifest.get("schema") != "ace.source-integration.v1" or len(files) != 25:
        raise RepairVerificationError("upstream manifest schema or count mismatch")
    for rel, meta in sorted(files.items()):
        path = (repo_root / rel).resolve(strict=True)
        raw = path.read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if git_blob != meta.get("git_blob"):
            raise RepairVerificationError(f"upstream blob modified: {rel}")
    return len(files)


def _require_strict_bool(mapping: dict[str, Any], key: str, expected: bool | None = None) -> bool:
    val = mapping.get(key)
    if type(val) is not bool:
        raise RepairVerificationError(f"field {key!r} must be a strict JSON boolean")
    if expected is not None and val is not expected:
        raise RepairVerificationError(f"field {key!r} expected {expected}, got {val}")
    return val


def verify_report_bytes(
    artifact_bytes: bytes,
    *,
    repo_root: Path | None = None,
    replay: bool = True,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()

    # 1. Verify AST custody and upstream pins
    isolated_count = verify_ast_isolation(root / "code/ace_research_repair")
    pinned_count = verify_upstream_pins(root)

    prescore_path = root / "docs/ACE_REPAIR_PRESCORE_V1.md"
    if not prescore_path.is_file():
        raise RepairVerificationError("missing docs/ACE_REPAIR_PRESCORE_V1.md")
    actual_prescore_sha = sha256_digest(prescore_path.read_bytes())
    if actual_prescore_sha != PRESCORE_DOC_SHA256:
        raise RepairVerificationError("pre-score protocol markdown modified post-registration")

    # 2. Decompress deterministic gzip if compressed, and verify canonical JSON bytes
    is_gzip = artifact_bytes[:2] == b"\x1f\x8b"
    if is_gzip:
        try:
            raw_json = decompress_gzip(artifact_bytes)
        except OSError as exc:
            raise RepairVerificationError("corrupted gzip stream") from exc
        if compress_deterministic_gzip(raw_json) != artifact_bytes:
            raise RepairVerificationError("non-deterministic gzip header or stream bytes")
    else:
        raw_json = artifact_bytes

    try:
        report = json.loads(raw_json.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RepairVerificationError("invalid UTF-8 JSON report") from exc

    if type(report) is not dict or canonical_json(report) != raw_json:
        raise RepairVerificationError("noncanonical JSON formatting or root type")

    # 3. Provenance and governance checks
    if report.get("schema") != REPORT_SCHEMA:
        raise RepairVerificationError("unsupported repair report schema")
    if report.get("protocol_commit") != PRESCORE_COMMIT:
        raise RepairVerificationError("protocol_commit mismatch")
    if report.get("protocol_doc_sha256") != PRESCORE_DOC_SHA256:
        raise RepairVerificationError("protocol_doc_sha256 mismatch")
    if report.get("scientific_decision") != "NOT_ASSESSED":
        raise RepairVerificationError("untrusted scientific_decision promotion")
    if report.get("release_gate") != "BLOCK_RELEASE":
        raise RepairVerificationError("untrusted release_gate promotion")

    _require_strict_bool(report, "oaie_established", False)
    _require_strict_bool(report, "candidate_deployed", False)
    _require_strict_bool(report, "open_world_safe", False)
    _require_strict_bool(report, "budget_matched", True)

    flags = report.get("evidence_flags")
    if type(flags) is not dict:
        raise RepairVerificationError("missing evidence_flags")
    _require_strict_bool(flags, "ACE_BASE_RUNTIME_EXECUTED", True)
    _require_strict_bool(flags, "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED", True)
    _require_strict_bool(flags, "SCIENTIFIC_CAPABILITY_VALIDATED")

    for h_name, h_obj in (report.get("hypotheses") or {}).items():
        if type(h_obj) is not dict:
            raise RepairVerificationError(f"malformed hypothesis entry: {h_name}")
        _require_strict_bool(h_obj, "passed")

    for arm in ARMS:
        rows = (report.get("target_trials_by_arm") or {}).get(arm)
        if type(rows) is not list or len(rows) != 18:
            raise RepairVerificationError(f"expected 18 target trials for {arm}")
        for row in rows:
            _require_strict_bool(row, "staged")
            _require_strict_bool(row, "abstained")
            if row["staged"] == row["abstained"]:
                raise RepairVerificationError("contradictory staged/abstained flags")
            if type(row.get("total_candidate_sandbox_evals")) is not int or not (
                0 <= row["total_candidate_sandbox_evals"] <= report["budget_k"]
            ):
                raise RepairVerificationError(f"budget violation in {arm}/{row.get('unit_id')}")
            term = row.get("terminal")
            if type(term) is not dict:
                raise RepairVerificationError("missing terminal evaluation receipt")
            _require_strict_bool(term, "terminal_all_passed")
            _require_strict_bool(term, "overfit_false_admission")

    # 4. Full deterministic replay check
    if replay:
        expected = run_benchmark()
        if canonical_json(expected) != raw_json:
            raise RepairVerificationError("reported metrics, patches, or hashes differ from clean replay")

    return {
        "status": "PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO" if replay else "PASS_STRUCTURE_AND_CUSTODY_ONLY",
        "canonical_json_sha256": sha256_digest(raw_json),
        "artifact_sha256": sha256_digest(artifact_bytes),
        "isolated_modules_verified": isolated_count,
        "upstream_pins_verified": pinned_count,
        "replay_verified": replay,
        "nominal_verified": {
            arm: report["arm_summaries"][arm]["nominal_terminal_verified"] for arm in ARMS
        },
        "scientific_decision": report["scientific_decision"],
        "release_gate": report["release_gate"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=Path("evidence/repair/ace_repair_v1.json.gz"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="Optional artifact path alias",
    )
    args = parser.parse_args(argv)
    target_path = args.artifact or args.report
    try:
        receipt = verify_report_bytes(target_path.read_bytes(), replay=True)
    except (RepairVerificationError, ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "HALT_INVALID_REPAIR_EVIDENCE", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
