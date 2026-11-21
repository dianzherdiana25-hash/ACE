"""Verifier ffmpeg/ffprobe lokal, cap waktu lintas proses, dan roster frame."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ace_perception import _raster, video_frame_sampler as model


BINARIES = shutil.which("ffmpeg") and shutil.which("ffprobe")


@unittest.skipUnless(BINARIES, "alat video lokal tidak tersedia")
class LocalVideoTests(unittest.TestCase):
    def test_ffv1_fixture_only_returns_declared_number_of_keyframes(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        vid = folder/"fixture.mkv"
        frames = []
        for shift in (5, 13, 17, 23):
            pixels = [220]*(40*32)
            for y in range(4, 18):
                for x in range(shift, shift+5):
                    pixels[y*40+x] = 10
            frames += pixels
        create = [shutil.which("ffmpeg"), "-v", "error", "-f", "rawvideo", "-pixel_format", "gray",
                  "-video_size", "40x32", "-framerate", "2", "-i", "-", "-c:v", "ffv1", "-g", "1",
                  "-threads", "1", str(vid)]
        subprocess.run(create, input=bytes(frames), capture_output=True, check=True)
        sample = vid.read_bytes()
        outputs, report = model.sample(sample, maximum_frames=3, long_edge=40, scan_seconds=4)
        self.assertEqual(report["source_sha256"], sha256(sample).hexdigest())
        self.assertEqual(report["keyframes_in_probe"], 4)
        self.assertEqual([row["time_us"] for row in report["frames"]], [0, 500_000, 1_000_000])
        self.assertEqual([row["file"] for row in report["frames"]], list(outputs))
        for index, artifact in enumerate(report["frames"]):
            image = _raster.decode(outputs[artifact["file"]])
            self.assertEqual(image.pixels, tuple(frames[index*1280:(index+1)*1280]))
            self.assertEqual((image.width, image.height), (40, 32))
            self.assertEqual(sha256(outputs[artifact["file"]]).hexdigest(), artifact["sha256"])
        out = folder/"export"
        model._write(out, outputs, report)
        self.assertEqual(json.loads((out/"manifest.json").read_bytes()), report)
        with self.assertRaises(FileExistsError):
            model._write(out, outputs, report)
        self.assertEqual(vid.read_bytes(), sample)


class VideoValidationTests(unittest.TestCase):
    def test_roster_rejects_duplicate_or_unavailable_timestamps_and_nonkeyframes(self):
        frame = {"key_frame": 1, "best_effort_timestamp_time": "1.250000"}
        valid = {"frames": [frame]}
        self.assertEqual(model._entries(model._canonical(valid), 9), ([1_250_000], 1))
        for rows in ([], [frame, frame], [{**frame, "key_frame": 0}],
                     [{**frame, "best_effort_timestamp_time": "N/A"}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                model._entries(model._canonical({"frames": rows}), 1)

    def test_render_log_checks_same_timebase_instead_of_count_only(self):
        fixture = b"""[Parsed_showinfo_2 @ fixture] config in time_base: 1/1000, frame_rate: 2/1
[Parsed_showinfo_2 @ fixture] n:   0 pts:      0 pts_time:0
[Parsed_showinfo_2 @ fixture] n:   1 pts:    500 pts_time:0.5"""
        model._check_render_times(fixture, [0, 500_000])
        with self.assertRaisesRegex(ValueError, "berbeda"):
            model._check_render_times(fixture, [0, 500_450])
        with self.assertRaisesRegex(ValueError, "tidak lengkap"):
            model._check_render_times(fixture, [0, 500_000, 1_000_000])

    def test_local_dependency_and_timeout_diagnosed(self):
        with patch.object(model.shutil, "which", return_value=None), self.assertRaisesRegex(ValueError, "lokal diperlukan"):
            model.sample(b"video")
        with patch.object(model.subprocess, "run", side_effect=subprocess.TimeoutExpired("tool", 1)):
            with self.assertRaisesRegex(ValueError, "batas waktu"):
                model._invoke(["tool"], ".", 1, subprocess.DEVNULL)
        for change in ({"maximum_frames": False}, {"long_edge": 801}, {"scan_seconds": 0}, {"timeout_seconds": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.sample(b"video", **change)
