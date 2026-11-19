"""Jalankan semua latihan tetap agar satu modul gagal tidak menyumbat trek belajar."""

from pathlib import Path, PurePosixPath
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_operational.autonomous_engine import LANGUAGE_CURRICULUM, TECHNICAL_CURRICULUM


class CurriculumIntegrityTests(unittest.TestCase):
    def test_unique_identity_and_learning_lab_paths(self) -> None:
        items = LANGUAGE_CURRICULUM + TECHNICAL_CURRICULUM
        text_fields = {
            "skill_name", "domain", "title", "goal", "target_file", "verification_str",
            "capability_id", "capability_name", "code",
        }
        list_fields = {"preconditions", "procedure_steps", "boundary_limitations"}
        for item in items:
            with self.subTest(skill=item.get("skill_name")):
                self.assertEqual(set(item), text_fields | list_fields)
                for field in text_fields:
                    self.assertIsInstance(item[field], str, field)
                    self.assertTrue(item[field].strip(), field)
                for field in list_fields:
                    self.assertIsInstance(item[field], list, field)
                    self.assertTrue(item[field], field)
                    self.assertTrue(all(isinstance(step, str) and step.strip() for step in item[field]), field)
                path = PurePosixPath(item["target_file"])
                self.assertTrue(path.is_relative_to("projects/learning_lab"), path)
                self.assertNotIn("..", path.parts)
                self.assertEqual(path.suffix, ".py")
        for field in ("skill_name", "capability_id", "capability_name",
                      "target_file", "verification_str"):
            with self.subTest(field=field):
                values = [item.get(field) for item in items]
                self.assertEqual(len(values), len(set(values)))

    def test_all_fixed_modules_pass_standalone_verification(self) -> None:
        for track, items in (("bahasa", LANGUAGE_CURRICULUM), ("teknis", TECHNICAL_CURRICULUM)):
            self.assertGreaterEqual(len(items), 12, track)
            for item in items:
                with self.subTest(track=track, skill=item["skill_name"]), TemporaryDirectory() as folder:
                    source = Path(folder) / PurePosixPath(item["target_file"]).name
                    source.write_text(item["code"], encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, "-I", "-B", str(source)],
                        cwd=folder,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=10,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                    self.assertIn(item["verification_str"], result.stdout, result.stderr)
