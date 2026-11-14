"""Indonesian Morphological Analyzer, Nazief-Adriani Stemmer, and Colloquial Normalizer (`ace_indo_nlp.morphology`)."""
from __future__ import annotations

import re
from typing import Any

COLLOQUIAL_SLANG_MAP: dict[str, str] = {
    "ak": "aku",
    "aq": "aku",
    "gw": "aku",
    "gue": "aku",
    "w": "aku",
    "sy": "saya",
    "sya": "saya",
    "kmu": "kamu",
    "km": "kamu",
    "lu": "kamu",
    "lo": "kamu",
    "loe": "kamu",
    "yg": "yang",
    "dgn": "dengan",
    "dg": "dengan",
    "sm": "sama",
    "utk": "untuk",
    "dr": "dari",
    "kpd": "kepada",
    "pd": "pada",
    "dlm": "dalam",
    "tp": "tapi",
    "ttg": "tentang",
    "jg": "juga",
    "aj": "saja",
    "aja": "saja",
    "doang": "saja",
    "bgt": "sangat",
    "skli": "sekali",
    "bener": "benar",
    "bnr": "benar",
    "emg": "memang",
    "emang": "memang",
    "kyk": "seperti",
    "kayak": "seperti",
    "spt": "seperti",
    "org": "orang",
    "skrg": "sekarang",
    "bsk": "besok",
    "kmrn": "kemarin",
    "td": "tadi",
    "nti": "nanti",
    "ntr": "nanti",
    "lg": "lagi",
    "sdh": "sudah",
    "udh": "sudah",
    "udah": "sudah",
    "blm": "belum",
    "belom": "belum",
    "ga": "tidak",
    "gak": "tidak",
    "gk": "tidak",
    "g": "tidak",
    "tdk": "tidak",
    "ngga": "tidak",
    "nggak": "tidak",
    "kagak": "tidak",
    "tak": "tidak",
    "bkn": "bukan",
    "blh": "boleh",
    "hrs": "harus",
    "bs": "bisa",
    "dpt": "dapat",
    "mo": "mau",
    "pengen": "ingin",
    "pgn": "ingin",
    "mgkn": "mungkin",
    "tau": "tahu",
    "tw": "tahu",
    "ngerti": "paham",
    "pahamin": "pahami",
    "blg": "kata",
    "bilang": "kata",
    "ngomong": "bicara",
    "bcara": "bicara",
    "omong": "bicara",
    "ngobrol": "bicara",
    "dgr": "dengar",
    "denger": "dengar",
    "dengerin": "dengar",
    "liat": "lihat",
    "lht": "lihat",
    "ngeliat": "lihat",
    "bljr": "belajar",
    "belajr": "belajar",
    "tgs": "tugas",
    "mksd": "maksud",
    "mksud": "maksud",
    "gmn": "bagaimana",
    "gmna": "bagaimana",
    "gimana": "bagaimana",
    "knp": "kenapa",
    "napa": "kenapa",
    "kpn": "kapan",
    "dmn": "dimana",
    "kmn": "kemana",
    "krn": "karena",
    "bbrp": "beberapa",
    "jd": "jadi",
    "jdi": "jadi",
    "bkin": "buat",
    "bikin": "buat",
    "bikinin": "buatkan",
    "jelasin": "jelaskan",
    "ajarin": "ajarkan",
    "artiin": "artikan",
    "ceritain": "ceritakan",
    "bantuin": "bantu",
    "tanyain": "tanya",
    "ingetin": "ingat",
    "ingatin": "ingat",
    "kerjain": "kerjakan",
    "mksh": "terima",
    "makasih": "terima",
    "mksih": "terima",
    "trims": "terima",
    "thx": "terima",
    "thanks": "terima",
    "maap": "maaf",
    "tlg": "tolong",
    "plis": "tolong",
    "kasi": "beri",
    "kasih": "beri",
    "pke": "pakai",
    "pake": "pakai",
    "jgn": "jangan",
    "kl": "kalau",
    "klo": "kalau",
    "kalo": "kalau",
    "btul": "betul",
    "sbr": "sabar",
    "smngt": "semangat",
    "smg": "semoga",
    "slmt": "selamat",
    "kbr": "kabar",
    "cape": "capek",
    "bosen": "bosan",
    "seneng": "senang",
    "binggung": "bingung",
    "laper": "lapar",
    "ngantuk": "mengantuk",
    "gabut": "bosan",
    "mikir": "pikir",
}

