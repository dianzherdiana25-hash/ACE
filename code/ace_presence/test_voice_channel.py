from io import BytesIO
from pathlib import Path
import secrets
from struct import pack, unpack
from tempfile import TemporaryDirectory
import unittest
import wave

from ._contracts import PresenceError, identity
from .test_rolling_summary import sample, save
from .voice_channel import open_duplex, render_voice_exchange


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

    @staticmethod
    def live_config():
        return {"schema": "ace.presence.live-voice.v1", "session": "fixture", "rate": 8000,
                "max_block_ms": 20, "max_stream_ms": 40,
                "roles": {"user": "fixture:user", "assistant": "fixture:assistant"}}

    def test_live_audio_passes_in_both_directions_on_actual_local_stream(self):
        plan = self.live_config()
        user, assistant = open_duplex(plan, identity(plan), secrets.token_bytes(32))
        with user, assistant:
            inbound = pack("<h", 100) * 80
            outbound = pack("<h", -50) * 160
            first = user.send_audio(inbound)
            second = assistant.send_audio(outbound)
            self.assertEqual(assistant.receive(), (inbound, first))
            self.assertEqual(user.receive(), (outbound, second))
            self.assertEqual(first["samples"], [0, 80])
            self.assertEqual(second["permission_ref"], "fixture:assistant")
            end_user = user.finish()
            self.assertEqual(assistant.receive(), (b"", end_user))
            new = assistant.send_audio(outbound)
            self.assertEqual(user.receive(), (outbound, new))
            self.assertEqual(new["samples"], [160, 320])
            with self.assertRaisesRegex(PresenceError, "batas"):
                assistant.send_audio(outbound)
            end_assistant = assistant.finish()
            self.assertEqual(user.receive(), (b"", end_assistant))
            with self.assertRaisesRegex(PresenceError, "disegel"):
                user.receive()

    def test_bad_length_rejected_before_stream_write_and_pinned_consent_required(self):
        plan = self.live_config()
        anchor = identity(plan)
        plan["roles"]["assistant"] = ""
        with self.assertRaises(PresenceError):
            open_duplex(plan, anchor, secrets.token_bytes(32))
        plan = self.live_config()
        user, assistant = open_duplex(plan, identity(plan), secrets.token_bytes(32))
        with user, assistant:
            with self.assertRaisesRegex(PresenceError, "genap"):
                user.send_audio(b"x")
            receipt = user.send_audio(b"\x00\x00")
            self.assertEqual(receipt["seq"], 1)
            self.assertEqual(assistant.receive(), (b"\x00\x00", receipt))

    def test_transport_without_final_receipt_remains_unfinished(self):
        plan = self.live_config()
        user, assistant = open_duplex(plan, identity(plan), secrets.token_bytes(32))
        with assistant:
            user.close()
            with self.assertRaisesRegex(PresenceError, "terminator"):
                assistant.receive()
            with self.assertRaisesRegex(PresenceError, "ditutup"):
                assistant.send_audio(b"\x01\x00")

    def test_capture_decodes_actual_mono_wav_and_sealed_sample_provenance(self):
        plan = self.live_config()
        user, assistant = open_duplex(plan, identity(plan), secrets.token_bytes(32))
        with user, assistant:
            audio = pack("<hh", 120, -120)
            receipt = user.send_audio(audio)
            complete = user.finish()
            data, summary = assistant.capture_wave()
            with wave.open(BytesIO(data), "rb") as reading:
                self.assertEqual(reading.getnchannels(), 1)
                self.assertEqual(reading.getframerate(), 8000)
                self.assertEqual(reading.readframes(2), audio)
            self.assertEqual(summary["frames"], 2)
            self.assertEqual(summary["packet_receipts"], [receipt, complete])
