"""Materialised operator-catalog artifact (G4
prerequisite P-G4-2; dossier design: bench Task 08,
gap G-1).

The admitted operator catalog from operator discovery
existed only as string lists inside the v4 evidence
record and was recomputed by ``run_discovery`` on every
run — no standalone file, no canonical serialisation,
no digest, so nothing existed whose digest the G4
instrument's C2 clause could match. This module is the
deterministic materialiser and the verified loader:

- ``materialize(evidence_path, out_path)`` reads a
  discovery evidence record, extracts the admitted
  operator keys and chains per defect class (exact
  string forms as recorded, sorted), and writes the
  canonical artifact file ``operator_catalog_v4.json``
  beside this module. Re-running it on the same evidence
  reproduces the artifact byte-for-byte.
- The artifact digest is SHA-256 over the canonical
  payload — ``{"artifact_name": ..., "classes": {...}}``
  serialised with sorted keys and compact separators —
  and is stored in the artifact as ``artifact_digest``.
- ``load_catalog`` / ``verify_catalog`` recompute the
  digest from the artifact's own content and refuse
  (or report) any artifact whose stored digest, name,
  or structure disagrees: the digest is the identity,
  never the file's mere presence.

The artifact is data. Applying its operators remains
the solver's existing ``apply_operator`` / ``apply_chain``
path; nothing here runs discovery.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ARTIFACT_NAME = "operator_catalog_v4"
ARTIFACT_VERSION = 1
ARTIFACT_FILENAME = "operator_catalog_v4.json"


def default_artifact_path() -> Path:
    return Path(__file__).with_name(ARTIFACT_FILENAME)


def _canonical_payload(artifact_name: str,
                       classes: dict[str, Any]) -> bytes:
    payload = {"artifact_name": artifact_name, "classes": classes}
    return json.dumps(payload, sort_keys=True,
                      separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def classes_digest(classes: dict[str, Any],
                   artifact_name: str = ARTIFACT_NAME) -> str:
    """SHA-256 over the canonical payload — the
    artifact's identity."""
    return hashlib.sha256(
        _canonical_payload(artifact_name, classes)).hexdigest()


def extract_classes(evidence: dict[str, Any]) -> dict[str, Any]:
    """Admitted operators/chains per class from a
    discovery evidence record (exact string forms,
    sorted for canonical form)."""
    classes: dict[str, Any] = {}
    by_class = evidence.get("by_class")
    if not isinstance(by_class, dict):
        raise ValueError("evidence has no by_class record")
    for cls in sorted(by_class):
        record = by_class[cls] or {}
        classes[cls] = {
            "operators": sorted(
                record.get("admitted_operators") or []),
            "chains": sorted(record.get("admitted_chains") or []),
        }
    return classes


def materialize(evidence_path: str | Path,
                out_path: str | Path | None = None) -> dict[str, Any]:
    """Build the catalog artifact from a discovery
    evidence file and write it deterministically.
    Returns the artifact dict."""
    evidence_bytes = Path(evidence_path).read_bytes()
    evidence = json.loads(evidence_bytes.decode("utf-8"))
    classes = extract_classes(evidence)
    artifact = {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": ARTIFACT_VERSION,
        "artifact_digest": classes_digest(classes),
        "source_evidence": "evidence/operator_discovery_v4.json",
        "source_evidence_sha256": hashlib.sha256(
            evidence_bytes).hexdigest(),
        "classes": classes,
    }
    dest = Path(out_path) if out_path is not None \
        else default_artifact_path()
    dest.write_text(json.dumps(artifact, indent=1, sort_keys=True,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return artifact


def verify_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Recompute the digest from the artifact's content
    and report every structural or identity problem."""
    src = Path(path) if path is not None else default_artifact_path()
    problems: list[str] = []
    try:
        artifact = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "artifact_digest": None,
                "problems": [f"artifact unreadable: {exc}"]}
    if not isinstance(artifact, dict):
        return {"valid": False, "artifact_digest": None,
                "problems": ["artifact is not a JSON object"]}
    if artifact.get("artifact_name") != ARTIFACT_NAME:
        problems.append(
            f"artifact_name is {artifact.get('artifact_name')!r}, "
            f"not {ARTIFACT_NAME!r}")
    classes = artifact.get("classes")
    if not isinstance(classes, dict) or not classes:
        problems.append("classes missing or empty")
        classes = {}
    for cls, record in classes.items():
        if not isinstance(record, dict) \
                or not isinstance(record.get("operators"), list) \
                or not isinstance(record.get("chains"), list):
            problems.append(f"class {cls!r}: operators/chains "
                            f"missing or not lists")
        elif record["operators"] != sorted(record["operators"]) \
                or record["chains"] != sorted(record["chains"]):
            problems.append(f"class {cls!r}: entries not in "
                            f"canonical (sorted) order")
    recomputed = classes_digest(classes,
                                artifact.get("artifact_name")
                                if isinstance(
                                    artifact.get("artifact_name"),
                                    str) else ARTIFACT_NAME)
    stored = artifact.get("artifact_digest")
    if stored != recomputed:
        problems.append(
            f"artifact_digest mismatch — stored {stored!r}, "
            f"recomputed {recomputed!r}")
    return {"valid": not problems, "artifact_digest": stored,
            "recomputed_digest": recomputed, "problems": problems}


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Load the artifact, verified. Raises ValueError on
    any problem — a catalog whose digest does not
    recompute is not the catalog."""
    report = verify_catalog(path)
    if not report["valid"]:
        raise ValueError("catalog artifact failed verification: "
                         + "; ".join(report["problems"]))
    src = Path(path) if path is not None else default_artifact_path()
    return json.loads(src.read_text(encoding="utf-8"))
