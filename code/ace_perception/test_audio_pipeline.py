"""Verifier WAV PCM, segmentasi berbatas dan rujukan transkrip."""
from hashlib import sha256
from io import BytesIO
import json
from math import sin, tau
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import wave

from ace_perception import _audio, audio_pipeline as model


RATE = 8000


def wav(values, rate=RATE, channels=1, width=2):
    output = BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        payload = struct.pack(f"<{len(values)}h", *values) if width == 2 else bytes(values)
        stream.writeframes(payload)
    return output.getvalue()


def tone(freq, count=480, amplitude=1600):
    return [round(amplitude*sin(tau*freq*index/RATE)) for index in range(count)]


def fixture():
    return wav([0]*160 + tone(250) + [0]*960 + tone(500) + [0]*120)


def receipt(roster):
    return {"schema": "ace.perception-transcript-receipts.v1", "audio_sha256": roster["audio_sha256"],
            "roster_sha256": roster["roster_sha256"], "source_ref": "fixture/transcript", "segments": [
                {"id": "s0001", "receipt_ref": "fixture/receipt/1", "status": "read",
                 "words": [{"word": "halo", "start_sample": 160, "end_sample": 320},
                           {"word": "dunia", "start_sample": 325, "end_sample": 640}]},
                {"id": "s0002", "receipt_ref": "fixture/receipt/2", "status": "read",
                 "words": [{"word": "uji", "start_sample": 1600, "end_sample": 2080}]},
            ]}


class AudioPipelineTests(unittest.TestCase):
    def test_segment_bounds_and_timestamp_math_are_from_pcm_bytes(self):
        source = fixture()
        roster = model.segment(source)
        self.assertEqual(roster["audio_sha256"], sha256(source).hexdigest())
        self.assertEqual(roster["sample_rate"], RATE)
        self.assertEqual(roster["sample_count"], 2200)
        first, second = roster["segments"]
        self.assertEqual(first, {"id": "s0001", "start_sample": 160, "end_sample": 640, "start_us": 20_000, "end_us": 80_000})
        self.assertEqual(second, {"id": "s0002", "start_sample": 1600, "end_sample": 2080, "start_us": 200_000, "end_us": 260_000})
        self.assertEqual(roster["roster_sha256"], model._sha({key: item for key, item in roster.items() if key != "roster_sha256"}))

    def test_gap_inclusive_and_rms_threshold_inclusive(self):
        source = wav([300]*320 + [0]*160 + [-300]*320)
        merged = model.segment(source, silence_ms=20, rms=300)
        self.assertEqual(len(merged["segments"]), 1)
        self.assertEqual(merged["segments"][0]["end_sample"], 800)
        self.assertEqual(len(model.segment(source, silence_ms=19, rms=300)["segments"]), 2)
        self.assertEqual(model.segment(source, silence_ms=20, rms=301)["segments"], [])

    def test_short_peak_ignored_and_final_partial_frame_retained(self):
        source = wav([1600]*159 + [0]*961 + [1600]*337)
        roster = model.segment(source)
        item, = roster["segments"]
        self.assertEqual(item["start_sample"], 1120)
        self.assertEqual(item["end_sample"], 1457)
        self.assertEqual(item["end_us"], 182125)

    def test_timecode_and_text_in_receipts_are_joined_in_audio_order(self):
        audio = fixture()
        raw = receipt(model.segment(audio))
        raw["segments"].reverse()
        source = model._canonical(raw)
        result = model.align(audio, source)
        self.assertEqual(result["receipt_sha256"], sha256(source).hexdigest())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["open_segments"], [])
        self.assertEqual(result["segments"][0]["text"], "halo dunia")
        self.assertEqual(result["segments"][0]["words"][1]["start_us"], 40625)
        self.assertEqual(result["segments"][1]["receipt_ref"], "fixture/receipt/2")

    def test_unintelligible_and_unrecorded_remain_distinct_without_guessed_words(self):
        audio = fixture()
        raw = receipt(model.segment(audio))
        raw["segments"].pop()
        raw["segments"][0].update(status="unintelligible", words=[])
        result = model.align(audio, model._canonical(raw))
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["open_segments"], ["s0001", "s0002"])
        first, second = result["segments"]
        self.assertEqual((first["status"], first["text"], first["receipt_ref"]), ("unintelligible", None, "fixture/receipt/1"))
        self.assertEqual((second["status"], second["text"], second["receipt_ref"]), ("missing", None, None))

    def test_audio_or_policy_change_invalidates_receipt(self):
        audio = fixture()
        raw = model._canonical(receipt(model.segment(audio)))
        with self.assertRaisesRegex(ValueError, "roster"):
            model.align(audio, raw, rms=301)
        with self.assertRaisesRegex(ValueError, "roster"):
            model.align(wav(tone(125)), raw)

    def test_words_require_bounds_nonthreatening_types_and_separate_timestamps(self):
        audio = fixture()
        for changes in ({"start_sample": 150}, {"start_sample": True}, {"end_sample": 641}, {"word": "dua kata"}, {"word": ""}):
            raw = receipt(model.segment(audio))
            raw["segments"][0]["words"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.align(audio, model._canonical(raw))
        raw = receipt(model.segment(audio))
        raw["segments"][0]["words"][0]["end_sample"] = 326
        with self.assertRaises(ValueError):
            model.align(audio, model._canonical(raw))

    def test_decoder_8_bit_stereo_signed_and_bad_wav(self):
        stereo = _audio.decode(wav([0, 255, 128, 128], channels=2, width=1))
        self.assertEqual(list(stereo.mono), [-128, 0])
        for source in (b"noise", fixture()[:-10], wav([80]*32, rate=2000), wav([1, 2, 3], channels=3)):
            with self.subTest(source_size=len(source)), self.assertRaises(ValueError):
                _audio.decode(source)

    def test_cli_join_status_and_exact_existing_files(self):
        audio = fixture()
        base = Path(self.enterContext(TemporaryDirectory()))
        wav_path, receipts_path = base/"audio.wav", base/"receipts.json"
        wav_path.write_bytes(audio)
        report_cmd = [sys.executable, "-m", "ace_perception.audio_pipeline", str(wav_path)]
        product = subprocess.run(report_cmd, capture_output=True, check=True)
        self.assertEqual(json.loads(product.stdout), model.segment(audio))
        raw = receipt(model.segment(audio))
        raw["segments"].pop()
        receipts_path.write_bytes(model._canonical(raw))
        product = subprocess.run([*report_cmd, "--receipts", str(receipts_path)], capture_output=True)
        self.assertEqual(product.returncode, 1)
        self.assertEqual(json.loads(product.stdout), model.align(audio, receipts_path.read_bytes()))
        self.assertEqual(wav_path.read_bytes(), audio)
