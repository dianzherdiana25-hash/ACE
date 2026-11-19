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

_REPORTED_SPEECH_SUBJECTS = frozenset({
    "orang", "teman", "temanku", "sahabat", "dia", "mereka", "kalian", "beliau",
    "ibu", "ayah", "mama", "papa", "bapak", "kakak", "adik", "guru", "dosen",
    "dokter", "bos", "kamu", "aku", "kami", "kita", "siapa", "apa",
})

_DOMAIN_LEXICAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("alam", ("alam", "langit", "bumi", "air", "api", "cahaya", "samudra", "angin", "hujan", "gunung", "laut", "senja", "cuaca", "hawa", "malam", "pagi", "bintang")),
    ("bahasa", ("bicara", "berbicara", "kata", "kalimat", "bahasa", "arti", "makna", "sinonim", "antonim", "suku", "fonem", "imbuhan")),
    ("memori", ("ingat", "memori", "catatan", "simpan", "lupa", "kemarin", "tadi", "riwayat")),
    ("rekayasa", ("kode", "berkas", "data", "program", "skrip", "sistem", "modul", "uji", "perbaiki")),
    ("verifikasi", ("bukti", "fakta", "uji", "periksa", "jujur", "nyata", "benar", "salah", "valid")),
    ("belajar", ("belajar", "latih", "ajar", "tahap", "ilmu", "paham", "tumbuh", "kembang", "bayi")),
    ("empati", ("tenang", "senang", "bingung", "sedih", "sabar", "ragu", "semangat", "hati", "maaf", "capek", "lelah", "bosan", "lapar")),
    ("harian", ("kopi", "teh", "makan", "minum", "warna", "musik", "lagu", "hobi", "tidur", "santai", "kerja", "kucing")),
)

