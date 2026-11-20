"""Pengukur kebaruan leksikal & struktural deterministik tanpa embedding eksternal (AG89).

Menghitung jarak kebaruan karya baru terhadap korpus pembanding memakai dua komponen
terbatas ``[0.0, 1.0]`` yang dapat dihitung dengan tangan:
1. Jarak leksikal (Jaccard distance pada himpunan token kata ternormalisasi).
2. Jarak struktural (rata-rata selisih L1 ternormalisasi atas 4 fitur struktur teks:
   ``paragraphs``, ``sentences``, ``dialogue_lines``, dan ``section_markers``).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.corpus-novelty.v1"
DEFAULT_LEXICAL_WEIGHT = 0.6
_TOKEN_RE = re.compile(r"[0-9a-zA-Z]+")
_SPEAKER_LINE_RE = re.compile(r"^[A-Z][A-Za-z0-9_ ]{0,24}:\s+")


@dataclass(frozen=True)
class StructuralProfile:
    paragraphs: int
    sentences: int
    dialogue_lines: int
    section_markers: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (
            self.paragraphs,
            self.sentences,
            self.dialogue_lines,
            self.section_markers,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "paragraphs": self.paragraphs,
            "sentences": self.sentences,
            "dialogue_lines": self.dialogue_lines,
            "section_markers": self.section_markers,
        }


def tokenize_lexical(text: str) -> frozenset[str]:
    """Ekstrak himpunan kata alfanumerik huruf kecil secara deterministik."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def extract_structural_profile(text: str) -> StructuralProfile:
    """Ekstrak 4 metrik struktural deterministik dari teks karya."""
    stripped = text.strip()
    if not stripped:
        return StructuralProfile(paragraphs=0, sentences=0, dialogue_lines=0, section_markers=0)

    blocks = [b.strip() for b in re.split(r"\n\s*\n", stripped) if b.strip()]
    sentences = [s.strip() for s in re.split(r"[.!?]+", stripped) if s.strip()]

    dialogue_lines = 0
    section_markers = 0
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line in {"---", "***", "==="}:
            section_markers += 1
        if '"' in line or "\u201c" in line or line.startswith("- ") or _SPEAKER_LINE_RE.match(line):
            dialogue_lines += 1

    return StructuralProfile(
        paragraphs=len(blocks),
        sentences=len(sentences),
        dialogue_lines=dialogue_lines,
        section_markers=section_markers,
    )


def lexical_jaccard_distance(tokens_a: frozenset[str], tokens_b: frozenset[str]) -> float:
    """1 - |A ∩ B| / |A ∪ B| (0.0 bila keduanya kosong)."""
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return 1.0 - (len(tokens_a & tokens_b) / len(union))


def structural_l1_distance(a: StructuralProfile, b: StructuralProfile) -> float:
    """Rata-rata selisih L1 ternormalisasi atas 4 komponen StructuralProfile."""
    va = a.as_tuple()
    vb = b.as_tuple()
    total = 0.0
    for x, y in zip(va, vb):
        denom = max(x, y, 1)
        total += abs(x - y) / denom
    return total / len(va)


def compute_work_distance(
    work_a_text: str,
    work_b_text: str,
    *,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
) -> dict[str, float]:
    """Hitung jarak leksikal, jarak struktural, dan gabungan tertimbang dua karya."""
    if not (0.0 <= lexical_weight <= 1.0):
        raise ValueError(f"lexical_weight wajib di [0.0, 1.0], didapat {lexical_weight!r}.")
    lex = lexical_jaccard_distance(tokenize_lexical(work_a_text), tokenize_lexical(work_b_text))
    struct = structural_l1_distance(
        extract_structural_profile(work_a_text),
        extract_structural_profile(work_b_text),
    )
    combined = (lexical_weight * lex) + ((1.0 - lexical_weight) * struct)
    return {
        "lexical_distance": round(lex, 6),
        "structural_distance": round(struct, 6),
        "combined_distance": round(combined, 6),
    }


def score_corpus_novelty(
    corpus: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    *,
    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT,
) -> dict[str, Any]:
    """Nilai kebaruan tiap karya kandidat terhadap ``corpus`` serta tetangga terdekatnya."""
    if not (0.0 <= lexical_weight <= 1.0):
        raise ValueError(f"lexical_weight wajib di [0.0, 1.0], didapat {lexical_weight!r}.")

    corpus_items = [
        {
            "work_id": str(item["work_id"]),
            "text": str(item.get("text", "")),
            "tokens": tokenize_lexical(str(item.get("text", ""))),
            "structure": extract_structural_profile(str(item.get("text", ""))),
        }
        for item in corpus
    ]

    results: list[dict[str, Any]] = []
    for cand in candidates:
        cid = str(cand["work_id"])
        ctext = str(cand.get("text", ""))
        ctokens = tokenize_lexical(ctext)
        cstruct = extract_structural_profile(ctext)

        if not corpus_items:
            results.append(
                {
                    "work_id": cid,
                    "novelty_score": 1.0,
                    "lexical_distance": 1.0,
                    "structural_distance": 1.0,
                    "nearest_neighbor": None,
                    "structure": cstruct.to_dict(),
                }
            )
            continue

        best_entry: dict[str, Any] | None = None
        for ref in corpus_items:
            lex = lexical_jaccard_distance(ctokens, ref["tokens"])
            struct = structural_l1_distance(cstruct, ref["structure"])
            combined = (lexical_weight * lex) + ((1.0 - lexical_weight) * struct)
            key = (round(combined, 12), ref["work_id"])
            if best_entry is None or key < best_entry["_sort_key"]:
                best_entry = {
                    "_sort_key": key,
                    "nearest_neighbor": ref["work_id"],
                    "novelty_score": round(combined, 6),
                    "lexical_distance": round(lex, 6),
                    "structural_distance": round(struct, 6),
                }
        assert best_entry is not None
        results.append(
            {
                "work_id": cid,
                "novelty_score": best_entry["novelty_score"],
                "lexical_distance": best_entry["lexical_distance"],
                "structural_distance": best_entry["structural_distance"],
                "nearest_neighbor": best_entry["nearest_neighbor"],
                "structure": cstruct.to_dict(),
            }
        )

    scores = [r["novelty_score"] for r in results]
    summary = {
        "candidate_count": len(results),
        "corpus_count": len(corpus_items),
        "mean_novelty": round(sum(scores) / len(scores), 6) if scores else 0.0,
        "min_novelty": min(scores) if scores else 0.0,
        "max_novelty": max(scores) if scores else 0.0,
    }
    return {
        "schema": SCHEMA,
        "lexical_weight": lexical_weight,
        "structural_weight": round(1.0 - lexical_weight, 6),
        "results": results,
        "summary": summary,
    }


def _load_jsonl_or_json(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    raise ValueError(f"Berkas {path} wajib memuat list JSON atau JSONL.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pengukur kebaruan karya terhadap korpus (AG89)")
    parser.add_argument("--corpus", required=True, help="Path JSON/JSONL korpus acuan")
    parser.add_argument("--candidates", required=True, help="Path JSON/JSONL karya baru")
    parser.add_argument("--lexical-weight", type=float, default=DEFAULT_LEXICAL_WEIGHT)
    args = parser.parse_args(argv)

    corpus = _load_jsonl_or_json(Path(args.corpus))
    candidates = _load_jsonl_or_json(Path(args.candidates))
    report = score_corpus_novelty(corpus, candidates, lexical_weight=args.lexical_weight)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
