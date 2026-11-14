"""Indonesian Discourse Pragmatics, Teaching/Anaphora Parser, Lexicon Q&A, and Sentence Realizer (`ace_indo_nlp.discourse`).

Provides Stage-2..Stage-4 pragmatic understanding and compositional generation:
  - Direct vocabulary teaching, contextual anaphora follow-ups ("itu artinya ..."),
    and corrective revisions ("ralat kata X artinya Y")
  - Meaning, synonym, antonym, and morphological Q&A extraction
  - Colloquial-aware discourse cue & semantic domain analysis
  - Pure-Python compositional Indonesian Stage-4 dialogue & Q&A realization
"""
from __future__ import annotations

import re
from typing import Any

from .lexicon_kb import (
    NON_TEACHABLE_WORDS_ID,
    QUESTION_WORDS_ID,
    SEMANTIC_RELATIONS,
    STOPWORDS_ID,
    VALID_POS_ROLES,
    infer_indonesian_pos,
)
from .morphology import analyze_morphology, normalize_colloquial
from .phonotactics import syllabify_indonesian

_ANAPHORA_SKIP_WORDS = frozenset({
    "itu", "ini", "yang", "apa", "apaan", "bukan", "salah", "keliru",
    "kurang", "belum", "tidak", "jangan", "kosong", "tadi",
})

_DOMAIN_LEXICAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("alam", ("alam", "langit", "bumi", "air", "api", "cahaya", "samudra", "angin", "hujan", "gunung", "laut", "senja")),
    ("bahasa", ("bicara", "berbicara", "kata", "kalimat", "bahasa", "arti", "makna", "sinonim", "antonim", "suku", "fonem", "imbuhan")),
    ("memori", ("ingat", "memori", "catatan", "simpan", "lupa", "kemarin", "tadi", "riwayat")),
    ("rekayasa", ("kode", "berkas", "data", "program", "skrip", "sistem", "modul", "uji", "perbaiki")),
    ("verifikasi", ("bukti", "fakta", "uji", "periksa", "jujur", "nyata", "benar", "salah", "valid")),
    ("belajar", ("belajar", "latih", "ajar", "tahap", "ilmu", "paham", "tumbuh", "kembang", "bayi")),
    ("empati", ("tenang", "senang", "bingung", "sedih", "sabar", "ragu", "semangat", "hati", "maaf")),
)


def clean_definition_tail(raw_tail: str) -> tuple[str, str]:
    """Strip trailing punctuation and optional parenthesized POS role tag from a definition."""
    tail = str(raw_tail or "").strip().rstrip(".")
    roles_pat = "|".join(sorted(VALID_POS_ROLES))
    role = ""
    role_match = re.search(rf"\(({roles_pat})\)", tail, flags=re.IGNORECASE)
    if role_match:
        role = role_match.group(1).lower()
        tail = (tail[: role_match.start()] + tail[role_match.end() :]).strip(" ,;:-")
    return tail, role


def is_question_or_empty_tail(raw_tail: str) -> bool:
    """Reject empty, interrogative, or placeholder tails that must not become definitions."""
    stripped = str(raw_tail or "").strip()
    if not stripped or stripped.endswith("?"):
        return True
    tokens = re.findall(r"[a-zA-Z]+", stripped.lower())
    if not tokens:
        return True
    if tokens[0] in QUESTION_WORDS_ID or tokens[-1] in QUESTION_WORDS_ID:
        return True
    return stripped.lower().strip(" ?!.") in {"apa sih", "apa itu", "benar", "salah", "kosong"}


def _is_code_directive(lower: str) -> bool:
    return any(
        k in lower
        for k in ("buatkan aplikasi", "buat program", "buat skrip", "skrip python", "program python", "script python", "kode python")
    )


def _clean_alpha(tok: str) -> str:
    return re.sub(r"[^a-zA-Z]", "", str(tok or "")).lower()


