"""Tes unit kalibrasi untuk tools/arc_rubric.py (AG90)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.arc_rubric import DIMENSIONS, SCHEMA, main, score_chapter_pack


class ArcRubricTests(unittest.TestCase):
    def test_strong_pack_strictly_outscores_weak_pack_on_every_dimension(self) -> None:
        strong_pack = {
            "pack_id": "kuat-01",
            "chapters": [
                {
                    "chapter_id": "bab-1",
                    "characters": ["Arya", "Bima"],
                    "beats": ["setup", "reversal"],
                    "open_hooks": ["Siapa pengirim pesan tersegel di mercusuar?"],
                    "text": (
                        "\"Mengapa pelita mercusuar menyala sendiri di tengah kabut?\" bisik Arya.\n"
                        "Bayangan langkah mendekat, namun dermaga sepi tanpa perahu bersandar.\n\n"
                        "Bima menemukan kunci berkarat di bawah papan basah. "
                        "Ternyata segel peti sudah pecah sebelum mereka tiba—ada jejak orang lain!"
                    ),
                },
                {
                    "chapter_id": "bab-2",
                    "characters": ["Arya", "Ranti"],
                    "beats": ["escalation", "cliffhanger"],
                    "open_hooks": ["Menara timur terkunci sebelum jam berdentang."],
                    "text": (
                        "Ancaman badai membuat Ranti berpacu menaiki tangga batu yang licin.\n"
                        "\"Jangan sentuh tuas utara!\" seru Bima dari lantai bawah.\n\n"
                        "Tetapi jarum kompas berputar liar dan pintu menara terkunci rapat dari luar. "
                        "Siapa yang menunggu di puncak menara sekarang?"
                    ),
                },
            ],
        }

        weak_pack = {
            "pack_id": "lemah-01",
            "chapters": [
                {
                    "chapter_id": "bab-1",
                    "text": (
                        "Orang berjalan pelan ke rumah. Orang berjalan pelan ke rumah. "
                        "Cuaca biasa dan hari selesai."
                    ),
                },
                {
                    "chapter_id": "bab-2",
                    "text": (
                        "Orang berjalan pelan ke pasar. Orang berjalan pelan ke pasar. "
                        "Hari berjalan biasa."
                    ),
                },
            ],
        }

        strong_report = score_chapter_pack(strong_pack)
        weak_report = score_chapter_pack(weak_pack)

        self.assertEqual(strong_report["schema"], SCHEMA)
        self.assertEqual(set(strong_report["dimensions"].keys()), set(DIMENSIONS))
        for dim in DIMENSIONS:
            self.assertGreater(
                strong_report["dimensions"][dim],
                weak_report["dimensions"][dim],
                f"Dimensi {dim} pada paket kuat wajib lebih tinggi dari paket lemah",
            )
        self.assertGreater(strong_report["overall"], weak_report["overall"])

        with tempfile.TemporaryDirectory() as tmpdir:
            p_path = Path(tmpdir) / "strong.json"
            p_path.write_text(json.dumps(strong_pack), encoding="utf-8")
            self.assertEqual(main(["--pack", str(p_path)]), 0)


if __name__ == "__main__":
    unittest.main()
