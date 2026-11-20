"""Rubrik penilai proksi pembaca deterministik untuk paket bab cerita (AG90).

Menilai paket bab berdasarkan fitur teks dan struktur deterministik pada empat
dimensi:
1. ``alur`` — progresi peristiwa, variasi giliran konflik/resolusi, dan ketuntasan bab.
2. ``tokoh`` — keterlibatan tokoh, kepadatan suara/dialog, dan keaktifan pelaku.
3. ``bahasa`` — keragaman kosakata/bigram, variasi ritme kalimat, dan minim pengulangan.
4. ``daya_tarik`` — kekuatan kait pembuka/penutup bab dan tarikan ketegangan/rasa ingin tahu.

Setiap dimensi berada pada rentang ``[0.0, 1.0]`` dan digabung ke ``overall`` tertimbang.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.arc-rubric.v1"
DIMENSIONS: tuple[str, ...] = ("alur", "tokoh", "bahasa", "daya_tarik")
DEFAULT_WEIGHTS: dict[str, float] = {
    "alur": 0.30,
    "tokoh": 0.25,
    "bahasa": 0.20,
    "daya_tarik": 0.25,
}

_WORD_RE = re.compile(r"[0-9a-zA-Z]+")
_SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z0-9_]{1,20}):\s+")
_PROPER_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,20})\b")
_TURNING_MARKERS = frozenset(
    {
        "namun",
        "tetapi",
        "ternyata",
        "tiba",
        "mendadak",
        "walau",
        "meski",
        "sebab",
        "karena",
        "akibatnya",
        "akhirnya",
        "rupanya",
        "seketika",
        "sayangnya",
        "but",
        "however",
        "suddenly",
        "meanwhile",
        "therefore",
        "finally",
    }
)
_HOOK_MARKERS = frozenset(
    {
        "rahasia",
        "ancaman",
        "bayangan",
        "jejak",
        "janji",
        "berpacu",
        "hampir",
        "hilang",
        "terkunci",
        "berisiko",
        "misteri",
        "darurat",
        "peringatan",
        "petunjuk",
        "gemetar",
        "secret",
        "danger",
        "clue",
        "locked",
        "missing",
    }
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _extract_chapter_features(chapter: Mapping[str, Any]) -> dict[str, Any]:
    text = str(chapter.get("text", "")).strip()
    words = _WORD_RE.findall(text.lower())
    sentences = _split_sentences(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    dialogue_lines = sum(
        1
        for ln in lines
        if '"' in ln or "\u201c" in ln or ln.startswith("- ") or _SPEAKER_RE.match(ln)
    )
    turning_hits = sum(1 for w in words if w in _TURNING_MARKERS)
    hook_hits = sum(1 for w in words if w in _HOOK_MARKERS)

    raw_chars = chapter.get("characters")
    if isinstance(raw_chars, Sequence) and not isinstance(raw_chars, (str, bytes)):
        characters = {str(c).strip() for c in raw_chars if str(c).strip()}
    else:
        characters = set()
    for ln in lines:
        m = _SPEAKER_RE.match(ln)
        if m:
            characters.add(m.group(1))
    # Tambahkan nama diri tengah kalimat sebagai indikasi tokoh tambahan.
    for sent in sentences:
        sent_words = sent.split()
        for tok in sent_words[1:]:
            cleaned = tok.strip(",.;:!?\"'()-")
            if _PROPER_NAME_RE.fullmatch(cleaned):
                characters.add(cleaned)

    raw_beats = chapter.get("beats")
    beats = (
        [str(b).strip().lower() for b in raw_beats if str(b).strip()]
        if isinstance(raw_beats, Sequence) and not isinstance(raw_beats, (str, bytes))
        else []
    )

    first_para = paragraphs[0] if paragraphs else ""
    last_para = paragraphs[-1] if paragraphs else ""
    opening_hook = bool(
        "?" in first_para
        or "!" in first_para
        or '"' in first_para
        or "\u201c" in first_para
        or any(w in _HOOK_MARKERS for w in _WORD_RE.findall(first_para.lower()))
    )
    closing_pull = bool(
        last_para.endswith("?")
        or last_para.endswith("!")
        or last_para.endswith("...")
        or any(w in _HOOK_MARKERS for w in _WORD_RE.findall(last_para.lower()))
        or bool(chapter.get("open_hooks"))
    )

    return {
        "chapter_id": str(chapter.get("chapter_id") or "<tanpa-id>"),
        "words": words,
        "sentences": sentences,
        "paragraph_count": len(paragraphs),
        "line_count": len(lines),
        "dialogue_lines": dialogue_lines,
        "turning_hits": turning_hits,
        "hook_hits": hook_hits,
        "characters": sorted(characters),
        "beats": beats,
        "opening_hook": opening_hook,
        "closing_pull": closing_pull,
    }


def score_chapter_pack(
    pack: Mapping[str, Any],
    *,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Nilai paket bab cerita pada keempat dimensi rubrik pembaca deterministik."""
    effective_weights = dict(DEFAULT_WEIGHTS)
    if weights is not None:
        for dim in DIMENSIONS:
            if dim in weights:
                effective_weights[dim] = float(weights[dim])
    weight_sum = sum(effective_weights.values())
    if weight_sum <= 0:
        raise ValueError("Jumlah bobot rubrik wajib lebih dari 0.")
    norm_weights = {dim: effective_weights[dim] / weight_sum for dim in DIMENSIONS}

    raw_chapters = pack.get("chapters", [])
    if not isinstance(raw_chapters, Sequence) or isinstance(raw_chapters, (str, bytes)):
        raise ValueError("pack['chapters'] wajib berupa list bab.")

    chapters = [_extract_chapter_features(ch) for ch in raw_chapters if isinstance(ch, Mapping)]
    if not chapters:
        zero_scores = {d: 0.0 for d in DIMENSIONS}
        return {
            "schema": SCHEMA,
            "pack_id": str(pack.get("pack_id") or "<tanpa-id>"),
            "chapter_count": 0,
            "dimensions": zero_scores,
            "overall": 0.0,
            "weights": {d: round(norm_weights[d], 6) for d in DIMENSIONS},
            "features": {},
        }

    n_ch = len(chapters)
    all_words = [w for ch in chapters for w in ch["words"]]
    all_sentences = [s for ch in chapters for s in ch["sentences"]]
    unique_characters = sorted({c for ch in chapters for c in ch["characters"]})
    all_beats = [b for ch in chapters for b in ch["beats"]]

    # 1. ALUR: progresi antar-bab, kepadatan paragraf, dan penanda balik/kausalitas.
    multi_para_ratio = sum(1 for ch in chapters if ch["paragraph_count"] >= 2) / n_ch
    turn_per_chapter = sum(min(2, ch["turning_hits"]) / 2.0 for ch in chapters) / n_ch
    if all_beats:
        beat_diversity = min(1.0, len(set(all_beats)) / max(3, n_ch))
    else:
        sent_counts = [len(ch["sentences"]) for ch in chapters]
        avg_sc = sum(sent_counts) / n_ch
        beat_diversity = min(1.0, avg_sc / 4.0)
    alur_score = _clamp01(0.35 * multi_para_ratio + 0.35 * turn_per_chapter + 0.30 * beat_diversity)

    # 2. TOKOH: keragaman pelaku + kehadiran dialog hidup lintas bab.
    char_presence = min(1.0, len(unique_characters) / 3.0)
    dialogue_chapters = sum(1 for ch in chapters if ch["dialogue_lines"] >= 1) / n_ch
    total_lines = max(1, sum(ch["line_count"] for ch in chapters))
    total_dialogue = sum(ch["dialogue_lines"] for ch in chapters)
    # Rasio dialog ideal ~0.25-0.65 mendapat penuh; nol atau 100% monoton berkurang.
    diag_ratio = total_dialogue / total_lines
    dialogue_balance = _clamp01(1.0 - abs(diag_ratio - 0.45) / 0.45) if total_dialogue > 0 else 0.0
    tokoh_score = _clamp01(0.40 * char_presence + 0.35 * dialogue_chapters + 0.25 * dialogue_balance)

    # 3. BAHASA: keunikan bigram kata, variasi panjang kalimat, minim duplikasi kalimat.
    if len(all_words) >= 2:
        bigrams = list(zip(all_words[:-1], all_words[1:]))
        unique_bigram_ratio = len(set(bigrams)) / len(bigrams)
    else:
        unique_bigram_ratio = 0.0
    sent_word_lens = [len(_WORD_RE.findall(s.lower())) for s in all_sentences]
    if len(sent_word_lens) >= 2:
        mean_len = sum(sent_word_lens) / len(sent_word_lens)
        std_len = math.sqrt(sum((x - mean_len) ** 2 for x in sent_word_lens) / len(sent_word_lens))
        rhythm_variety = min(1.0, std_len / 4.0)
    else:
        rhythm_variety = 0.0
    norm_sentences = [" ".join(_WORD_RE.findall(s.lower())) for s in all_sentences]
    sentence_uniqueness = (
        len(set(norm_sentences)) / len(norm_sentences) if norm_sentences else 0.0
    )
    bahasa_score = _clamp01(
        0.45 * unique_bigram_ratio + 0.25 * rhythm_variety + 0.30 * sentence_uniqueness
    )

    # 4. DAYA TARIK: kait pembuka, tarikan penutup, dan kerapatan penanda ketegangan.
    open_ratio = sum(1 for ch in chapters if ch["opening_hook"]) / n_ch
    close_ratio = sum(1 for ch in chapters if ch["closing_pull"]) / n_ch
    hook_density = min(1.0, sum(ch["hook_hits"] for ch in chapters) / max(2.0, n_ch * 2.0))
    daya_tarik_score = _clamp01(0.35 * open_ratio + 0.40 * close_ratio + 0.25 * hook_density)

    dimensions = {
        "alur": round(alur_score, 6),
        "tokoh": round(tokoh_score, 6),
        "bahasa": round(bahasa_score, 6),
        "daya_tarik": round(daya_tarik_score, 6),
    }
    overall = round(
        sum(dimensions[d] * norm_weights[d] for d in DIMENSIONS),
        6,
    )
    return {
        "schema": SCHEMA,
        "pack_id": str(pack.get("pack_id") or "<tanpa-id>"),
        "chapter_count": n_ch,
        "dimensions": dimensions,
        "overall": overall,
        "weights": {d: round(norm_weights[d], 6) for d in DIMENSIONS},
        "features": {
            "total_words": len(all_words),
            "total_sentences": len(all_sentences),
            "unique_characters": unique_characters,
            "unique_beats": sorted(set(all_beats)),
            "unique_bigram_ratio": round(unique_bigram_ratio, 6),
            "sentence_uniqueness": round(sentence_uniqueness, 6),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rubrik penilaian paket bab pembaca-proksi (AG90)")
    parser.add_argument("--pack", required=True, help="Path JSON paket bab cerita")
    args = parser.parse_args(argv)
    pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    report = score_chapter_pack(pack)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
