"""Tes peta celah tes tools/test_coverage_map.py pada pohon fixture sementara."""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from contextlib import redirect_stdout

from tools.test_coverage_map import SCHEMA, build_coverage_map, main


SCRIPT = Path(__file__).with_name("test_coverage_map.py")


class TestCoverageMapTests(unittest.TestCase):
    def test_maps_untested_modules_sorted_by_size_and_excludes_tested_and_forbidden(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo_fixture"
            tools = root / "tools"
            tools.mkdir(parents=True)

            # Modul teruji langsung (punya test_covered.py) -> tidak masuk missing_matching_test_file
            (tools / "covered.py").write_text("x = 1\n" * 40, encoding="utf-8")
            (tools / "test_covered.py").write_text("from tools import covered\n", encoding="utf-8")

            # Modul teruji lewat nama lain (imported_only.py) -> masuk missing_matching_test_file, bukan untested_all_gaps
            (tools / "imported_only.py").write_text("def f():\n    return 1\n" * 30, encoding="utf-8")
            (tools / "test_bundle_misc.py").write_text("from tools import imported_only\n", encoding="utf-8")

            # Tiga modul CLI tanpa tes sama sekali dengan ukuran berbeda (terurut besar -> kecil)
            (tools / "small_cli.py").write_text(
                "import argparse\ndef main():\n    argparse.ArgumentParser().parse_args()\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )
            (tools / "big_cli.py").write_text(
                "import argparse\n" + ("# padding\n" * 25) + "def main():\n    argparse.ArgumentParser().parse_args()\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )
            (tools / "mid_cli.py").write_text(
                "import argparse\n" + ("# padding\n" * 10) + "def main():\n    argparse.ArgumentParser().parse_args()\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )

            # Modul wilayah terlarang wajib dilewati secara default
            (tools / "abc_v3_run.py").write_text("# forbidden\n" * 100, encoding="utf-8")

            report = build_coverage_map(root)
            self.assertEqual(report["schema"], SCHEMA)
            self.assertEqual(
                [item["module"] for item in report["untested_cli_gaps"]],
                ["big_cli.py", "mid_cli.py", "small_cli.py"],
            )
            sizes = [item["size_bytes"] for item in report["untested_cli_gaps"]]
            self.assertEqual(sizes, sorted(sizes, reverse=True))
            self.assertNotIn("abc_v3_run.py", [item["module"] for item in report["untested_all_gaps"]])
            self.assertNotIn("covered.py", [item["module"] for item in report["missing_matching_test_file"]])
            self.assertIn("imported_only.py", [item["module"] for item in report["missing_matching_test_file"]])

    def test_cli_help_json_and_markdown_output(self) -> None:
        help_proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_proc.returncode, 0)
        self.assertIn("--format", help_proc.stdout)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            tools = root / "tools"
            tools.mkdir(parents=True)
            (tools / "alpha.py").write_text(
                "import argparse\nif __name__ == '__main__':\n    argparse.ArgumentParser().parse_args()\n",
                encoding="utf-8",
            )
            out_md = Path(tmp) / "map.md"
            self.assertEqual(main(["--root", str(root), "--format", "markdown", "--output", str(out_md)]), 0)
            self.assertIn("tools/alpha.py", out_md.read_text(encoding="utf-8"))

            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(main(["--root", str(root), "--format", "json"]), 0)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(parsed["summary"]["untested_cli_gaps"], 1)


if __name__ == "__main__":
    unittest.main()
