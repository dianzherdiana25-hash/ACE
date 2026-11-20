"""Tes kelengkapan nama entri manifest bundle tanpa kebocoran nilai (AG26)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools import bridge_home
from tools.bundle_manifest_check import (
    OPTIONAL_ENTRY_NAMES,
    SCHEMA,
    check_bundle_manifest,
    main,
    render_markdown,
)


SCRIPT = Path(__file__).with_name("bundle_manifest_check.py")


class BundleManifestCheckTests(unittest.TestCase):
    def _write_manifest(self, path: Path, entries: list[dict]) -> None:
        path.write_text(
            json.dumps({"schema": bridge_home.BUNDLE_MANIFEST_SCHEMA, "entries": entries}),
            encoding="utf-8",
        )

    def test_complete_manifest_passes_and_never_emits_values(self) -> None:
        canary = "CANARY_SECRET_VALUE_MUST_NEVER_LEAK_8821"
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            all_names = [*bridge_home.REQUIRED_ENTRY_NAMES, *OPTIONAL_ENTRY_NAMES]
            self._write_manifest(path, [{"name": n, "value": canary, "note": canary} for n in all_names])
            report = check_bundle_manifest(path)
            self.assertEqual(report["schema"], SCHEMA)
            self.assertEqual(report["status"], "complete")
            self.assertTrue(report["has_all_required"])
            self.assertTrue(report["clean"])
            self.assertEqual(report["missing_required"], [])
            self.assertEqual(report["unexpected_names"], [])
            self.assertEqual(report["missing_optional"], [])
            self.assertNotIn(canary, json.dumps(report))
            self.assertNotIn(canary, render_markdown(report))

    def test_missing_required_entry_names_only_missing_name(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            self._write_manifest(path, [{"name": "groq-api-key"}, {"name": "gemini-api-key"}])
            report = check_bundle_manifest(path)
            self.assertEqual(report["status"], "missing_required")
            self.assertFalse(report["has_all_required"])
            self.assertFalse(report["clean"])
            self.assertEqual(report["missing_required"], ["gonka-api-key"])
            self.assertEqual(report["unexpected_names"], [])

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--manifest", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["missing_required"], ["gonka-api-key"])

    def test_unexpected_name_and_strict_mode_without_value_leak(self) -> None:
        canary = "ANOTHER_CANARY_TOKEN_5512"
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            self._write_manifest(
                path,
                [{"name": n} for n in bridge_home.REQUIRED_ENTRY_NAMES]
                + [{"name": "rogue-foreign-key", "secret": canary}],
            )
            report = check_bundle_manifest(path)
            self.assertEqual(report["status"], "unexpected_or_duplicate_entries")
            self.assertTrue(report["has_all_required"])
            self.assertFalse(report["clean"])
            self.assertEqual(report["unexpected_names"], ["rogue-foreign-key"])
            self.assertEqual(report["missing_required"], [])
            self.assertNotIn(canary, json.dumps(report))
            self.assertEqual(main(["--manifest", str(path)]), 0)
            self.assertEqual(main(["--manifest", str(path), "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
