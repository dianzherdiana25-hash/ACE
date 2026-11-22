from hashlib import sha256
from pathlib import Path
from shutil import which
import unittest

from ._audio import parse_wav
from ._contracts import ContractError, decode, identity
from ._raster import raster
from .studio_bench import run_bench


class StudioBenchTests(unittest.TestCase):
    @unittest.skipUnless(all(map(which, ("blender", "ffmpeg", "ffprobe"))), "Backend studio lokal diperlukan")
    def test_closed_fixture_has_verified_movie_cover_audio_and_distinct_poses(self):
        fixtures = Path(__file__).parent / "fixtures"
        plan = decode((fixtures / "closed_studio_bench.json").read_bytes())
        outputs, report = run_bench(plan, identity(plan))
        self.assertEqual(report["status"], "fixture_pass")
        self.assertEqual((report["qa"]["passed"], report["qa"]["total"]), (10, 10))
        self.assertEqual((report["character"]["passed_landmarks"], report["character"]["landmarks"]), (20, 20))
        self.assertEqual(len(outputs), 7)
        self.assertEqual(parse_wav(outputs["audio_mix.wav"]).frames, 8000)
        self.assertEqual(raster(outputs["cover.png"]).width, 160)
        for filename, data in outputs.items():
            self.assertEqual(report["outputs"][filename], {"sha256": sha256(data).hexdigest(), "bytes": len(data)})
        archived = decode((fixtures / "closed_studio_evidence" / "report.json").read_bytes())
        self.assertEqual(archived["plan_sha256"], identity(plan))
        for name, proof in archived["outputs"].items():
            raw = (fixtures / "closed_studio_evidence" / name).read_bytes()
            self.assertEqual(proof, {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)})

    def test_bench_refuses_other_case_before_backends(self):
        plan = decode((Path(__file__).parent / "fixtures" / "closed_studio_bench.json").read_bytes())
        plan["case"] = "live_media"
        with self.assertRaisesRegex(ContractError, "fixture tertutup"):
            run_bench(plan, identity(plan))
