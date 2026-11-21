"""Verifier clustering spektral dan abstain dari audio sintetis."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import audio_pipeline, speaker_diarization as model
from ace_perception.test_audio_pipeline import tone, wav


def fixture():
    silence = [0]*1120
    return wav(tone(125) + silence + tone(500) + silence + tone(125, amplitude=3100))


class SpeakerTests(unittest.TestCase):
    def test_identifiable_synthetic_segments_join_without_identity_claim(self):
        recording = fixture()
        report = model.diarize(recording)
        self.assertEqual(report["audio_sha256"], sha256(recording).hexdigest())
        self.assertEqual(report["config_sha256"], audio_pipeline._sha(report["config"]))
        self.assertEqual(report["unattributed"], [])
        self.assertEqual(report["config"]["frequencies_hz"], [125, 250, 500, 1000])
        self.assertEqual([row["speaker_id"] for row in report["segments"]], ["speaker-1", "speaker-2", "speaker-1"])
        self.assertEqual([row["status"] for row in report["segments"]], ["new_cluster", "new_cluster", "assigned"])
        self.assertEqual(report["speakers"][0]["segments"], ["s0001", "s0003"])
        self.assertEqual(report["speakers"][1]["segments"], ["s0002"])
        self.assertGreater(report["segments"][0]["signal_bp"], 4000)
        self.assertGreater(report["segments"][1]["signature_bp"][2], 9000)
        tail = report["segments"][-1]
        self.assertEqual(tail["nearest"][0]["speaker_id"], "speaker-1")
        self.assertLess(tail["nearest"][0]["distance_bp"], 50)

    def test_shared_audio_segmentation_matches_pipeline_sample_boundaries(self):
        recording = fixture()
        samples = audio_pipeline.segment(recording)["segments"]
        report = model.diarize(recording)["segments"]
        self.assertEqual([{key: row[key] for key in sample} for row, sample in zip(report, samples, strict=True)], samples)
        self.assertEqual(report[-1]["start_us"], 400_000)
        self.assertEqual(report[-1]["end_us"], 460_000)

    def test_constant_loud_segment_not_attributed_without_spectral_signal(self):
        source = wav([1700]*640)
        report = model.diarize(source)
        row, = report["segments"]
        self.assertEqual(report["speakers"], [])
        self.assertEqual(report["unattributed"], ["s0001"])
        self.assertEqual(row["status"], "insufficient_signal")
        self.assertIsNone(row["speaker_id"])
        self.assertEqual(row["nearest"], [])

    def test_cluster_limit_preserves_unknown_selection_and_existing_cluster(self):
        rows = model.diarize(fixture(), maximum_speakers=1)
        self.assertEqual(rows["unattributed"], ["s0002"])
        self.assertEqual(rows["segments"][1]["status"], "cluster_limit")
        self.assertEqual(rows["speakers"][0]["segments"], ["s0001", "s0003"])

    def test_close_centroids_abstain_and_record_distances_without_updating(self):
        clusters = [model.Cluster("speaker-1", [5000, 5000], ["a"]),
                    model.Cluster("speaker-2", [5100, 4900], ["b"])]
        answer, code, evidence = model._assign(clusters, "c", [5040, 4960], 3000, 40, 4)
        self.assertEqual((answer, code), (None, "ambiguous"))
        self.assertEqual(evidence, [{"speaker_id": "speaker-1", "distance_bp": 40},
                                    {"speaker_id": "speaker-2", "distance_bp": 60}])
        self.assertEqual([item.members for item in clusters], [["a"], ["b"]])

    def test_sorted_bands_same_extraction_for_non_sorted_policy(self):
        one = model.diarize(fixture(), frequencies=(125, 500, 250))
        two = model.diarize(fixture(), frequencies=(250, 125, 500))
        self.assertEqual(one, two)
        self.assertEqual(one["config"]["frequencies_hz"], [125, 250, 500])
        self.assertEqual(one["speakers"][0]["segments"], ["s0001", "s0003"])

    def test_silent_audio_and_invalid_frequency_settings(self):
        quiet = wav([0]*1600)
        product = model.diarize(quiet)
        self.assertEqual(product["segments"], [])
        self.assertEqual(product["speakers"], [])
        for changes in ({"frequencies": (125, 125)}, {"frequencies": (125,)},
                        {"frequencies": (125, 4000)}, {"frequencies": (True, 125)},
                        {"maximum_speakers": 0}, {"distance_bp": -1}, {"spectral_window_ms": 5},
                        {"separation_bp": 0}, {"silence_ms": 400_000}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.diarize(quiet, **changes)

    def test_overlaid_frequencies_near_both_clusters_are_unattributed(self):
        stream = fixture()
        single = model.diarize(stream)
        first, second = (row["centroid_bp"] for row in single["speakers"])
        clusters = [model.Cluster("speaker-1", first, ["a"]), model.Cluster("speaker-2", second, ["b"])]
        midpoint = [(a+b)//2 for a, b in zip(first, second, strict=True)]
        answer, code, evidence = model._assign(clusters, "c", midpoint, 6000, 2, 3)
        self.assertIsNone(answer)
        self.assertEqual(code, "ambiguous")
        self.assertEqual(evidence[0]["distance_bp"], evidence[1]["distance_bp"])
        self.assertEqual(len(clusters), 2)

    def test_cli_nonzero_for_unattributed_and_same_candidate_table(self):
        wav_path = Path(self.enterContext(TemporaryDirectory())) / "audio.wav"
        payload = fixture()
        wav_path.write_bytes(payload)
        command = [sys.executable, "-m", "ace_perception.speaker_diarization", str(wav_path)]
        product = subprocess.run(command, capture_output=True, check=True)
        self.assertEqual(json.loads(product.stdout), model.diarize(payload))
        second = subprocess.run([*command, "--maximum-speakers", "1"], capture_output=True)
        self.assertEqual(second.returncode, 1)
        self.assertEqual(json.loads(second.stdout)["unattributed"], ["s0002"])
        self.assertEqual(wav_path.read_bytes(), payload)

    def test_distance_and_separation_include_exact_boundaries(self):
        cluster = model.Cluster("speaker-1", [6000, 4000], ["a"])
        selected, status, evidence = model._assign([cluster], "b", [5000, 5000], 1000, 350, 2)
        self.assertEqual((selected, status), ("speaker-1", "assigned"))
        self.assertEqual(evidence[0]["distance_bp"], 1000)
        self.assertEqual(cluster.export()["centroid_bp"], [5500, 4500])
        cluster = model.Cluster("speaker-1", [6000, 4000], ["a"])
        other = model.Cluster("speaker-2", [6350, 3650], ["other"])
        selected, status, evidence = model._assign([cluster, other], "b", [5000, 5000], 1000, 350, 2)
        self.assertEqual((selected, status), ("speaker-1", "assigned"))
        self.assertEqual([item["distance_bp"] for item in evidence], [1000, 1350])

    def test_same_cluster_identifiers_with_equivalent_8_bit_waveform(self):
        source = wav(tone(125, amplitude=8192) + [0]*1120 + tone(500, amplitude=8192))
        signal = tone(125, amplitude=8192) + [0]*1120 + tone(500, amplitude=8192)
        coarse = wav([value//256+128 for value in signal], width=1)
        dense_rows = model.diarize(source)["segments"]
        coarse_rows = model.diarize(coarse)["segments"]
        self.assertEqual([row["speaker_id"] for row in dense_rows], [row["speaker_id"] for row in coarse_rows])
        self.assertEqual([row["start_sample"] for row in dense_rows], [row["start_sample"] for row in coarse_rows])

    def test_window_extraction_for_short_segments_keeps_one_unique_interval(self):
        from ace_perception import _audio

        audio = _audio.decode(wav(tone(125, count=160)))
        value = model._windows(audio, {"start_sample": 0, "end_sample": 160}, audio.sample_rate, 40)
        self.assertEqual(len(value), 1)
        self.assertEqual(len(value[0]), 160)
        self.assertEqual(list(value[0]), tone(125, count=160))
        self.assertEqual(_audio.MIN_RATE, audio.sample_rate)
