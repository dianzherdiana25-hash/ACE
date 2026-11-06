"""Verify imported source bytes against recorded Git blob IDs, without network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def verify(root: Path) -> int:
    root = root.resolve()
    manifest = json.loads((root / "docs/UPSTREAM_SOURCES.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "ace.source-integration.v1":
        raise ValueError("unsupported source manifest schema")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("source manifest must contain a nonempty files mapping")

    for name, source in sorted(files.items()):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"invalid source path: {name}")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError(f"source path escapes repository: {name}")
        expected = source.get("git_blob") if isinstance(source, dict) else None
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise ValueError(f"invalid Git blob ID: {name}")
        content = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()
        if actual != expected:
            raise ValueError(f"source mismatch: {name}: expected {expected}, got {actual}")
    return len(files)


def main() -> int:
    try:
        count = verify(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, TypeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {count} imported files match their recorded Git blob IDs (offline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
