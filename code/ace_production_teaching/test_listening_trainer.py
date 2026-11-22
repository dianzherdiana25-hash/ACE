from io import BytesIO
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
import unittest
import wave

from ._contracts import identity
from .listening_trainer import prepare_listening
from .test_tabular_engine import save


class ListeningTests(unittest.TestCase):
    def test_wave_slice_and_separate_key_have_same_card_content_hash(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with BytesIO() as stream:
                with wave.open(stream, "wb") as writer:
                    writer.setparams((1, 2, 8000, 0, "NONE", "fixture"))
                    writer.writeframes(pack("<h", 2500) * 2000)
                proof = save(root, "sample.wav", stream.getvalue())
            plan = {"schema": "ace.teaching.listening-plan.v1", "audio": proof, "permission_ref": "fixture:license",
                    "seed": 7, "clips": [{"id": "take", "from_ms": 50, "through_ms": 110,
                        "question": "Opsi mana?", "options": ["A", "B", "C"], "answer": "B", "transcript_ref": "fixture:utterance"}]}
            files, key, report = prepare_listening(plan, identity(plan), root)
            with wave.open(BytesIO(files["take.wav"]), "rb") as reader:
                self.assertEqual(reader.getnframes(), 480)
            card = report["cards"][0]
            self.assertEqual(card["first_sample"], 400)
            self.assertEqual(card["options"][key[0]["option_index"]], "B")
            self.assertEqual(identity(card), key[0]["card_sha256"])
