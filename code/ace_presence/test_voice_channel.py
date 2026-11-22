from io import BytesIO
from pathlib import Path
from struct import pack, unpack
from tempfile import TemporaryDirectory
import unittest
import wave

from ._contracts import PresenceError, identity
from .test_rolling_summary import sample, save
from .voice_channel import render_voice_exchange


def audio(value):
    with BytesIO() as buffer:
        with wave.open(buffer, "wb") as stream:
            stream.setparams((1, 2, 8000, 0, "NONE", "fixture"))
            stream.writeframes(pack("<h", value) * 400)
        return buffer.getvalue()


class VoiceTests(unittest.TestCase):
    def test_audio_in_both_directions_and_actual_gap_with_evidence(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dialogue, records = sample(root)
            clips = []
            for row in records["events"]:
                name = row["turn"]["id"]
                clips.append({"id": name, "turn_sha256": row["sha256"], **save(root, name + ".wav", audio(1450)),
                              "permission_ref": "fixture:consent"})
            plan = {"schema": "ace.presence.duplex-plan.v1", "dialogue": dialogue, "clips": clips,
                    "pause_ms": 10, "max_duration_ms": 2000}
            output, report = render_voice_exchange(plan, identity(plan), root)
            self.assertEqual(report["frames"], 1840)
            with wave.open(BytesIO(output), "rb") as stream:
                self.assertEqual(unpack("<hh", stream.readframes(1)), (1450, 0))
                stream.setpos(440)
                self.assertEqual(unpack("<hh", stream.readframes(1)), (0, 0))
                stream.setpos(490)
                self.assertEqual(unpack("<hh", stream.readframes(1)), (0, 1450))
            clips[0]["turn_sha256"] = "a" * 64
            with self.assertRaisesRegex(PresenceError, "hash turn"):
                render_voice_exchange(plan, identity(plan), root)