_NON_SPLITTING_REDUPS = frozenset({"kupu", "kura", "laba", "lumba", "cumicumi", "cumi", "paru", "ubur"})

_LAUGH_RE = re.compile(r"^(?:wk+|wkwk(?:wk)*|ha(?:ha)+h?|he(?:he)+h?|hi(?:hi)+h?|xi(?:xi)+|hu(?:hu)+)$")


def is_laughter_token(token: str) -> bool:
    """Return True when an Indonesian token represents chat laughter (wkwk, haha, hehe)."""
    clean = re.sub(r"[^a-z]", "", str(token or "").lower())
    return bool(clean and _LAUGH_RE.match(clean))


def bounded_edit_distance(a: str, b: str) -> int:
    """Compute bounded Levenshtein edit distance (returns 99 if length diff exceeds 3)."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 3:
        return 99
    prev = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        cur = [i]
        for j, ch_b in enumerate(b, start=1):
            cost = 0 if ch_a == ch_b else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def normalize_colloquial(text: str) -> tuple[str, dict[str, str]]:
    """Normalize Indonesian slang/chat abbreviations cleanly while tracking applied rewrites."""
    tokens = re.findall(r"[a-zA-Z0-9'-]+", str(text or ""))
    out_tokens: list[str] = []
    rewrites: dict[str, str] = {}
    for tok in tokens:
        low = tok.lower()
        if is_laughter_token(low):
            if low != "haha":
                rewrites[low] = "haha"
            out_tokens.append("haha")
            continue
        mapped = COLLOQUIAL_SLANG_MAP.get(low, low)
        if mapped != low:
            rewrites[low] = mapped
        out_tokens.append(mapped)
    return " ".join(out_tokens), rewrites


def _strip_particles_and_possessives(word: str) -> tuple[str, list[str]]:
    clitics: list[str] = []
    cur = word
    for part in ("lah", "kah", "tah", "pun"):
        if cur.endswith(part) and len(cur) > len(part) + 2:
            clitics.append(part)
            cur = cur[: -len(part)]
            break
    for poss in ("ku", "mu", "nya"):
        if cur.endswith(poss) and len(cur) > len(poss) + 2:
            clitics.append(poss)
            cur = cur[: -len(poss)]
            break
    return cur, clitics


def _expand_inner_prefixes(
    outer_pref: str,
    rem: str,
    inner_candidates: tuple[tuple[str, tuple[str, ...]], ...],
) -> list[tuple[str, list[str]]]:
    extra: list[tuple[str, list[str]]] = []
    for inner_pref, inner_restores in inner_candidates:
        if not (rem.startswith(inner_pref) and len(rem) > len(inner_pref) + 2):
            continue
        inner_rem = rem[len(inner_pref) :]
        for rep in inner_restores:
            extra.append((rep + inner_rem, [outer_pref, inner_pref]))
    return extra


def _expand_prefix_rules(base: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = [(base, [])]
    pref_rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("menge", ("",)),
        ("meng", ("", "k")),
        ("meny", ("s", "")),
        ("men", ("", "t")),
        ("mem", ("", "p")),
        ("me", ("",)),
        ("peng", ("", "k")),
        ("peny", ("s", "")),
        ("pen", ("", "t")),
        ("pem", ("", "p")),
        ("pel", ("",)),
        ("pe", ("",)),
        ("bel", ("",)),
        ("ber", ("",)),
        ("ter", ("",)),
        ("per", ("",)),
        ("di", ("",)),
        ("ke", ("",)),
        ("se", ("",)),
        ("nge", ("",)),
        ("ng", ("", "k")),
        ("ny", ("s", "c")),
        ("n", ("", "t")),
        ("m", ("p",)),
    )
    inner_candidates = pref_rules[:12] + (("per", ("",)), ("ke", ("",)), ("ber", ("",)), ("bel", ("",)))
    for pref, restores in pref_rules:
        if not (base.startswith(pref) and len(base) > len(pref) + 2):
            continue
        rem = base[len(pref) :]
        for rep in restores:
            out.append((rep + rem, [pref]))
        if pref in {"di", "ter", "ke", "ber", "se", "mem", "men", "meng", "peny", "pem", "pen", "peng"}:
            out.extend(_expand_inner_prefixes(pref, rem, inner_candidates))
    return out


def _expand_suffix_rules(stem: str) -> list[tuple[str, list[str]]]:
    variants: list[tuple[str, list[str]]] = [(stem, [])]
    for suf in ("kan", "an", "in", "i"):
        if stem.endswith(suf) and len(stem) > len(suf) + 2:
            variants.append((stem[: -len(suf)], [suf]))
    return variants


def stem_candidates(word: str) -> list[str]:
    """Generate ordered Indonesian root stem candidates for morphological lookup."""
    info = analyze_morphology(word)
    return list(info["candidates"])


def analyze_morphology(raw_word: str, *, known_roots: set[str] | frozenset[str] | None = None) -> dict[str, Any]:
    """Perform Nazief-Adriani-inspired morphological decomposition on an Indonesian token."""
    raw_low = str(raw_word or "").strip().lower()
    is_redup = False
    clean = re.sub(r"[^a-z]", "", raw_low)
    if "-" in raw_low:
        parts = [re.sub(r"[^a-z]", "", p) for p in raw_low.split("-") if re.sub(r"[^a-z]", "", p)]
        if len(parts) == 2 and parts[0] and parts[0] not in _NON_SPLITTING_REDUPS:
            is_redup = True
            clean = parts[1] if parts[0] != parts[1] and len(parts[1]) < len(parts[0]) else parts[0]

    if not clean:
        return {"surface": raw_low, "root": "", "candidates": [], "prefixes": [], "suffixes": [], "clitics": [], "is_reduplicated": is_redup, "affix_pos_hint": ""}

    mapped = COLLOQUIAL_SLANG_MAP.get(clean, clean)
    core, clitics = _strip_particles_and_possessives(mapped)

    raw_cands: list[tuple[str, list[str], list[str]]] = []
    for base_variant in (mapped, core):
        for p_stem, prefs in _expand_prefix_rules(base_variant):
            for s_stem, sufs in _expand_suffix_rules(p_stem):
                raw_cands.append((s_stem, prefs, sufs))

    seen: set[str] = set()
    ordered_cands: list[str] = []
    meta_by_cand: dict[str, tuple[list[str], list[str]]] = {}
    for cand, prefs, sufs in raw_cands:
        if len(cand) < 2 or cand in seen:
            continue
        seen.add(cand)
        ordered_cands.append(cand)
        meta_by_cand[cand] = (prefs, sufs)

    chosen_root = ordered_cands[0] if ordered_cands else mapped
    if known_roots:
        matched = [c for c in ordered_cands if c in known_roots]
        if matched:
            chosen_root = min(matched, key=lambda w: (len(meta_by_cand[w][0]) + len(meta_by_cand[w][1]) == 0 and w != clean, len(w)))
            if mapped in known_roots:
                chosen_root = mapped

    prefs_out, sufs_out = meta_by_cand.get(chosen_root, ([], []))
    pos_hint = _infer_pos_from_affixes(prefs_out, sufs_out)
    return {
        "surface": raw_low,
        "root": chosen_root,
        "candidates": ordered_cands,
        "prefixes": prefs_out,
        "suffixes": sufs_out,
        "clitics": clitics,
        "is_reduplicated": is_redup,
        "affix_pos_hint": pos_hint,
    }


def _infer_pos_from_affixes(prefixes: list[str], suffixes: list[str]) -> str:
    if any(p in {"me", "mem", "men", "meng", "meny", "menge", "di", "ber", "be", "bel"} for p in prefixes):
        return "aksi"
    if "ke" in prefixes and "an" in suffixes:
        return "objek"
    if any(p in {"pe", "pem", "pen", "peng", "peny"} for p in prefixes):
        return "objek"
    if "ter" in prefixes:
        return "sifat"
    return ""


def stem_word(word: str, *, known_roots: set[str] | frozenset[str] | None = None) -> str:
    """Return best root stem for an Indonesian word using optional lexicon grounding."""
    return str(analyze_morphology(word, known_roots=known_roots)["root"])
