"""Verifier pitch fixture 125 Hz, penolakan izin dan keluaran berprosodi."""
from hashlib import sha256
from math import pi,sin
import unittest

from ace_media_studio import voice_style
from ace_media_studio._audio import Audio,wav
from ace_media_studio._contracts import ContractError,identity


class ProsodyTests(unittest.TestCase):
    def setUp(self):
        frame=tuple(round(9000*sin(2*pi*125*index/8000)) for index in range(4000))
        self.sample=wav(Audio(8000,1,frame+(0,)*1200))
        self.policy={"schema":"ace.media.voice-style-policy.v1","source_ref":"fixture/analysis",
                     "sample_sha256":sha256(self.sample).hexdigest(),"sample_ref":"fixture/oscillator",
                     "permission":{"purpose":"prosody_reuse","reference":"fixture/authorization"},
                     "minimum_windows":4,"silence_floor":140}

    def test_pitch_and_pauses_measured_from_wave_samples(self):
        output=voice_style.analyze(self.sample,self.policy,identity(self.policy))
        self.assertEqual(output["status"],"prosody_measured")
        self.assertAlmostEqual(output["median_pitch_hz"],125,delta=2)
        self.assertGreater(output["pause_bp"],0)
        render={"schema":"ace.media.prosody-render-plan.v1","source_ref":"fixture/script","text":"Satu dua.",
                "rate":8000,"seed":8}
        bytes_,receipt=voice_style.render(self.sample,self.policy,identity(self.policy),render,identity(render))
        self.assertEqual(receipt["status"],"rendered_generic_prosody")
        self.assertNotEqual(bytes_,self.sample)

    def test_missing_permission_does_not_measure_sample(self):
        self.policy["permission"]["purpose"]="other"
        with self.assertRaisesRegex(ContractError,"Izin"):
            voice_style.analyze(self.sample,self.policy,identity(self.policy))
