"""Indonesian Phonotactics, Syllabification, Prosody, and Constrained Babbling (`ace_indo_nlp.phonotactics`).

Implements Stage-1 infant/foundational phonological primitives purely offline:
  - Grapheme-to-phoneme tokenization recognizing digraphs (`ng`, `ny`, `kh`, `sy`)
  - Maximal-onset / valid-coda syllabification and CV pattern labeling
  - Penultimate prosodic stress cueing (`me·nya·YA·ngi`)
  - Phonotactically valid CV/CVC babbling synthesis from phoneme inventories
"""
from __future__ import annotations

import re
from typing import Any

VOWELS = frozenset("aiueo")
CONSONANTS = frozenset("bcdfghjklmnpqrstvwxyz")
DIGRAPHS: tuple[str, ...] = ("ng", "ny", "kh", "sy")

VALID_ONSET_CLUSTERS = frozenset({
    "pr", "tr", "kr", "br", "dr", "gr", "fr",
    "pl", "kl", "bl", "fl", "sl", "sp", "st", "sk", "sw",
    "str", "skr", "spr",
})

VALID_CODA_CLUSTERS = frozenset({
    "ng", "kh", "sy", "ks", "ns", "nt", "rt", "rn", "st", "mp", "nk", "lt", "ld", "rf",
})


def tokenize_phonemes(word: str) -> list[str]:
    """Tokenize an alphabetic lowercase token into Indonesian single/digraph phonemes."""
    clean = re.sub(r"[^a-z]", "", str(word or "").lower())
    phonemes: list[str] = []
    idx = 0
    while idx < len(clean):
        pair = clean[idx : idx + 2]
        if pair in DIGRAPHS:
            phonemes.append(pair)
            idx += 2
        else:
            phonemes.append(clean[idx])
            idx += 1
    return phonemes


def _is_valid_onset(cluster: list[str]) -> bool:
    if not cluster:
        return True
    if len(cluster) == 1:
        return cluster[0] in CONSONANTS or cluster[0] in DIGRAPHS
    return "".join(cluster) in VALID_ONSET_CLUSTERS


def _is_valid_coda(cluster: list[str]) -> bool:
    if not cluster:
        return True
    if len(cluster) == 1:
        return cluster[0] in CONSONANTS or cluster[0] in DIGRAPHS
    if len(cluster) == 2 and all(len(c) == 1 for c in cluster):
        return "".join(cluster) in VALID_CODA_CLUSTERS
    return False


def _split_intervocalic(cluster: list[str]) -> tuple[list[str], list[str]]:
    if not cluster:
        return [], []
    if len(cluster) == 1:
        return [], list(cluster)
    if len(cluster) == 2:
        if "".join(cluster) in VALID_ONSET_CLUSTERS:
            return [], list(cluster)
        return [cluster[0]], [cluster[1]]
    if len(cluster) == 3 and "".join(cluster[1:]) in VALID_ONSET_CLUSTERS:
        return [cluster[0]], list(cluster[1:])
    return list(cluster[:-1]), [cluster[-1]]


def _syllable_cv_pattern(syll_phonemes: list[str]) -> str:
    return "".join("V" if ph in VOWELS else "K" for ph in syll_phonemes)


def syllabify_indonesian(word: str) -> dict[str, Any]:
    """Syllabify an Indonesian word and validate its phonotactic well-formedness."""
    raw = str(word or "").strip().lower()
    if not raw or not re.fullmatch(r"[a-z]+", raw):
        return {"word": raw, "syllables": [], "patterns": [], "pronounceable": False, "reason": "non_alfabet"}

    phonemes = tokenize_phonemes(raw)
    vowel_indices = [i for i, ph in enumerate(phonemes) if ph in VOWELS]
    if not vowel_indices:
        return {"word": raw, "syllables": [], "patterns": [], "pronounceable": False, "reason": "tanpa_vokal"}

    initial_onset = phonemes[: vowel_indices[0]]
    if not _is_valid_onset(initial_onset):
        return {"word": raw, "syllables": [], "patterns": [], "pronounceable": False, "reason": "gugus_awal_tidak_valid"}

    chunks: list[list[str]] = []
    cur_onset = list(initial_onset)
    for idx, v_pos in enumerate(vowel_indices):
        if idx + 1 < len(vowel_indices):
            next_v = vowel_indices[idx + 1]
            coda, next_onset = _split_intervocalic(phonemes[v_pos + 1 : next_v])
        else:
            coda, next_onset = phonemes[v_pos + 1 :], []
        if not (_is_valid_coda(coda) and _is_valid_onset(next_onset)):
            return {"word": raw, "syllables": [], "patterns": [], "pronounceable": False, "reason": "fonotaktik_tidak_wajar"}
        chunks.append(cur_onset + [phonemes[v_pos]] + coda)
        cur_onset = next_onset

    syllables = ["".join(ch) for ch in chunks]
    patterns = [_syllable_cv_pattern(ch) for ch in chunks]
    stress_idx = max(0, len(syllables) - 2) if len(syllables) >= 2 else 0
    prosody = "·".join(s.upper() if i == stress_idx else s for i, s in enumerate(syllables))
    return {
        "word": raw,
        "syllables": syllables,
        "patterns": patterns,
        "hyphenated": "-".join(syllables),
        "prosody_cue": prosody,
        "pronounceable": True,
        "reason": "valid",
    }


def synthesize_babble(
    *,
    consonants: list[str] | None = None,
    vowels: list[str] | None = None,
    count: int = 6,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Synthesize constrained Stage-1 infant CV/CVC vocalizations using given phoneme pools."""
    raw_c = consonants if consonants is not None else ["b", "m", "d", "n", "k", "t"]
    raw_v = vowels if vowels is not None else ["a", "i", "u"]
    c_pool = [c.lower() for c in raw_c if _is_valid_onset([c.lower()])]
    v_pool = [v.lower() for v in raw_v if v.lower() in VOWELS]
    if not c_pool or not v_pool:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in range(max(1, count * 3)):
        if len(out) >= count:
            break
        c1 = c_pool[(seed + step) % len(c_pool)]
        v1 = v_pool[(seed + step * 2) % len(v_pool)]
        c2 = c_pool[(seed + step + 1) % len(c_pool)]
        v2 = v_pool[(seed + step + 1) % len(v_pool)]
        candidate = f"{c1}{v1}{c1}{v1}" if step % 2 == 0 else f"{c1}{v1}{c2}{v2}"
        if candidate in seen:
            continue
        check = syllabify_indonesian(candidate)
        if check["pronounceable"]:
            seen.add(candidate)
            out.append(check)
    return out


def echo_input_syllables(text: str, *, max_words: int = 3) -> list[str]:
    """Extract pronounceable hyphenated Indonesian syllables from user text for infant mirroring."""
    tokens = [re.sub(r"[^a-z]", "", t.lower()) for t in re.findall(r"[a-zA-Z]+", str(text or ""))]
    sylls: list[str] = []
    for tok in tokens:
        if len(tok) < 2:
            continue
        parsed = syllabify_indonesian(tok)
        if parsed["pronounceable"]:
            sylls.append(parsed["hyphenated"])
        if len(sylls) >= max_words:
            break
    return sylls
