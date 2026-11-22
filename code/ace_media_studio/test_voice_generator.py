"""Verifier PCM deterministik, fonem digraph, angka dan jeda."""
from hashlib import sha256
import unittest

from ace_media_studio import voice_generator
from ace_media_studio._audio import parse_wav
from ace_media_studio._contracts import ContractError,identity


def plan(words="Nyanyi, 12."):
    return {"schema":"ace.media.voice-plan.v1","source_ref":"fixture/line","text":words,"language":"id",
            "rate":8000,"pitch_hz":150,"speed_milli":1000,"peak":12000,"seed":12}


class VoiceTests(unittest.TestCase):
    def test_real_pcm_hashes_and_phoneme_span_including_number(self):
        raw=plan()
        data,receipt=voice_generator.synthesize(raw,identity(raw))
        audio=parse_wav(data)
        self.assertEqual(receipt["wav_sha256"],sha256(data).hexdigest())
        self.assertEqual(audio.frames,receipt["phonemes"][-1]["last_frame_exclusive"])
        self.assertEqual([row["phoneme"] for row in receipt["phonemes"][:4]],["ny","a","ny","i"])
        self.assertGreater(receipt["peak"],1000)
        self.assertLess(receipt["peak"],32768)
        self.assertEqual(voice_generator.synthesize(raw,identity(raw)),(data,receipt))

    def test_pitch_speed_and_language_bounds(self):
        raw=plan("Satu")
        _,one=voice_generator.synthesize(raw,identity(raw))
        raw["speed_milli"]=1500
        _,two=voice_generator.synthesize(raw,identity(raw))
        self.assertLess(two["frames"],one["frames"])
        raw["text"]="Halo 💡"
        with self.assertRaisesRegex(ContractError,"Grafem"):
            voice_generator.synthesize(raw,identity(raw))