def _parse_correction_directive(stripped: str) -> dict[str, Any] | None:
    patterns = (
        r"(?:ralat|koreksi|revisi)\s+(?:arti|makna|maksud)?\s*(?:kata\s+)?[\"']?([a-zA-Z-]{2,24})[\"']?\s*(?:artinya|berarti|maknanya|jadi|menjadi|adalah|=|:)\s*(.+)",
        r"(?:ubah|ganti|perbaiki)\s+(?:arti|makna|definisi)\s+(?:kata\s+)?[\"']?([a-zA-Z-]{2,24})[\"']?\s*(?:jadi|menjadi|adalah|=)\s*(.+)",
        r"bukan\s*,?\s*(?:maksudku|maksudnya)\s+(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:artinya|berarti|adalah|=)\s*(.+)",
    )
    for pat in patterns:
        match = re.search(pat, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        word = _clean_alpha(match.group(1))
        raw_tail = match.group(2).strip()
        if not word or word in NON_TEACHABLE_WORDS_ID or is_question_or_empty_tail(raw_tail):
            continue
        tail, role = clean_definition_tail(raw_tail)
        if not tail:
            continue
        return {"word": word, "meaning_id": tail, "role": role, "is_correction": True, "is_anaphora": False}
    return None


def _parse_anaphora_teaching(stripped: str, pending_word: str) -> dict[str, Any] | None:
    target = _clean_alpha(pending_word)
    if len(target) < 3 or target in NON_TEACHABLE_WORDS_ID:
        return None
    if re.match(r"^\s*(?:bukan|tidak|gak|gk)\b", stripped, flags=re.IGNORECASE):
        return None
    patterns = (
        r"^(?:oh\s*,?\s*)?(?:yang\s+tadi\s+)?itu\s+(?:artinya|berarti|maknanya|maksudnya|adalah|=|:)\s*(.+)$",
        r"^(?:oh\s*,?\s*)?(?:kalau\s+)?kata\s+(?:itu|tadi)\s+(?:artinya|berarti|maknanya|adalah|=)\s*(.+)$",
        r"^(?:oh\s*,?\s*)?(?:artinya|berarti|maknanya|maksudnya)\s*(?:adalah|ialah|itu|=|:)?\s*(.+)$",
    )
    for pat in patterns:
        match = re.match(pat, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        raw_tail = match.group(1).strip()
        first_tok = _clean_alpha(raw_tail.split()[0]) if raw_tail.split() else ""
        if first_tok in _ANAPHORA_SKIP_WORDS or is_question_or_empty_tail(raw_tail):
            continue
        tail, role = clean_definition_tail(raw_tail)
        if not tail:
            continue
        return {"word": target, "meaning_id": tail, "role": role, "is_correction": False, "is_anaphora": True}
    return None


def parse_teaching_or_correction(raw_text: str, *, pending_word: str = "") -> dict[str, Any] | None:
    """Parse direct teaching, corrective revision, or anaphoric definition follow-up."""
    stripped = str(raw_text or "").strip()
    lower = stripped.lower()
    if not stripped or "?" in stripped or _is_code_directive(lower):
        return None

    corr = _parse_correction_directive(stripped)
    if corr is not None:
        return corr

    patterns = (
        (r"(?:ajarkan|ajari|latih)\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1),
        (r"kata\s+baru\s*[:\-]?\s*[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1),
        (r"ingat\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1),
        (r"(?:arti|makna|maksud)\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s+(?:itu\s+)?(?:adalah|ialah|itu|=)\s+(.+)", 1),
        (r"kata\s+[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:adalah|ialah|artinya|berarti|maknanya|=)\s+(.+)", 1),
        (r"^\s*[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:artinya|berarti|maknanya)\s+(.+)", 1),
        (r"\bkata\s+[\"']?([a-zA-Z-]{3,24})[\"']?\s+itu\s+(.+)", 2),
    )
    for pat, min_words in patterns:
        match = re.search(pat, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        word = _clean_alpha(match.group(1))
        raw_tail = match.group(2).strip()
        if not word or word in NON_TEACHABLE_WORDS_ID or is_question_or_empty_tail(raw_tail):
            continue
        tail, role = clean_definition_tail(raw_tail)
        if len(tail.split()) < min_words:
            continue
        return {"word": word, "meaning_id": tail, "role": role, "is_correction": False, "is_anaphora": False}

    if pending_word:
        return _parse_anaphora_teaching(stripped, pending_word)
    return None


def extract_query_target(user_text: str, *, pending_word: str = "") -> dict[str, str] | None:
    """Extract meaning, synonym, antonym, or morphology Q&A target word and kind."""
    stripped = str(user_text or "").strip()
    skip_words = QUESTION_WORDS_ID | {"yang", "dari", "dalam", "untuk", "itu", "ini", "sini", "situ", "sana"}

    kind_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "synonym",
            (
                r"(?:apa|apakah|sebutkan)?\s*(?:sinonim|persamaan\s+kata|padanan\s+kata)\s+(?:dari\s+)?(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?",
                r"[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:sinonimnya|persamaan\s+katanya)\s*(?:apa|apaan)?\??\s*$",
            ),
        ),
        (
            "antonym",
            (
                r"(?:apa|apakah|sebutkan)?\s*(?:antonim|lawan\s+kata|kebalikan\s+kata)\s+(?:dari\s+)?(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?",
                r"[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:antonimnya|lawan\s+katanya)\s*(?:apa|apaan)?\??\s*$",
            ),
        ),
        (
            "morphology",
            (
                r"(?:apa|sebutkan)?\s*(?:kata\s+dasar|akar\s+kata|suku\s+kata|morfo(?:logi)?)\s+(?:dari\s+)?(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?",
            ),
        ),
        (
            "meaning",
            (
                r"(?:apa|apakah|jelaskan)\s+(?:itu\s+)?(?:arti|artinya|makna|maknanya|maksud|maksudnya|definisi)\s+(?:dari\s+)?(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?",
                r"(?:arti|artinya|makna|maknanya|maksud|maksudnya|definisi)\s+(?:dari\s+)?(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?",
                r"^\s*(?:kata\s+)?[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:artinya|maknanya|maksudnya)?\s*(?:apa|apaan)\??\s*$",
            ),
        ),
    )
    for kind, pats in kind_patterns:
        for pat in pats:
            match = re.search(pat, stripped, flags=re.IGNORECASE)
            if not match:
                continue
            cand = _clean_alpha(match.group(1))
            if cand and cand not in skip_words:
                return {"word": cand, "query_kind": kind}

    clean_pending = _clean_alpha(pending_word)
    if clean_pending and re.match(r"^\s*(?:apa\s+)?(?:artinya|maknanya|maksudnya)\s*(?:itu\s*)?(?:apa)?\??\s*$", stripped, flags=re.IGNORECASE):
        return {"word": clean_pending, "query_kind": "meaning"}
    return None


def extract_meaning_query(user_text: str) -> str | None:
    """Return queried word string when input asks meaning of a specific word."""
    hit = extract_query_target(user_text)
    if hit and hit["query_kind"] == "meaning":
        return hit["word"]
    return None


def _detect_question_focus(norm_lower: str, raw_text: str) -> tuple[bool, str]:
    wh_order = ("bagaimana", "mengapa", "kenapa", "siapa", "kapan", "dimana", "mana", "berapa", "apa", "apakah")
    for wh in wh_order:
        if re.search(rf"\b{wh}\b", norm_lower):
            return True, "mengapa" if wh == "kenapa" else ("apa" if wh == "apakah" else wh)
    return ("?" in raw_text), "umum" if "?" in raw_text else ""


def _infer_active_domains(norm_lower: str, cues: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    tokens = set(re.findall(r"[a-z]+", norm_lower))
    for dom, keys in _DOMAIN_LEXICAL_HINTS:
        if any(k in tokens for k in keys):
            domains.append(dom)
    if cues["is_confused_or_negative"] and "empati" not in domains:
        domains.append("empati")
    if cues["is_positive"] and "positif" not in domains:
        domains.append("positif")
    if cues["is_greeting"] and "sapaan" not in domains:
        domains.append("sapaan")
    if cues["is_question"] and "tanya" not in domains:
        domains.append("tanya")
    return domains


def analyze_discourse_cues(
    user_text: str,
    *,
    colloquial_text: str = "",
    pending_word: str = "",
) -> dict[str, Any]:
    """Extract rich Indonesian pragmatics, sentiment, colloquial rewrites, and query cues."""
    if colloquial_text:
        norm_col, slang_rewrites = colloquial_text.lower(), {}
    else:
        norm_col, slang_rewrites = normalize_colloquial(user_text)
    raw_low = str(user_text or "").lower()
    comb = f"{raw_low} {norm_col}"

    is_greeting = any(
        re.search(rf"\b{w}\b", comb)
        for w in ("halo", "hai", "hi", "selamat", "pagi", "siang", "sore", "malam", "permisi", "salam")
    )
    asks_wellbeing = (
        any(p in comb for p in ("apa kabar", "gimana kabar", "bagaimana kabarmu", "bagaimana kabar", "kabar kamu"))
        or (bool(re.search(r"\bkabar\b", norm_col)) and bool(re.search(r"\b(apa|bagaimana)\b", norm_col)))
    )
    is_thanks = any(p in comb for p in ("terima kasih", "makasih", "trims", "thanks"))
    is_question, q_focus = _detect_question_focus(norm_col, str(user_text or ""))
    is_confused = any(
        re.search(rf"\b{w}\b", comb)
        for w in ("bingung", "pusing", "susah", "sulit", "error", "gagal", "kesal", "capek", "sedih", "ragu")
    )
    is_positive = any(
        re.search(rf"\b{w}\b", comb)
        for w in ("bagus", "mantap", "keren", "senang", "gembira", "bahagia", "hebat", "suka", "yakin")
    )
    mentions_speech = any(
        re.search(rf"\b{w}\b", comb)
        for w in ("bicara", "berbicara", "kata", "kalimat", "bahasa", "belajar", "bayi", "tahap", "sinonim", "antonim", "imbuhan", "makna")
    )
    q_target = extract_query_target(str(user_text or ""), pending_word=pending_word)
    cues: dict[str, Any] = {
        "normalized_colloquial": norm_col,
        "slang_rewrites": slang_rewrites,
        "is_greeting": is_greeting,
        "asks_wellbeing": asks_wellbeing,
        "is_thanks": is_thanks,
        "is_question": is_question,
        "question_focus": q_focus,
        "is_confused_or_negative": is_confused,
        "is_positive": is_positive,
        "mentions_speech": mentions_speech,
        "query_target": q_target,
        "meaning_query_word": q_target["word"] if q_target and q_target["query_kind"] == "meaning" else None,
        "lexicon_qa_target": q_target,
    }
    cues["active_domains"] = _infer_active_domains(norm_col, cues)
    return cues


def format_lexicon_qa_clauses(
    *,
    query_target: dict[str, str],
    entry: dict[str, Any] | None,
    grounded: list[dict[str, Any]],
    mode_label: str,
    known_roots: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """Generate grounded Indonesian clauses answering meaning, synonym, antonym, or morphology Q&A."""
    target_word = query_target["word"]
    kind = query_target["query_kind"]

    if kind == "morphology":
        syll = syllabify_indonesian(target_word)
        morph = analyze_morphology(target_word, known_roots=known_roots)
        syl_str = syll["hyphenated"] if syll["pronounceable"] else target_word
        pros_str = syll.get("prosody_cue") or syl_str
        affixes = ", ".join(morph["prefixes"] + morph["suffixes"] + morph["clitics"]) or "tanpa imbuhan"
        root_note = f"akar kata `{morph['root']}`" if morph["root"] else "bentuk dasar"
        if morph["root"] and entry and entry["word"] == morph["root"]:
            root_note += f" (*{entry['meaning_id']}*)"
        return [
            f"Analisis morfologi & fonotaktik kata **`{target_word}`** (mode **{mode_label}**): "
            f"suku kata `{syl_str}` (tekanan `{pros_str}`), terurai menjadi {root_note} dengan imbuhan `{affixes}`."
        ]

    if entry is None:
        syll = syllabify_indonesian(target_word)
        syl_note = f" (`{syll['hyphenated']}`)" if syll["pronounceable"] else ""
        return [
            f"Sejujurnya kata **`{target_word}`**{syl_note} belum ada di leksikon persisten **ACE** (mode **{mode_label}**), "
            "jadi aku tidak mau mengarang maknanya.",
            f"Kamu bisa mengajariku langsung lewat chat, misalnya *\"{target_word} itu artinya ...\"* atau *\"ajarkan kata {target_word} artinya ...\"*.",
        ]

    kb_rel = SEMANTIC_RELATIONS.get(entry["word"], {})
    syns = list(dict.fromkeys(list(entry.get("synonyms") or []) + list(kb_rel.get("synonyms") or [])))
    ants = list(dict.fromkeys(list(entry.get("antonyms") or []) + list(kb_rel.get("antonyms") or [])))

    if kind == "synonym":
        if syns:
            syn_str = ", ".join(f"`{s}`" for s in syns[:5])
            return [f"Menurut memori **ACE** ({mode_label}), sinonim atau padanan kata **`{entry['word']}`** (*{entry['meaning_id']}*) antara lain: {syn_str}."]
        return [f"Kata **`{entry['word']}`** (*{entry['meaning_id']}*) ada di memoriku, namun belum memiliki daftar sinonim khusus saat ini."]

    if kind == "antonym":
        if ants:
            ant_str = ", ".join(f"`{a}`" for a in ants[:5])
            return [f"Menurut memori **ACE** ({mode_label}), antonim atau lawan kata **`{entry['word']}`** (*{entry['meaning_id']}*) meliputi: {ant_str}."]
        return [f"Kata **`{entry['word']}`** (*{entry['meaning_id']}*) tercatat di leksikon **ACE**, namun lawan katanya belum didaftarkan."]

    src_label = "ajaranmu di memori **ACE**" if entry["source"] == "user_taught" else "leksikon dasar **ACE**"
    extra = [
        g for g in grounded
        if g["word"] != entry["word"]
        and g["word"] not in STOPWORDS_ID
        and g["word"] not in QUESTION_WORDS_ID
    ]
    extra_str = ", ".join(f"`{g['word']}`" for g in extra[:3])
    extra_note = f" Dalam konteks pesanmu, kata ini juga berkaitan dengan {extra_str}." if extra_str else ""
    syn_note = f" Sinonim dekatnya: {', '.join(f'`{s}`' for s in syns[:3])}." if syns else ""
    ant_note = f" Lawan katanya: {', '.join(f'`{a}`' for a in ants[:2])}." if ants else ""
    rev_n = int(entry.get("revision_count", 0) or 0)
    rev_note = f" (sudah diperbarui `{rev_n}x`)" if rev_n > 0 else ""
    ex_first = entry["examples"][0] if entry.get("examples") else ""
    ex_line = f' Contoh pemakaiannya: *"{ex_first}"*.' if ex_first else ""
    syl_joined = "-".join(entry["syllables"])
    morph_note = (
        f" (bentuk berimbuhan dari `{entry['word']}`)"
        if target_word != entry["word"]
        else ""
    )
    return [
        f"Menurut {src_label}, kata **`{entry['word']}`**{morph_note} (`{syl_joined}`, peran `{entry['role']}`{rev_note}) "
        f"berarti *{entry['meaning_id']}*.{ex_line}{syn_note}{ant_note}{extra_note}",
    ]


def _pick_variant(variants: list[str], seed_text: str, turn_index: int, recent_texts: list[str]) -> str:
    recent_win = recent_texts[-4:]
    seed_num = sum(ord(ch) for ch in seed_text) + turn_index
    for offset in range(len(variants)):
        cand = variants[(seed_num + offset) % len(variants)]
        if all(cand.strip() not in prev for prev in recent_win):
            return cand
    return variants[seed_num % len(variants)]


def _compose_opening_clause(
    *,
    user_text: str,
    cues: dict[str, Any],
    profile: dict[str, Any],
    mode_label: str,
    recent_assistant_texts: list[str],
    history_turns: int,
) -> str:
    if cues["asks_wellbeing"]:
        return (
            f"Kabar **ACE** baik dan stabil di mode **{mode_label}**. "
            f"Kemampuan bicaraku sudah di Tahap `4/4` dengan **{profile['vocab_count']} kosakata** persisten "
            f"({profile['user_taught_count']} ajaran pengguna)."
        )
    if cues["is_thanks"]:
        return f"Sama-sama! Aku **ACE** senang bisa membantu dan terus mencatat kosakata maupun progres nyata di mode **{mode_label}**."
    if cues["is_confused_or_negative"]:
        variants = [
            f"Tenang, aku **ACE** siap menemani di mode **{mode_label}** supaya kendala ini bisa kita urai satu langkah per satu.",
            f"Aku **ACE** paham bagian itu terasa membingungkan. Mari pecah jadi satu bagian terkecil dulu ({mode_label}).",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_assistant_texts)
    if cues["is_positive"]:
        variants = [
            f"Senang mendengar progresnya berjalan baik! Aku **ACE** terus menjaga memorinya tetap konsisten ({mode_label}).",
            f"Mantap, terima kasih apresiasinya! Aku **ACE** siap lanjut ke langkah atau topik berikutnya ({mode_label}).",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_assistant_texts)
    variants = [
        f"Halo, aku **ACE** ({mode_label}). Aku menyimak maksud pesanmu dengan baik.",
        f"Pesanmu kuterima dengan jelas; aku **ACE** ({mode_label}) siap nyambung membahas topik ini.",
        f"Baik, aku **ACE** di mode **{mode_label}** menangkap arah obrolanmu dan terus mempelajarinya.",
        f"Sip, aku **ACE** ({mode_label}) mencatat konteks percakapan kita supaya tetap nyambung.",
    ]
    return _pick_variant(variants, user_text, history_turns, recent_assistant_texts)


def _format_grounded_memory_clause(
    *,
    taught_hits: list[dict[str, Any]],
    grounded: list[dict[str, Any]],
    cues: dict[str, Any],
    profile: dict[str, Any],
) -> str | None:
    if len(taught_hits) >= 2:
        w1, w2 = taught_hits[0], taught_hits[1]
        s1, s2 = "-".join(w1["syllables"]), "-".join(w2["syllables"])
        return (
            f"Aku ingat kata **`{w1['word']}`** (`{s1}`) berarti *{w1['meaning_id']}* "
            f"dan **`{w2['word']}`** (`{s2}`) berarti *{w2['meaning_id']}*."
        )
    if taught_hits:
        w = taught_hits[0]
        w_syl = "-".join(w["syllables"])
        ex_list = w.get("examples") or []
        ex_note = f' (contoh: *"{ex_list[0]}"*)' if ex_list else ""
        return f"Aku ingat kata **`{w['word']}`** (`{w_syl}`) yang kamu ajarkan berarti *{w['meaning_id']}*{ex_note}."
    if cues["mentions_speech"] and not cues["asks_wellbeing"]:
        return f"Kemampuan bicaraku kini di Tahap `4/4` dengan **{profile['vocab_count']} kata** tersimpan."
    if grounded and not cues["is_greeting"]:
        ground_str = ", ".join(f"`{g['word']}`" for g in grounded[:3])
        return f"Kata kunci yang kutangkap: {ground_str}."
    return None


def realize_indonesian_clauses(
    *,
    user_text: str,
    cues: dict[str, Any],
    grounded: list[dict[str, Any]],
    profile: dict[str, Any],
    mode_label: str,
    latest_task: dict[str, Any] | None,
    recent_assistant_texts: list[str],
    history_turns: int,
    curious_word: dict[str, Any] | None,
) -> list[str]:
    """Compose context-sensitive, grounded, anti-repetitive Stage-4 Indonesian reply clauses."""
    taught_hits = [w for w in grounded if w["source"] == "user_taught"]
    parts: list[str] = [
        _compose_opening_clause(
            user_text=user_text,
            cues=cues,
            profile=profile,
            mode_label=mode_label,
            recent_assistant_texts=recent_assistant_texts,
            history_turns=history_turns,
        )
    ]

    mem_clause = _format_grounded_memory_clause(
        taught_hits=taught_hits,
        grounded=grounded,
        cues=cues,
        profile=profile,
    )
    if mem_clause:
        parts.append(mem_clause)

    show_task = bool(
        latest_task
        and (latest_task.get("status") != "COMPLETED" or latest_task.get("kind") != "learning_task")
        and not cues["is_greeting"]
    )
    if show_task and latest_task:
        parts.append(f"Status tugas terakhir (**{latest_task['title_id']}**): `{latest_task['status']}`.")

    if curious_word:
        syls = "-".join(curious_word["syllables"])
        parts.append(f"Ngomong-ngomong, aku belum mengenal makna kata **`{curious_word['word']}`** (`{syls}`) — artinya apa menurutmu?")
    elif (
        not taught_hits
        and cues["is_question"]
        and not show_task
        and any(k in cues["normalized_colloquial"] for k in ("tugas", "progres", "kerja", "jalan"))
    ):
        parts.append("Saat ini belum ada tugas kode aktif di belakang layar, jadi kita bisa berdiskusi leluasa dulu.")

    return parts


__all__ = [
    "analyze_discourse_cues",
    "clean_definition_tail",
    "extract_meaning_query",
    "extract_query_target",
    "format_lexicon_qa_clauses",
    "infer_indonesian_pos",
    "is_question_or_empty_tail",
    "parse_teaching_or_correction",
    "realize_indonesian_clauses",
]
