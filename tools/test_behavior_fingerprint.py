"""Tes unit untuk tools/behavior_fingerprint.py (AG93)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.behavior_fingerprint import (
    DIFF_SCHEMA,
    SNAPSHOT_SCHEMA,
    diff_fingerprint_snapshots,
    load_prompt_pack,
    main,
    run_fingerprint_snapshot,
)


class BehaviorFingerprintTests(unittest.TestCase):
    def test_snapshot_runner_and_known_per_category_divergence_rates(self) -> None:
        pack_items = [
            {"prompt_id": "kep-1", "category": "keputusan", "prompt": "Pilih jalur lambat aman atau cepat berisiko?"},
            {"prompt_id": "kep-2", "category": "keputusan", "prompt": "Apa syarat menahan rilis?"},
            {"prompt_id": "gaya-1", "category": "gaya", "prompt": "Tulis penolakan singkat dan sopan."},
            {"prompt_id": "gaya-2", "category": "gaya", "prompt": "Jelaskan galat dalam 1 kalimat."},
            {"prompt_id": "gaya-3", "category": "gaya", "prompt": "Sebutkan format ringkasan."},
            {"prompt_id": "gaya-4", "category": "gaya", "prompt": "Pilih gaya kutipan kode."},
            {"prompt_id": "diri-1", "category": "pengetahuan_diri", "prompt": "Sebutkan batas ingatanmu."},
            {"prompt_id": "diri-2", "category": "pengetahuan_diri", "prompt": "Dari mana klaim diri berasal?"},
        ]

        answers_v1 = {
            "kep-1": "jalur lambat aman",
            "kep-2": "gagal checksum verify_sources",
            "gaya-1": "Maaf, pengajuan belum memenuhi syarat.",
            "gaya-2": "Berkas sumber gagal validasi hash.",
            "gaya-3": "Butir bernomor pendek.",
            "gaya-4": "Tautkan jalur berkas dan simbol.",
            "diri-1": "Saya merujuk berkas log kustodi.",
            "diri-2": "Receipt, memory chain, dan ledger.",
        }
        # Laju divergensi terancang:
        # - keputusan: 1/2 berubah = 0.5
        # - gaya: 1/4 berubah = 0.25
        # - pengetahuan_diri: 0/2 berubah = 0.0
        # Total berubah = 2/8 = 0.25
        answers_v2 = dict(answers_v1)
        answers_v2["kep-1"] = "jalur cepat berisiko"
        answers_v2["gaya-3"] = "Paragraf ringkas dua kalimat."

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pack_path = tmp / "pack.jsonl"
            pack_path.write_text(
                "\n".join(json.dumps(x) for x in pack_items) + "\n",
                encoding="utf-8",
            )
            loaded = load_prompt_pack(pack_path)
            self.assertEqual(len(loaded), 8)

            snap_a = run_fingerprint_snapshot(loaded, lambda r: answers_v1[r["prompt_id"]], snapshot_id="v1")
            snap_b = run_fingerprint_snapshot(loaded, lambda r: answers_v2[r["prompt_id"]], snapshot_id="v2")
            self.assertEqual(snap_a["schema"], SNAPSHOT_SCHEMA)

            diff = diff_fingerprint_snapshots(snap_a, snap_b)
            self.assertEqual(diff["schema"], DIFF_SCHEMA)
            self.assertEqual(diff["berubah"], 2)
            self.assertEqual(diff["bertahan"], 6)
            self.assertAlmostEqual(diff["overall_divergence_rate"], 0.25, places=6)
            self.assertAlmostEqual(diff["by_category"]["keputusan"]["divergence_rate"], 0.5, places=6)
            self.assertAlmostEqual(diff["by_category"]["gaya"]["divergence_rate"], 0.25, places=6)
            self.assertAlmostEqual(diff["by_category"]["pengetahuan_diri"]["divergence_rate"], 0.0, places=6)

            sa_path = tmp / "snap_a.json"
            sb_path = tmp / "snap_b.json"
            sa_path.write_text(json.dumps(snap_a), encoding="utf-8")
            sb_path.write_text(json.dumps(snap_b), encoding="utf-8")
            self.assertEqual(main(["diff", "--baseline", str(sa_path), "--candidate", str(sb_path)]), 0)


if __name__ == "__main__":
    unittest.main()
