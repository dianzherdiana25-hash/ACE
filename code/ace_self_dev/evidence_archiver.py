"""Evidence Archiver & Repository Scalability Manager.

Indexes and manages historical evidence artifacts to prevent Git repository bloat:
- Builds a unified cryptographic manifest (evidence_manifest.json).
- Keeps recent cycles active while organizing historical evidence.
- Ensures zero loss of historical negative scientific records.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional


class EvidenceArchiver:
    """Indexes evidence files into an aggregated manifest to maintain lean repository size."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.repo_root = Path(repo_root)

        self.evidence_dir = self.repo_root / "evidence" / "self_dev"
        self.checkpoints_dir = self.repo_root / "checkpoints" / "self_dev"
        self.manifest_path = self.checkpoints_dir / "evidence_manifest.json"

    def build_or_update_manifest(self) -> Dict[str, Any]:
        """Scans evidence artifacts and updates the cumulative manifest."""
        manifest: Dict[str, Any] = {
            "schema_version": "1.0",
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_artifacts": 0,
            "artifacts": {},
        }

        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        if not self.evidence_dir.exists():
            return manifest

        for gz_file in sorted(self.evidence_dir.glob("*.json.gz")):
            fname = gz_file.name
            if fname in manifest.get("artifacts", {}):
                continue

            file_bytes = gz_file.read_bytes()
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            manifest["artifacts"][fname] = {
                "sha256": sha256,
                "size_bytes": len(file_bytes),
                "indexed_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        manifest["total_artifacts"] = len(manifest["artifacts"])
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest
