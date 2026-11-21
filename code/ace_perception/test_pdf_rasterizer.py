"""Verifier renderer Poppler lokal, roster halaman, dan kepemilikan saat ekspor."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _raster, pdf_rasterizer as model


def fixture_pdf():
    streams = [b"0 g 0 0 24 32 re f", b"0 g 30 0 30 10 re f"]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 80 40] /Contents 5 0 R >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 60 90] /Contents 6 0 R >>"]
    objects += [b"<< /Length %d >>\nstream\n" % len(item) + item + b"\nendstream" for item in streams]
    payload = b"%PDF-1.4\n"
    offsets = []
    for index, data in enumerate(objects, 1):
        offsets.append(len(payload))
        payload += b"%d 0 obj\n" % index + data + b"\nendobj\n"
    table = len(payload)
    payload += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects)+1)
    payload += b"".join(b"%010d 00000 n \n" % item for item in offsets)
    payload += b"trailer\n<< /Root 1 0 R /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects)+1, table)
    return payload


class PdfTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pdftoppm"), "pdftoppm lokal tidak tersedia")
    def test_actual_poppler_renders_two_distinct_pages_with_bounded_size(self):
        source = fixture_pdf()
        files, report = model.rasterize(source, first_page=1, last_page=2, long_edge=80)
        self.assertEqual(report["source_sha256"], sha256(source).hexdigest())
        self.assertEqual([item["page"] for item in report["pages"]], [1, 2])
        self.assertEqual(list(files), ["page-000001.pgm", "page-000002.pgm"])
        self.assertEqual([(item["width"], item["height"]) for item in report["pages"]], [(80, 40), (54, 80)])
        for row in report["pages"]:
            payload = files[row["file"]]
            image = _raster.decode(payload)
            self.assertEqual(row["bytes"], len(payload))
            self.assertEqual(row["sha256"], sha256(payload).hexdigest())
            self.assertEqual(min(image.pixels), 0)
            self.assertEqual(max(image.pixels), 255)
        self.assertNotEqual(*[item["sha256"] for item in report["pages"]])

    @unittest.skipUnless(shutil.which("pdftoppm"), "pdftoppm lokal tidak tersedia")
    def test_actual_cli_renders_one_selected_page_and_keeps_pdf(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        source = folder/"scan.pdf"
        pages = folder/"renders"
        sample = fixture_pdf()
        source.write_bytes(sample)
        args = [sys.executable, "-m", "ace_perception.pdf_rasterizer", str(source), "--output-dir", str(pages),
                "--first-page", "2", "--long-edge", "64"]
        run = subprocess.run(args, check=True, capture_output=True)
        manifest = json.loads(run.stdout)
        self.assertEqual(json.loads((pages/"manifest.json").read_bytes()), manifest)
        self.assertEqual([row["file"] for row in manifest["pages"]], ["page-000002.pgm"])
        self.assertEqual(source.read_bytes(), sample)
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)

    def test_work_bounds_and_missing_executable_before_process(self):
        for change in ({"long_edge": 31}, {"first_page": True}, {"last_page": 13},
                       {"timeout_seconds": 121}, {"last_page": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.rasterize(fixture_pdf(), **change)
        with self.assertRaisesRegex(ValueError, "PDF lokal"):
            model.rasterize(b"broken")
        with patch.object(model.shutil, "which", return_value=None), self.assertRaisesRegex(ValueError, "lokal diperlukan"):
            model.rasterize(fixture_pdf())

    def test_renderer_timeout_signal_and_no_page_all_fail_closed(self):
        with patch.object(model.shutil, "which", return_value="/tool/pdftoppm"):
            with patch.object(model.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 2)):
                with self.assertRaisesRegex(ValueError, "batas waktu"):
                    model.rasterize(fixture_pdf())
            with patch.object(model.subprocess, "run", return_value=subprocess.CompletedProcess([], 9)):
                with self.assertRaisesRegex(ValueError, "status 9"):
                    model.rasterize(fixture_pdf())
            with patch.object(model.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                with self.assertRaisesRegex(ValueError, "seluruh halaman"):
                    model.rasterize(fixture_pdf())

    def test_explicit_result_path_is_new_and_cannot_escape(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        with self.assertRaisesRegex(ValueError, "ekspor"):
            model.write_artifacts(folder/"out", {"../outside": b"bad"}, {})
        self.assertFalse((folder/"out").exists())
        self.assertFalse((folder/"outside").exists())