_COLOR_WORDS = frozenset({"merah", "biru", "hijau", "kuning", "putih", "hitam", "ungu", "jingga", "abu", "pink", "cokelat"})


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
        (r"(?:ajarkan|ajari|latih)\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1, False),
        (r"kata\s+baru\s*[:\-]?\s*[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1, False),
        (r"ingat\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s*(?:artinya|berarti|maknanya|=|:|-)\s*(.+)", 1, False),
        (r"(?:arti|makna|maksud)\s+kata\s+[\"']?([a-zA-Z-]+)[\"']?\s+(?:itu\s+)?(?:adalah|ialah|itu|=)\s+(.+)", 1, False),
        (r"kata\s+[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:adalah|ialah|artinya|berarti|maknanya|=)\s+(.+)", 1, True),
        (r"^\s*[\"']?([a-zA-Z-]{3,24})[\"']?\s+(?:itu\s+)?(?:artinya|berarti|maknanya)\s+(.+)", 1, False),
        (r"\bkata\s+[\"']?([a-zA-Z-]{3,24})[\"']?\s+itu\s+(.+)", 2, True),
    )
    for pat, min_words, guard_speaker in patterns:
        match = re.search(pat, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        word = _clean_alpha(match.group(1))
        raw_tail = match.group(2).strip()
        if not word or word in NON_TEACHABLE_WORDS_ID or is_question_or_empty_tail(raw_tail):
            continue
        if guard_speaker and word in _REPORTED_SPEECH_SUBJECTS:
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
    skip_words = QUESTION_WORDS_ID | {"yang", "dari", "dalam", "untuk", "itu", "ini", "sini", "situ", "sana",
                                      # Kata bingkai tanya-makna tidak pernah menjadi kata target:
                                      # "artinya apa?" harus jatuh ke fallback pending_word.
                                      "arti", "artinya", "makna", "maknanya", "maksud", "maksudnya", "definisi"}

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


def _detect_greeting_period(comb: str, raw_low: str = "") -> str:
    for period in ("pagi", "siang", "sore", "malam"):
        if re.search(rf"\bselamat\s+{period}\b", comb):
            return period
    toks = re.findall(r"[a-z]+", (raw_low or comb).strip().lower())
    if toks and toks[0] in ("pagi", "siang", "sore", "malam"):
        non_greet_next = {"ini", "itu", "tadi", "nanti", "kemarin", "besok", "hari", "banget", "bgt", "sekali", "yang", "sekarang"}
        if len(toks) == 1 or (len(toks) == 2 and toks[1] not in non_greet_next):
            return toks[0]
    if "assalam" in comb or "salam" in comb:
        return "salam"
    return ""


def _detect_dialogue_act(raw_low: str, norm_col: str, tokens: set[str], is_question: bool) -> str:
    comb = f"{raw_low} {norm_col}"
    if "haha" in norm_col.split() or any(w in tokens for w in ("lucu", "ngakak", "kocak", "receh", "ketawa")):
        return "laughter"
    if any(p in comb for p in ("siapa namamu", "namamu siapa", "siapa nama kamu", "kamu siapa", "siapa kamu", "kamu ai", "kamu bot", "kamu robot", "kenalan", "perkenalkan")):
        return "identity"
    if any(p in comb for p in ("lagi ngapain", "sedang apa", "lagi apa", "kamu lagi apa", "ngapain aja")):
        return "casual_activity"
    if any(p in comb for p in ("ceritain sesuatu", "cerita dong", "ceritakan sesuatu", "kasih cerita", "cerita singkat", "fakta menarik")):
        return "story_request"
    if any(w in tokens for w in ("capek", "lelah", "letih", "mengantuk")):
        return "emotion_tired"
    if any(w in tokens for w in ("bosan", "jenuh")):
        return "emotion_bored"
    if any(w in tokens for w in ("lapar", "haus")):
        return "emotion_hungry"
    if any(w in tokens for w in ("sedih", "galau", "kecewa")):
        return "emotion_sad"
    if any(w in tokens for w in ("cemas", "khawatir", "stres", "takut", "marah", "kesal")):
        return "emotion_anxious"
    if any(w in tokens for w in ("bingung", "pusing", "sulit", "susah", "ragu", "error", "gagal")):
        return "emotion_confused"
    if is_question and any(w in comb for w in ("suka ", "favorit", "lebih suka", "pendapatmu", "menurutmu", "atau ")):
        return "preference_question"
    return "general"


def analyze_discourse_cues(
    user_text: str,
    *,
    colloquial_text: str = "",
    pending_word: str = "",
) -> dict[str, Any]:
    """Extract rich Indonesian pragmatics, dialogue act, sentiment, colloquial rewrites, and Q&A cues."""
    if colloquial_text:
        norm_col, slang_rewrites = colloquial_text.lower(), {}
    else:
        norm_col, slang_rewrites = normalize_colloquial(user_text)
    raw_low = str(user_text or "").lower()
    comb = f"{raw_low} {norm_col}"
    tokens = set(re.findall(r"[a-z]+", comb))

    greet_period = _detect_greeting_period(comb, raw_low)
    greet_words = ("halo", "hai", "hi", "hey", "hei", "selamat", "permisi", "salam", "assalamualaikum")
    is_greeting = any(w in tokens for w in greet_words) or greet_period in {"pagi", "siang", "sore", "malam", "salam"}
    asks_wellbeing = (
        any(p in comb for p in ("apa kabar", "kabarnya", "kabarmu", "gimana kabar", "bagaimana kabar", "kabar kamu"))
        or ("kabar" in tokens and bool(tokens & {"apa", "bagaimana", "baik"}))
    )
    is_thanks = any(p in comb for p in ("terima kasih", "makasih", "trims", "thanks")) or ("terima" in tokens and "makasih" in raw_low) or bool(tokens & {"mksh", "mksih", "thx"})
    is_question, q_focus = _detect_question_focus(norm_col, str(user_text or ""))
    neg_words = ("bingung", "pusing", "susah", "sulit", "error", "gagal", "kesal", "capek", "lelah", "sedih", "ragu", "bosan", "lapar", "cemas", "marah", "kecewa")
    is_confused = bool(tokens & set(neg_words))
    pos_words = ("bagus", "mantap", "keren", "senang", "gembira", "bahagia", "hebat", "suka", "yakin", "seru", "asyik", "nyaman", "sehat")
    is_positive = bool(tokens & set(pos_words)) and not is_question
    speech_words = (
        "bicara", "berbicara", "kalimat", "bahasa", "belajar", "bayi",
        "tahap", "sinonim", "antonim", "imbuhan", "makna", "kosakata", "leksikon", "lafal", "pelafalan",
    )
    mentions_speech = bool(tokens & set(speech_words)) or bool(
        re.search(r"\b(?:arti|makna|ajarkan|ajari|latih|ralat|belajar)\s+kata\b", comb)
    )
    q_target = extract_query_target(str(user_text or ""), pending_word=pending_word)
    d_act = _detect_dialogue_act(raw_low, norm_col, tokens, is_question)
    cues: dict[str, Any] = {
        "normalized_colloquial": norm_col,
        "slang_rewrites": slang_rewrites,
        "is_greeting": is_greeting,
        "greeting_period": greet_period,
        "asks_wellbeing": asks_wellbeing,
        "is_thanks": is_thanks,
        "is_question": is_question,
        "question_focus": q_focus,
        "is_confused_or_negative": is_confused,
        "is_positive": is_positive,
        "mentions_speech": mentions_speech,
        "dialogue_act": d_act,
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
    morph_note = f" (bentuk berimbuhan dari `{entry['word']}`)" if target_word != entry["word"] else ""
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


def _extract_last_topic(conversation_context: dict[str, Any] | None, recent_messages: list[dict[str, Any]] | None) -> str:
    topic = str((conversation_context or {}).get("last_topic", "")).strip()
    if topic:
        return topic
    if not recent_messages:
        return ""
    for msg in reversed(recent_messages[-4:]):
        if msg.get("role") != "assistant":
            continue
        low = str(msg.get("text", "")).lower()
        if "warna apa" in low:
            return "warna"
        if "tim kopi atau tim teh" in low or "suka kopi atau teh" in low:
            return "minuman"
        if "kurang tidur" in low or "capek" in low:
            return "istirahat"
        if "ceritain sesuatu" in low or "tebak kata" in low:
            return "saran_bosan"
        break
    return ""


def _compose_followup_turn(
    user_text: str,
    cues: dict[str, Any],
    last_topic: str,
    history_turns: int,
    recent_texts: list[str],
) -> tuple[str, str, str] | None:
    tokens = set(re.findall(r"[a-z]+", cues["normalized_colloquial"]))
    raw_low = user_text.lower()
    if not last_topic or len(tokens) > 7 or cues["is_question"] or cues["is_greeting"]:
        return None

    color_hit = next((c for c in _COLOR_WORDS if c in tokens), "")
    if last_topic == "warna" and (color_hit or len(tokens) <= 3):
        chosen = color_hit or next(iter(tokens), "itu")
        reply = (
            f"Warna **{chosen}** memang punya kesan yang khas dan enak dilihat! "
            "Biasanya kamu lebih suka nuansa yang lembut atau yang agak mencolok?"
        )
        return reply, "obrolan_ringan", "Biasanya kamu lebih suka nuansa yang lembut atau yang agak mencolok?"

    if last_topic == "minuman" and tokens & {"kopi", "teh", "air", "susu", "cokelat", "duanya", "keduanya"}:
        if "kopi" in tokens:
            return "Tim **kopi** memang paling pas buat nemenin mikir atau santai! Kamu biasanya lebih cocok kopi manis atau yang agak pahit?", "kopi_selera", ""
        if "teh" in tokens:
            return "Tim **teh** itu adem banget rasanya, cocok diminum pelan-pelan pas lagi rehat. Kamu lebih suka teh hangat atau es teh manis?", "teh_selera", ""
        return "Mantap, fleksibel antara kopi maupun teh sesuai suasana ya! Paling enak memang nemenin obrolan santai gini.", "obrolan_ringan", ""

    if last_topic == "istirahat":
        if tokens & {"tidur", "ngantuk", "begadang", "kurang"}:
            return "Kurang tidur memang cepat bikin energi turun. Malam ini coba sempatkan tidur agak lebih cepat ya biar besok lebih seger!", "santai", ""
        if tokens & {"kerja", "kerjaan", "tugas", "kuliah", "sibuk", "capek"}:
            return "Pantas kerasa melelahkan kalau beban tugas lagi menumpuk. Jangan lupa jeda sebentar ya; kalau ada hal yang mau dibantu beresin, bilang aja ke ACE.", "bantuan_ringan", ""
        return "Yang penting sekarang beri ruang buat napas sebentar. Santai dulu di sini sambil ngobrol ringan juga boleh banget kok.", "obrolan_ringan", ""

    if last_topic == "saran_bosan":
        if "cerita" in tokens or "ceritakan" in tokens:
            return _compose_story_reply(user_text, history_turns, recent_texts)
        if "tebak" in tokens:
            return (
                "Yuk main tebak kata ringan! Cluenya: aku berwarna biru luas saat cerah, menaungi bumi dari atas, "
                "dan warnaku berubah jingga pas senja. Menurutmu aku apa?"
            ), "tebak_langit", "Menurutmu aku apa?"
        if any(w in raw_low for w in ("kode", "skrip", "program", "bikin", "buat")):
            return "Siap! Mau dibikinkan skrip apa nih — pengatur pengeluaran, pengolah CSV, atau game tebak angka?", "pilih_kode", ""

    if last_topic == "tebak_langit":
        if "langit" in tokens or "awan" in tokens or "angkasa" in tokens:
            return "Tepat banget, jawabannya **langit**! Haha, tebakannya langsung kena. Mau lanjut satu ronde lagi atau ganti bahas yang lain?", "obrolan_ringan", ""
        return f"Dekat tuh dengan `{next(iter(tokens), 'tebakanmu')}`! Jawabannya adalah **langit** — biru pas siang, jingga pas senja.", "obrolan_ringan", ""

    if tokens <= {"iya", "ya", "yap", "betul", "benar", "boleh", "lanjut", "terus", "sip", "oke"}:
        variants = [
            "Sip, nyambung nih! Menurutmu bagian mana yang paling seru buat diterusin?",
            "Oke, siap lanjut! Ada detail atau ide tambahan dari sisi kamu?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "obrolan_ringan", ""
    return None


def _compose_story_reply(user_text: str, history_turns: int, recent_texts: list[str]) -> tuple[str, str, str]:
    stories = [
        (
            "Ada satu cerita menarik dari bahasa Indonesia: kita punya satu kata singkat, **\"rindu\"**, "
            "yang terasa hangat sekaligus dalam saat dipakai berbagi rasa tentang jarak maupun kenangan. "
            "Kalau kamu sendiri lagi suka topik santai tentang cerita, musik, atau teknologi?"
        ),
        (
            "Cerita singkat nih: bayangin suasana kedai kecil pas hujan sore — suara rintik hujan bikin orang otomatis ngomong lebih pelan dan tenang. "
            "Biasanya kalau hujan gitu, kamu lebih suka dengerin musik, rebahan, atau ngemil hangat?"
        ),
        (
            "Ada cerita menarik soal **ACE**: di Termux sekalipun, sistem ini bisa jalan penuh tanpa kuota internet buat bantu nulis skrip dan ngobrol. "
            "Menurutmu fitur seperti itu paling enak dipakai buat proyek kecil apa nih?"
        ),
    ]
    picked = _pick_variant(stories, user_text, history_turns, recent_texts)
    return picked, "cerita", "Bagaimana menurutmu?"


def _compose_greeting_identity_turn(
    cues: dict[str, Any],
    user_text: str,
    mode_label: str,
    history_turns: int,
    recent_texts: list[str],
    stage_id: int,
) -> tuple[str, str, str] | None:
    act = cues["dialogue_act"]
    period = cues["greeting_period"]
    stage_note = f" (tahap `0/4`)" if stage_id == 0 and (history_turns <= 1 or cues["mentions_speech"]) else ""

    if act == "identity":
        variants = [
            f"Kenalin, aku **ACE** — asisten sekaligus teman ngobrol lokalmu di mode **{mode_label}**{stage_note}. Kalau kamu lagi pengin ngobrol santai atau ngerjain sesuatu, tinggal bilang aja!",
            f"Namaku **ACE**! Aku berjalan lokal di mode **{mode_label}**{stage_note} dan selalu ingat obrolan serta kosakata yang kita bahas. Lagi pengin bahas apa hari ini?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "identitas", ""

    if act == "casual_activity":
        variants = [
            "Lagi standby nemenin kamu di sini nih! Kalau kamu sendiri lagi sibuk apa, atau lagi pengin santai ngobrol dulu?",
            "Lagi siap sedia dengerin obrolanmu dan nyusun ide kalau sewaktu-waktu dibutuhin. Hari ini lagi seru atau santai aja?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "santai", ""

    if cues["asks_wellbeing"]:
        greet_head = f"Selamat {period}! " if period in {"pagi", "siang", "sore", "malam"} else ("Waalaikumsalam! " if period == "salam" else "")
        variants = [
            f"{greet_head}Kabar **ACE** baik dan masih ingat obrolan kita kok{stage_note}! Kamu sendiri gimana kabarnya sekarang?",
            f"{greet_head}Kabar **ACE** aman dan siap nemenin ngobrol kapan saja{stage_note}. Gimana harimu sejauh ini?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "kabar_user", "Kamu sendiri gimana kabarnya sekarang?"

    if cues["is_greeting"]:
        if period == "salam":
            return f"Waalaikumsalam! Halo, aku **ACE**{stage_note}. Senang disapa hari ini — lagi santai atau ada yang mau kita bahas bareng?", "sapaan", ""
        if period in {"pagi", "siang", "sore", "malam"}:
            return f"Selamat {period}! Aku **ACE**{stage_note} siap nemenin ngobrol atau bantu kerjaanmu. Lagi ada aktivitas apa nih?", "sapaan", ""
        variants = [
            f"Halo! Aku **ACE**{stage_note}, senang bisa ngobrol sama kamu. Lagi pengin cerita sesuatu atau nanya apa hari ini?",
            f"Hai! **ACE** di sini{stage_note}. Gimana kabarmu — ada yang seru atau lagi butuh teman ngobrol nih?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "sapaan", ""

    if cues["is_thanks"]:
        variants = [
            "Sama-sama! Senang banget bisa bantu dan nemenin di sini. Kabari aja ya kalau ada lagi yang mau diobrolin.",
            "Dengan senang hati! **ACE** selalu siap bantu dan lanjut ngobrol kapan pun kamu butuh.",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "terima_kasih", ""
    return None


def _compose_emotion_or_humor_turn(
    cues: dict[str, Any],
    user_text: str,
    history_turns: int,
    recent_texts: list[str],
) -> tuple[str, str, str] | None:
    act = cues["dialogue_act"]
    emotion_templates: dict[str, tuple[list[str], str, str]] = {
        "laughter": (
            [
                "Haha, ikut seneng nih dengernya! Lagi ada cerita atau momen lucu apa hari ini?",
                "Haha wkwk, jadi ikutan ketawa nih! Memang lucu — bagi cerita serunya dong kalau boleh.",
            ],
            "cerita_seru",
            "",
        ),
        "emotion_tired": (
            [
                "Waduh, pasti lumayan menguras tenaga ya hari ini. Jangan lupa minum air dan tarik napas sebentar biar nggak terlalu capek — lagi capek kerjaan atau kurang tidur nih?",
                "Kalau sudah terasa capek dan lelah, nggak ada salahnya rehat sebentar. Lagi padat kerjaan atau emang kurang tidur?",
            ],
            "istirahat",
            "Lagi capek kerjaan atau kurang tidur nih?",
        ),
        "emotion_bored": (
            [
                "Lagi bosan ya? Kita bisa ngobrol bebas, main tebak kata, aku ceritain sesuatu yang ringan, atau bikin skrip seru. Mau pilih yang mana?",
                "Kalau lagi bosan dan butuh selingan, bilang aja mau aku ceritain sesuatu atau main tebak kata ringan!",
            ],
            "saran_bosan",
            "Mau aku ceritain sesuatu atau main tebak kata?",
        ),
        "emotion_hungry": (
            [
                "Wah, kalau sudah lapar memang susah fokus! Lagi pengin makan atau minum apa nih sekarang?",
                "Jangan ditunda kalau lagi lapar atau haus — sikat dulu makanan ringan atau air hangat biar tenagamu balik!",
            ],
            "minuman",
            "Lagi pengin makan atau minum apa nih?",
        ),
        "emotion_sad": (
            [
                "Aku ikut prihatin dengar kamu lagi merasa sedih. Nggak harus dipendam sendiri — kalau mau cerita pelan-pelan, aku siap dengerin di sini.",
            ],
            "empati",
            "",
        ),
        "emotion_anxious": (
            [
                "Tarik napas pelan dulu ya. Wajar kok sesekali ngerasa cemas atau kesal — kalau mau diurai satu per satu biar lebih ringan, cerita aja.",
            ],
            "empati",
            "",
        ),
        "emotion_confused": (
            [
                "Santai aja, nggak usah buru-buru. Bagian mana yang lagi terasa bikin bingung? Ceritain yang paling kelihatan dulu biar kita urai bareng pelan-pelan.",
                "Kalau masih kerasa pusing atau sulit di awalnya, kita pecah jadi satu pertanyaan kecil dulu ya. Mulai dari bagian mana nih?",
            ],
            "empati",
            "",
        ),
    }
    if act in emotion_templates:
        variants, topic, q = emotion_templates[act]
        return _pick_variant(variants, user_text, history_turns, recent_texts), topic, q

    if cues["is_positive"]:
        variants = [
            "Senang dengernya! Pelan tapi jalan terus itu bikin hasilnya kerasa banget. Ada hal seru apa lagi yang lagi kamu kerjain?",
            "Mantap! Semangat positif kayak gini memang bikin hari terasa jauh lebih ringan. Mau bahas apa lagi nih?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), "positif", ""
    return None


def _compose_topic_or_opinion_turn(
    user_text: str,
    cues: dict[str, Any],
    grounded: list[dict[str, Any]],
    history_turns: int,
    recent_texts: list[str],
) -> tuple[str, str, str] | None:
    norm = cues["normalized_colloquial"]
    tokens = set(re.findall(r"[a-z]+", norm))
    raw_low = user_text.lower()

    if cues["dialogue_act"] == "story_request":
        return _compose_story_reply(user_text, history_turns, recent_texts)

    if "warna" in tokens or bool(tokens & _COLOR_WORDS):
        reply = (
            "Kalau **ACE** paling suka warna biru langit dan ungu lembut — rasanya adem dan tenang di mata! "
            "Kalau kamu sendiri paling suka warna apa?"
        )
        return reply, "warna", "Kalau kamu sendiri paling suka warna apa?"

    if tokens & {"kopi", "teh", "minum", "ngopi"} or ("makan" in tokens and cues["is_question"]):
        reply = (
            "Soal **kopi** atau teh, banyak yang suka ngopi pagi buat cari fokus, tapi sore juga nikmat asal nggak bikin susah tidur. "
            "Kamu sendiri tim kopi atau tim teh nih?"
        )
        return reply, "minuman", "Kamu sendiri tim kopi atau tim teh?"

    if tokens & {"musik", "lagu", "hobi", "nyanyi"}:
        return (
            "Mendengarkan **musik** atau lagu santai memang ampuh banget buat ngembaliin suasana hati! "
            "Kamu lagi sering dengerin genre lagu apa atau lagi menekuni hobi apa akhir-akhir ini?"
        ), "hobi", ""

    if tokens & {"hujan", "angin", "cuaca", "sejuk", "panas", "dingin"}:
        hits = [w for w in ("angin", "sejuk", "hujan", "panas", "dingin", "cuaca") if w in tokens]
        hit_phrase = " ".join(hits[:2]) or "cuaca"
        return (
            f"Suasana dengan {hit_phrase} kayak gini memang bikin pengin jalan lebih pelan dan menikmati momen sebentar. "
            "Kalau di tempatmu sekarang kondisinya lagi enak buat santai atau justru sibuk?"
        ), "cuaca", ""

    if any(p in raw_low for p in ("pendapatmu", "menurutmu", "gimana menurut", "bagaimana pendapat")):
        taught_hint = next((w for w in grounded if w["source"] == "user_taught"), None)
        focus_toks = [t for t in re.findall(r"[a-z]+", raw_low) if t not in STOPWORDS_ID and len(t) >= 4][:2]
        topic_ref = taught_hint["word"] if taught_hint else (" ".join(focus_toks) or "hal itu")
        return (
            f"Kalau menurut **ACE**, topik tentang **{topic_ref}** menarik banget buat dilihat dari pengalaman sehari-hari — "
            "selalu ada detail kecil yang baru terasa kalau dijalani pelan-pelan. Menurutmu sendiri gimana?"
        ), "opini", ""
    return None


_GENERIC_ECHO_SKIP = frozenset({
    "aku", "saya", "kamu", "engkau", "kau", "dia", "ia", "kita", "kami",
    "mereka", "kalian", "lu", "gue", "gw", "ini", "itu", "situ", "sana", "sini",
    "ada", "jadi", "bisa", "mau", "akan", "sudah", "belum", "lagi", "aja", "saja",
    "yah", "ya", "iya", "tidak", "nggak", "gak", "dong", "sih", "deh", "nih",
    "kok", "kan", "banget", "sekali", "halo", "hai", "pagi", "siang", "sore", "malam",
    "kata", "hal", "sesuatu", "cara", "bagian",
})


def _pick_echo_topic(grounded: list[dict[str, Any]], user_text: str) -> str:
    for item in grounded:
        w = item["word"]
        if w not in STOPWORDS_ID and w not in _GENERIC_ECHO_SKIP and item.get("role") != "aktor":
            return w
    raw_toks = [
        t for t in re.findall(r"[a-z]+", user_text.lower())
        if t not in STOPWORDS_ID and t not in _GENERIC_ECHO_SKIP and len(t) >= 3
    ]
    if raw_toks:
        return raw_toks[0]
    fallback = [g["word"] for g in grounded if g["word"] not in _GENERIC_ECHO_SKIP]
    return fallback[0] if fallback else ""


def _compose_open_natural_turn(
    user_text: str,
    cues: dict[str, Any],
    grounded: list[dict[str, Any]],
    profile: dict[str, Any],
    mode_label: str,
    history_turns: int,
    recent_texts: list[str],
    stage_id: int,
) -> tuple[str, str, str]:
    taught_hits = [w for w in grounded if w["source"] == "user_taught"]
    if taught_hits:
        w = taught_hits[0]
        return (
            f"Aku masih ingat kata **{w['word']}** (*{w['meaning_id']}*) yang kamu ajarkan! "
            f"Cerita tentang {w['word']} itu memang kebayang suasananya — ada lagi yang ingin kamu ceritakan?"
        ), w["word"], ""

    echo_word = _pick_echo_topic(grounded, user_text)
    if cues["mentions_speech"]:
        stage_label = f"Tahap `{stage_id}/4`"
        reply = (
            f"Kemampuan bicara **ACE** sekarang ada di {stage_label} dengan **{profile['vocab_count']} kata** tersimpan. "
            "Kamu bisa langsung ajak ngobrol santai atau ajarin kata baru kapan saja!"
        )
        return reply, "bahasa", ""

    if cues["is_question"]:
        ref = f"soal **{echo_word}**" if echo_word else "hal itu"
        variants = [
            f"Pertanyaan menarik {ref}! Dari sudut pandang **ACE** di mode **{mode_label}**, bagian paling serunya ada di konteks nyata yang lagi kita bahas — menurut kamu gimana?",
            f"Wah, kalau membahas {ref}, ada beberapa sisi yang bisa dilihat bareng. Kamu sendiri lagi kepikiran bagian mananya nih?",
        ]
        return _pick_variant(variants, user_text, history_turns, recent_texts), echo_word or "diskusi", ""

    ref_clause = f"tentang **{echo_word}**" if echo_word else "yang barusan kamu sampaikan"
    variants = [
        f"Wah, menarik juga ya cerita {ref_clause}! Boleh ceritain lebih lanjut maksud atau kejadiannya?",
        f"Oke, kebayang sih maksudmu {ref_clause}. Terus habis itu atau menurutmu sendiri gimana?",
        f"Menarik dibahas nih {ref_clause}. Kalau versi kamu, bagian paling berkesannya yang mana?",
    ]
    return _pick_variant(variants, user_text, history_turns, recent_texts), echo_word or "obrolan_ringan", ""


def realize_indonesian_turn(
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
    conversation_context: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
    stage_id: int = 4,
) -> dict[str, Any]:
    """Compose a warm, context-aware Indonesian dialogue turn plus next topic metadata."""
    last_topic = _extract_last_topic(conversation_context, recent_messages)
    hit = (
        _compose_followup_turn(user_text, cues, last_topic, history_turns, recent_assistant_texts)
        or _compose_greeting_identity_turn(cues, user_text, mode_label, history_turns, recent_assistant_texts, stage_id)
        or _compose_emotion_or_humor_turn(cues, user_text, history_turns, recent_assistant_texts)
        or _compose_topic_or_opinion_turn(user_text, cues, grounded, history_turns, recent_assistant_texts)
        or _compose_open_natural_turn(user_text, cues, grounded, profile, mode_label, history_turns, recent_assistant_texts, stage_id)
    )
    main_text, next_topic, bot_question = hit
    parts: list[str] = [main_text]

    taught_hits = [w for w in grounded if w["source"] == "user_taught"]
    if len(taught_hits) >= 2:
        w1, w2 = taught_hits[0], taught_hits[1]
        parts.append(
            f"Aku juga ingat **`{w1['word']}`** (*{w1['meaning_id']}*) dan **`{w2['word']}`** (*{w2['meaning_id']}*) dari ajaranmu."
        )
    elif taught_hits and taught_hits[0]["word"] not in main_text.lower():
        w = taught_hits[0]
        parts.append(f"Aku juga ingat kata **`{w['word']}`** (*{w['meaning_id']}*) yang kamu ajarkan.")

    show_task = bool(
        latest_task
        and (latest_task.get("status") != "COMPLETED" or latest_task.get("kind") != "learning_task")
        and not cues["is_greeting"]
        and not cues["asks_wellbeing"]
        and cues["dialogue_act"] in {"general", "preference_question"}
    )
    if show_task and latest_task:
        parts.append(f"Info tambahan: tugas terakhirmu (**{latest_task['title_id']}**) berstatus `{latest_task['status']}`.")

    if stage_id == 0 and ((history_turns <= 0 and cues["is_greeting"]) or cues["mentions_speech"]):
        parts.append("Kalau ingin aku berlatih mulai dari tahap bayi, kirim *\"latih tahap 1\"* atau *\"belajar berbicara\"*.")
    elif curious_word:
        syls = "-".join(curious_word["syllables"])
        parts.append(f"Ngomong-ngomong, aku belum mengenal makna kata **`{curious_word['word']}`** (`{syls}`) — artinya apa menurutmu?")

    return {"clauses": parts, "next_topic": next_topic, "bot_question": bot_question}


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
    conversation_context: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
    stage_id: int = 4,
) -> list[str]:
    """Compose context-sensitive, grounded, anti-repetitive Indonesian reply clauses."""
    return realize_indonesian_turn(
        user_text=user_text,
        cues=cues,
        grounded=grounded,
        profile=profile,
        mode_label=mode_label,
        latest_task=latest_task,
        recent_assistant_texts=recent_assistant_texts,
        history_turns=history_turns,
        curious_word=curious_word,
        conversation_context=conversation_context,
        recent_messages=recent_messages,
        stage_id=stage_id,
    )["clauses"]


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
    "realize_indonesian_turn",
]
