"""Tes lint paket konten kurikulum Bahasa Indonesia jenjang lanjut (AG66).

Memvalidasi ``tools/fixtures/language_advanced_curriculum_v1.jsonl`` atas empat
sub-jenjang (``esai_argumentatif``, ``dialog_negosiasi``,
``ringkasan_dokumen_panjang``, ``debat_tertulis``): struktur tugas bertingkat
lengkap, bobot rubrik berjumlah 1.0, serta konsistensi skor & teks contoh
terkalibrasi ``baik > sedang > buruk``.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "language_advanced_curriculum_v1.jsonl"
)
EXPECTED_SUB_TIERS = (
    "esai_argumentatif",
    "dialog_negosiasi",
    "ringkasan_dokumen_panjang",
    "debat_tertulis",
)
EXPECTED_LEVELS = ("dasar", "menengah", "lanjut")


def lint_curriculum_entry(entry: dict) -> list[str]:
    """Audit satu entri sub-jenjang kurikulum bahasa; kembalikan daftar temuan cacat."""
    errors: list[str] = []
    sub = entry.get("sub_tier")
    if not isinstance(sub, str) or not sub:
        return ["missing sub_tier"]

    tasks = entry.get("tiered_tasks")
    if not isinstance(tasks, list) or len(tasks) != 3:
        errors.append(f"{sub}: tiered_tasks wajib memuat tepat 3 jenjang")
    else:
        levels = [t.get("level") for t in tasks]
        if tuple(levels) != EXPECTED_LEVELS:
            errors.append(f"{sub}: urutan level harus {EXPECTED_LEVELS}, dapat {levels}")
        prev_words = 0
        for t in tasks:
            if not t.get("prompt") or not t.get("required_elements"):
                errors.append(f"{sub}/{t.get('task_id')}: prompt atau required_elements kosong")
            mw = t.get("min_words", 0)
            if not isinstance(mw, int) or mw <= prev_words:
                errors.append(f"{sub}/{t.get('task_id')}: min_words tidak menaik bertingkat")
            prev_words = mw

    rubric = entry.get("rubric")
    if not isinstance(rubric, dict):
        errors.append(f"{sub}: rubric hilang")
        return errors

    criteria = rubric.get("criteria") or []
    bands = rubric.get("bands") or {}
    if not criteria:
        errors.append(f"{sub}: criteria kosong")
        return errors

    weight_sum = sum(float(c["weight"]) for c in criteria)
    if abs(weight_sum - 1.0) > 1e-6:
        errors.append(f"{sub}: jumlah bobot rubrik {weight_sum} != 1.0")

    criteria_map = {c["criterion"]: c for c in criteria}
    examples = entry.get("calibrated_examples") or {}
    computed_scores: dict[str, float] = {}
    word_counts: dict[str, int] = {}

    for band in ("baik", "sedang", "buruk"):
        ex = examples.get(band)
        if not isinstance(ex, dict):
            errors.append(f"{sub}: contoh terkalibrasi '{band}' hilang")
            continue
        text = str(ex.get("text") or "").strip()
        if not text:
            errors.append(f"{sub}/{band}: teks contoh kosong")
        word_counts[band] = len(text.split())
        if ex.get("expected_band") != band:
            errors.append(f"{sub}/{band}: expected_band tidak cocok")
        c_scores = ex.get("criteria_scores") or {}
        if set(c_scores.keys()) != set(criteria_map.keys()):
            errors.append(f"{sub}/{band}: criteria_scores tidak sama persis dengan kriteria rubrik")
            continue

        weighted = 0.0
        for cname, cspec in criteria_map.items():
            raw_val = float(c_scores[cname])
            max_s = float(cspec["max_score"])
            if not 0.0 <= raw_val <= max_s:
                errors.append(f"{sub}/{band}: skor {cname}={raw_val} di luar [0, {max_s}]")
            weighted += float(cspec["weight"]) * (raw_val / max_s)
        weighted = round(weighted, 6)
        computed_scores[band] = weighted

        if abs(weighted - float(ex.get("expected_score", -1.0))) > 1e-4:
            errors.append(
                f"{sub}/{band}: expected_score {ex.get('expected_score')} != hasil bobot rubrik {weighted}"
            )
        lo, hi = bands.get(band, [999, -999])
        if not lo <= weighted <= hi:
            errors.append(f"{sub}/{band}: skor rubrik {weighted} di luar rentang band [{lo}, {hi}]")

    if len(computed_scores) == 3:
        if not (computed_scores["baik"] > computed_scores["sedang"] > computed_scores["buruk"]):
            errors.append(f"{sub}: urutan skor kalibrasi rusak: {computed_scores}")
        if not (word_counts["baik"] > word_counts["buruk"]):
            errors.append(f"{sub}: contoh baik lebih pendek daripada buruk")

    return errors


class LanguageAdvancedCurriculumLintTest(unittest.TestCase):
    def test_curriculum_jsonl_complete_and_consistent_across_four_subtiers(self) -> None:
        raw_lines = [
            ln.strip() for ln in FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        entries = [json.loads(ln) for ln in raw_lines]
        self.assertEqual(
            tuple(e["sub_tier"] for e in entries),
            EXPECTED_SUB_TIERS,
        )
        for entry in entries:
            issues = lint_curriculum_entry(entry)
            self.assertEqual(issues, [], msg=f"Lint gagal pada {entry.get('sub_tier')}: {issues}")

    def test_lint_catches_inconsistent_rubric_or_calibration(self) -> None:
        entries = [
            json.loads(ln)
            for ln in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        broken = json.loads(json.dumps(entries[0]))
        # Tukar skor 'baik' dan 'buruk' sehingga kalibrasi bertentangan dengan rubrik.
        broken["calibrated_examples"]["baik"]["criteria_scores"] = broken["calibrated_examples"]["buruk"]["criteria_scores"]
        issues = lint_curriculum_entry(broken)
        self.assertTrue(issues)


if __name__ == "__main__":
    unittest.main()
