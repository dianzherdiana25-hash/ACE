"""Verify and restore a reviewed portability bundle into an inactive preview."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory

from tools.instance_kit import load_instance_config, validate_isolation
from tools.portability_pack import normalize_rel_path, verify_bundle

SCHEMA = "ace.migration-rehearsal.v1"
EXCLUDED = ("credential", "secret", "token", ".pem", ".key", "ledger", "utang",
            "prereg", "sealed", "evo-0007", "evo_0007")


def _path_allowed(path):
    parts = PurePosixPath(path).parts
    return (normalize_rel_path(path) == path and
            not any(part.startswith(".") for part in parts) and
            not any(fragment in path.casefold() for fragment in EXCLUDED))


def rehearse(bundle, source_config, target_config, *, expected_manifest_sha256):
    if not isinstance(expected_manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256):
        raise ValueError("a trusted source manifest SHA-256 is required")
    if any(cfg.get("foundation_only") is not True for cfg in (source_config, target_config)):
        raise ValueError("both configurations must declare an inactive foundation")
    check = validate_isolation([source_config, target_config])
    if not check["isolated"]:
        codes = sorted({item["kind"] for item in check["violations"]})
        raise ValueError("instance isolation failed: " + ", ".join(codes))
    workspace = Path(target_config["directories"]["workspace_dir"])
    if not workspace.is_dir() or not workspace.is_absolute():
        raise ValueError("target workspace must already exist as an absolute directory")
    verified, payload = verify_bundle(Path(bundle))
    if not verified["ok"] or not payload:
        raise ValueError("portability bundle failed integrity verification")
    if any(not _path_allowed(path) for path in payload):
        raise ValueError("bundle contains a path outside the migration rehearsal policy")

    entries = [
        {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for path, data in sorted(payload.items())
    ]
    digest = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != expected_manifest_sha256:
        raise ValueError("verified bundle does not match the trusted source manifest")
    # Use the verified bytes directly. The input bundle is not opened again
    # between validation and the restore drill.
    with TemporaryDirectory(prefix=".ace-migration-rehearsal-", dir=workspace) as temporary:
        restored = Path(temporary)
        for entry in entries:
            path = entry["path"]
            destination = restored / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(payload[path])
            if hashlib.sha256(destination.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("restored file differs from verified source bytes")
    return {
        "schema": SCHEMA, "manifest_sha256": digest,
        "restored_and_rechecked": len(entries), "isolation_passed": True,
        "preview_cleaned": True, "activation_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("source_config", type=Path)
    parser.add_argument("target_config", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = rehearse(args.bundle, load_instance_config(args.source_config),
                          load_instance_config(args.target_config),
                          expected_manifest_sha256=args.manifest_sha256)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"migration rehearsal: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
