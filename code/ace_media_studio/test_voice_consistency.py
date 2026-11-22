from hashlib import sha256
from math import sin, tau
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, wav
from ._contracts import ContractError, identity
from .voice_consistency import compare_episodes


class VoiceContinuityTests(unittest.TestCase):
    def test_good_episode_and_pitch_drift_with_prosody_sources(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = []
            for name, freq in (("ref", 125), ("match", 128), ("drift", 180)):
                signal = wav(Audio(8000, 1, tuple(round(8000 * sin(tau * freq * n / 8000)) for n in range(4000))))
                path = f"{name}.wav"
                (root / path).write_bytes(signal)
                clips.append({"id": name, "path": path, "sha256": sha256(signal).hexdigest(),
                              "source_ref": f"fixture:{name}", "permission_ref": "fixture:allowed-tts"})
            plan = {"schema": "ace.media.voice-consistency.v1", "source_ref": "fixture:protocol",
                    "reference_id": "ref", "clips": clips, "limits": {"pitch_delta_hz": 7, "pause_delta_bp": 200,
                                                                    "minimum_windows": 4, "silence_floor": 200}}
            report = compare_episodes(plan, identity(plan), root)
            self.assertEqual(report["matches"], 1)
            self.assertEqual(report["status"], "hold")
            rows = {r["id"]: r for r in report["episodes"]}
            self.assertEqual(rows["drift"]["reasons"], ["pitch_drift"])
            self.assertEqual(rows["match"]["reasons"], [])
            clips[1]["permission_ref"] = ""
            with self.assertRaisesRegex(ContractError, "Izin"):
                compare_episodes(plan, identity(plan), root)
