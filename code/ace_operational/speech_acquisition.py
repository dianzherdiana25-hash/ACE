"""Four-Stage Developmental Indonesian Speech Acquisition & Persistent Lexicon Engine.

Backed by the pure-Python ``ace_indo_nlp`` Indonesian Computational Linguistics
Library (phonotactics, Nazief-Adriani morphology, colloquial normalization,
curated semantic lexicon KB, pragmatic discourse & realization):
  1. Stage 1 (``babbling_phonotactics``): Indonesian phoneme inventory, digraph-aware
     syllabification, prosody cadence marks, constrained vocalization/babbling,
     and phonotactic well-formedness validation.
  2. Stage 2 (``holophrase_lexicon``): Grounded 190+ word Indonesian lexicon +
     passive exposure memory persisted in SQLite inside ``OperationalStore``,
     morphological/slang/typo lookup, curiosity about unfamiliar words,
     anaphoric follow-ups, corrective revisions, and authentic example carry-over.
  3. Stage 3 (``telegraphic_phrases``): Context- and domain-scored compositional
     2-3 word phrase grammar across 17 grammatical patterns over learned lexicon.
  4. Stage 4 (``contextual_utterance``): Intent-, mood-, and domain-aware
     Indonesian dialogue & lexicon Q&A (meaning, synonym, antonym, morphology)
     plus Stage-4 GGUF conditioning, gated by an anti-hallucination verifier.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ace_indo_nlp.discourse import (
    analyze_discourse_cues,
    extract_meaning_query,
    extract_query_target,
    format_lexicon_qa_clauses,
    parse_teaching_or_correction,
    realize_indonesian_clauses,
    realize_indonesian_turn,
)
from ace_indo_nlp.lexicon_kb import (
    CORE_INDONESIAN_LEXICON,
    NON_TEACHABLE_WORDS_ID,
    QUESTION_WORDS_ID,
    SEMANTIC_RELATIONS,
    STOPWORDS_ID,
    TELEGRAPHIC_PATTERNS,
    VALID_POS_ROLES,
    infer_indonesian_pos,
)
from ace_indo_nlp.morphology import (
    COLLOQUIAL_SLANG_MAP,
    analyze_morphology,
    bounded_edit_distance,
    is_laughter_token,
    normalize_colloquial,
    stem_candidates,
)
from ace_indo_nlp.phonotactics import (
    CONSONANTS,
    DIGRAPHS,
    VALID_CODA_CLUSTERS,
    VALID_ONSET_CLUSTERS,
    VOWELS,
    echo_input_syllables,
    syllabify_indonesian,
    synthesize_babble,
    tokenize_phonemes,
)

from .store import OperationalStore, utc_now_iso

SPEECH_STAGE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "stage_id": 1,
        "stage_name": "babbling_phonotactics",
        "title_id": "Tahap 1: Vokalisasi, Fonem & Suku Kata Indonesia",
    },
    {
        "stage_id": 2,
        "stage_name": "holophrase_lexicon",
        "title_id": "Tahap 2: Kata Pertama, Makna & Leksikon Persisten",
    },
    {
        "stage_id": 3,
        "stage_name": "telegraphic_phrases",
        "title_id": "Tahap 3: Kombinasi 2-3 Kata Telegrafik",
    },
    {
        "stage_id": 4,
        "stage_name": "contextual_utterance",
        "title_id": "Tahap 4: Komposisi Kalimat & Ujaran Kontekstual",
    },
)

VALID_ROLES = VALID_POS_ROLES
COMMON_SPEECH_TYPOS = COLLOQUIAL_SLANG_MAP
_STOPWORDS_AND_META_ID = STOPWORDS_ID
_NON_TEACHABLE_WORDS = NON_TEACHABLE_WORDS_ID
_QUESTION_WORDS = QUESTION_WORDS_ID

# Compatibility 5-tuple view preserved for downstream code & existing tests
CORE_SEED_LEXICON: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = tuple(
    (word, role, meaning_id, domains, example)
    for word, role, meaning_id, domains, example, _syns, _ants in CORE_INDONESIAN_LEXICON
)


def _bounded_edit_distance(a: str, b: str) -> int:
    return bounded_edit_distance(a, b)


def _stem_candidates(word: str) -> list[str]:
    return stem_candidates(word)


def _infer_word_role(word: str, meaning_id: str, explicit_role: str = "") -> str:
    return infer_indonesian_pos(word, meaning_id, explicit_role=explicit_role)


def _parse_teach_word_directive(raw_text: str, *, pending_word: str = "") -> dict[str, Any] | None:
    return parse_teaching_or_correction(raw_text, pending_word=pending_word)


def _extract_meaning_query_word(user_text: str) -> str | None:
    return extract_meaning_query(user_text)


def validate_telegraphic_phrase(tokens_with_roles: list[tuple[str, str]]) -> dict[str, Any]:
    """Validate grammatical role ordering and coherence for a Stage-3 2-3 word phrase."""
    if not 2 <= len(tokens_with_roles) <= 3:
        return {"valid": False, "reason": "jumlah_kata_bukan_2_sampai_3", "phrase": ""}
    words = [str(w).strip().lower() for w, _ in tokens_with_roles]
    roles = tuple(str(r).strip().lower() for _, r in tokens_with_roles)
    if any(not w for w in words) or len(set(words)) != len(words):
        return {"valid": False, "reason": "duplikasi_atau_kata_kosong", "phrase": " ".join(words)}
    if roles not in TELEGRAPHIC_PATTERNS:
        return {"valid": False, "reason": f"pola_peran_tidak_valid:{roles}", "phrase": " ".join(words)}
    return {"valid": True, "pattern": "+".join(roles), "phrase": " ".join(words), "reason": "valid"}


def _parse_target_speech_stage(lower: str) -> int | str | None:
    stage_aliases: tuple[tuple[int | str, tuple[str, ...]], ...] = (
        (1, ("tahap 1", "tahap satu", "tahap bayi", "tahap pertama", "babbling")),
        (2, ("tahap 2", "tahap dua", "tahap kedua", "holofrasis", "kata pertama")),
        (3, ("tahap 3", "tahap tiga", "tahap ketiga", "telegrafik", "frasa telegrafik")),
        (4, ("tahap 4", "tahap empat", "tahap keempat", "kontekstual")),
        ("next", ("tahap berikutnya", "tahap selanjutnya", "naik tahap", "lanjut tahap", "lanjut ke tahap")),
    )
    for target, cues in stage_aliases:
        if any(cue in lower for cue in cues):
            return target
    if any(cue in lower for cue in ("coba skill berbicara", "latih skill berbicara", "kurikulum berbicara", "semua tahap")):
        return "all"
    return None


def classify_speech_intent(
    raw_text: str,
    normalized_text: str,
    constraints: list[str],
    offline_requested: bool,
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Classify Indonesian speech-teaching, anaphora, corrections, training, or status queries."""
    colloquial_norm, _ = normalize_colloquial(normalized_text)
    lower = f"{normalized_text.lower()} {colloquial_norm}"
    is_code_request = any(
        w in lower
        for w in ("buatkan aplikasi", "buat program", "buat skrip", "buatkan script", "script python", "kode python")
    )
    if is_code_request:
        return None

    pending_word = str((conversation_context or {}).get("pending_curiosity_word", "")).strip()
    taught = (
        parse_teaching_or_correction(raw_text, pending_word=pending_word)
        or parse_teaching_or_correction(normalized_text, pending_word=pending_word)
    )
    if taught is not None:
        return {
            "intent": "TEACH_WORD",
            "taught_word": taught,
            "normalized_text": normalized_text,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }

    q_target = extract_query_target(raw_text, pending_word=pending_word)
    if q_target and not any(k in lower for k in ("perkembangan", "status", "daftar")):
        return None

    status_cues = (
        "tahap bicara", "tahap berbicara", "status bicara", "status berbicara",
        "perkembangan bicara", "perkembangan berbicara", "kosakata kamu",
        "berapa kata yang kamu tahu", "daftar kosakata", "kemampuan berbicara",
    )
    stage_target = _parse_target_speech_stage(lower)
    explicit_train_cues = (
        "belajar berbicara", "belajar bicara", "latih berbicara", "latih bicara",
        "latihan berbicara", "latihan bicara", "coba skill berbicara", "mulai skill berbicara",
        "skill berbicara", "kurikulum berbicara", "tingkatkan kemampuan berbicara", "belajar bicara",
        "mulai dari tahap", "naik ke tahap", "latih tahap", "tes bicara", "latih skill bicara",
    )
    is_status_query = (
        any(cue in lower for cue in status_cues)
        and stage_target is None
        and not any(t in lower for t in ("coba skill berbicara", "belajar berbicara", "latih berbicara"))
        and not ("menurutmu" in lower and "tentang" in lower)
    )
    if is_status_query:
        return {
            "intent": "SPEECH_STATUS",
            "normalized_text": normalized_text,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    is_philosophical_q = (
        any(q in lower for q in ("kenapa", "mengapa", "menurutmu", "apa manfaat"))
        and stage_target is None
        and not any(cmd in lower for cmd in ("latih", "coba", "mulai", "naik", "lanjut"))
    )
    if not is_philosophical_q and (stage_target is not None or any(cue in lower for cue in explicit_train_cues)):
        return {
            "intent": "TRAIN_SPEECH",
            "target_stage": stage_target if stage_target is not None else "all",
            "normalized_text": normalized_text,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": True,
        }
    return None


class SpeechDevelopmentEngine:
    """SQLite-persisted 4-stage developmental Indonesian speech engine."""

    def __init__(self, store: OperationalStore) -> None:
        self.store = store
        self._init_tables()

    def _migrate_lexicon_columns(self) -> None:
        existing_cols = {
            row["name"]
            for row in self.store._conn.execute("PRAGMA table_info(speech_lexicon)").fetchall()
        }
        additions = (
            ("domains_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("synonyms_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("antonyms_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("revision_count", "INTEGER NOT NULL DEFAULT 0"),
        )
        for col_name, col_def in additions:
            if col_name not in existing_cols:
                self.store._conn.execute(f"ALTER TABLE speech_lexicon ADD COLUMN {col_name} {col_def}")

    def _init_tables(self) -> None:
        with self.store._lock:
            self.store._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speech_stage_state (
                    stage_id INTEGER PRIMARY KEY,
                    stage_name TEXT NOT NULL,
                    title_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exam_score REAL NOT NULL DEFAULT 0.0,
                    passed_cases INTEGER NOT NULL DEFAULT 0,
                    total_cases INTEGER NOT NULL DEFAULT 0,
                    receipt_id TEXT NOT NULL DEFAULT '',
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )
            self.store._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speech_lexicon (
                    word TEXT PRIMARY KEY,
                    syllables_json TEXT NOT NULL,
                    role TEXT NOT NULL,
                    meaning_id TEXT NOT NULL,
                    contexts_json TEXT NOT NULL,
                    examples_json TEXT NOT NULL,
                    domains_json TEXT NOT NULL DEFAULT '[]',
                    synonyms_json TEXT NOT NULL DEFAULT '[]',
                    antonyms_json TEXT NOT NULL DEFAULT '[]',
                    revision_count INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL,
                    mastery REAL NOT NULL DEFAULT 0.5,
                    exposure_count INTEGER NOT NULL DEFAULT 1,
                    taught_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._migrate_lexicon_columns()
            self.store._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speech_heard_words (
                    word TEXT PRIMARY KEY,
                    syllables_json TEXT NOT NULL,
                    exposure_count INTEGER NOT NULL DEFAULT 1,
                    sample_context TEXT NOT NULL DEFAULT '',
                    grounded INTEGER NOT NULL DEFAULT 0,
                    last_heard_at TEXT NOT NULL
                )
                """
            )
            self.store._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speech_utterances (
                    utterance_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    stage_id INTEGER NOT NULL,
                    intent TEXT NOT NULL,
                    utterance_text TEXT NOT NULL,
                    grounding_json TEXT NOT NULL,
                    verification_score REAL NOT NULL,
                    passed INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            now = utc_now_iso()
            for spec in SPEECH_STAGE_SPECS:
                self.store._conn.execute(
                    """
                    INSERT OR IGNORE INTO speech_stage_state(
                        stage_id, stage_name, title_id, status, updated_at
                    ) VALUES (?, ?, ?, 'LOCKED', ?)
                    """,
                    (spec["stage_id"], spec["stage_name"], spec["title_id"], now),
                )
            self.store._conn.commit()

    def _save_stage_result(
        self,
        *,
        stage_id: int,
        passed: bool,
        passed_cases: int,
        total_cases: int,
        receipt_id: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        status = "PASSED" if passed else "FAILED"
        score = round(passed_cases / max(1, total_cases), 4)
        now = utc_now_iso()
        with self.store._lock:
            self.store._conn.execute(
                """
                UPDATE speech_stage_state SET
                    status = ?,
                    exam_score = ?,
                    passed_cases = ?,
                    total_cases = ?,
                    receipt_id = ?,
                    evidence_json = ?,
                    updated_at = ?
                WHERE stage_id = ?
                """,
                (status, score, passed_cases, total_cases, receipt_id, json.dumps(evidence, ensure_ascii=False), now, stage_id),
            )
            self.store._conn.commit()
        return {
            "stage_id": stage_id,
            "status": status,
            "score": score,
            "passed": passed,
            "passed_cases": passed_cases,
            "total_cases": total_cases,
            "receipt_id": receipt_id,
            "evidence": evidence,
        }

    def _upsert_lexicon_word(
        self,
        *,
        word: str,
        syllables: list[str],
        role: str,
        meaning_id: str,
        contexts: list[str],
        examples: list[str],
        domains: list[str] | None = None,
        synonyms: list[str] | None = None,
        antonyms: list[str] | None = None,
        is_correction: bool = False,
        source: str,
        mastery: float,
        note: str = "",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        doms = domains if domains is not None else contexts
        syns = synonyms or []
        ants = antonyms or []
        rev_inc = 1 if is_correction else 0
        with self.store._lock:
            self.store._conn.execute(
                """
                INSERT INTO speech_lexicon(
                    word, syllables_json, role, meaning_id, contexts_json, examples_json,
                    domains_json, synonyms_json, antonyms_json, revision_count,
                    source, mastery, exposure_count, taught_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    syllables_json = excluded.syllables_json,
                    role = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.role ELSE excluded.role END,
                    meaning_id = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.meaning_id ELSE excluded.meaning_id END,
                    contexts_json = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.contexts_json ELSE excluded.contexts_json END,
                    examples_json = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.examples_json ELSE excluded.examples_json END,
                    domains_json = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.domains_json ELSE excluded.domains_json END,
                    synonyms_json = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.synonyms_json ELSE excluded.synonyms_json END,
                    antonyms_json = CASE WHEN speech_lexicon.source = 'user_taught' AND excluded.source != 'user_taught' THEN speech_lexicon.antonyms_json ELSE excluded.antonyms_json END,
                    revision_count = speech_lexicon.revision_count + excluded.revision_count,
                    source = CASE WHEN speech_lexicon.source = 'user_taught' THEN 'user_taught' ELSE excluded.source END,
                    mastery = MAX(speech_lexicon.mastery, excluded.mastery),
                    exposure_count = speech_lexicon.exposure_count + 1,
                    taught_note = CASE WHEN excluded.taught_note != '' THEN excluded.taught_note ELSE speech_lexicon.taught_note END,
                    updated_at = excluded.updated_at
                """,
                (
                    word,
                    json.dumps(syllables, ensure_ascii=False),
                    role,
                    meaning_id,
                    json.dumps(contexts, ensure_ascii=False),
                    json.dumps(examples, ensure_ascii=False),
                    json.dumps(doms, ensure_ascii=False),
                    json.dumps(syns, ensure_ascii=False),
                    json.dumps(ants, ensure_ascii=False),
                    rev_inc,
                    source,
                    float(mastery),
                    note,
                    now,
                    now,
                ),
            )
            self.store._conn.execute("UPDATE speech_heard_words SET grounded = 1 WHERE word = ?", (word,))
            self.store._conn.commit()
            row = self.store._conn.execute("SELECT * FROM speech_lexicon WHERE word = ?", (word,)).fetchone()
            return self._row_to_lexicon(row)

    def _batch_upsert_curriculum_lexicon(self) -> int:
        now = utc_now_iso()
        rows_to_insert: list[tuple[Any, ...]] = []
        for word, role, meaning, domains, example, syns, ants in CORE_INDONESIAN_LEXICON:
            syll = syllabify_indonesian(word)
            if not syll["pronounceable"]:
                continue
            rows_to_insert.append(
                (
                    word,
                    json.dumps(syll["syllables"], ensure_ascii=False),
                    role,
                    meaning,
                    json.dumps(list(domains), ensure_ascii=False),
                    json.dumps([example], ensure_ascii=False),
                    json.dumps(list(domains), ensure_ascii=False),
                    json.dumps(list(syns), ensure_ascii=False),
                    json.dumps(list(ants), ensure_ascii=False),
                    "curriculum",
                    0.75,
                    "",
                    now,
                    now,
                )
            )
        with self.store._lock:
            self.store._conn.executemany(
                """
                INSERT INTO speech_lexicon(
                    word, syllables_json, role, meaning_id, contexts_json, examples_json,
                    domains_json, synonyms_json, antonyms_json, revision_count,
                    source, mastery, exposure_count, taught_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    syllables_json = excluded.syllables_json,
                    role = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.role ELSE excluded.role END,
                    meaning_id = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.meaning_id ELSE excluded.meaning_id END,
                    contexts_json = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.contexts_json ELSE excluded.contexts_json END,
                    examples_json = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.examples_json ELSE excluded.examples_json END,
                    domains_json = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.domains_json ELSE excluded.domains_json END,
                    synonyms_json = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.synonyms_json ELSE excluded.synonyms_json END,
                    antonyms_json = CASE WHEN speech_lexicon.source = 'user_taught' THEN speech_lexicon.antonyms_json ELSE excluded.antonyms_json END,
                    source = CASE WHEN speech_lexicon.source = 'user_taught' THEN 'user_taught' ELSE excluded.source END,
                    mastery = MAX(speech_lexicon.mastery, excluded.mastery),
                    exposure_count = speech_lexicon.exposure_count + 1,
                    updated_at = excluded.updated_at
                """,
                rows_to_insert,
            )
            self.store._conn.commit()
        return len(rows_to_insert)

    @staticmethod
    def _row_to_lexicon(row: Any) -> dict[str, Any]:
        keys = set(row.keys())
        return {
            "word": row["word"],
            "syllables": json.loads(row["syllables_json"] or "[]"),
            "role": row["role"],
            "meaning_id": row["meaning_id"],
            "contexts": json.loads(row["contexts_json"] or "[]"),
            "examples": json.loads(row["examples_json"] or "[]"),
            "domains": json.loads(row["domains_json"] or "[]") if "domains_json" in keys else json.loads(row["contexts_json"] or "[]"),
            "synonyms": json.loads(row["synonyms_json"] or "[]") if "synonyms_json" in keys else [],
            "antonyms": json.loads(row["antonyms_json"] or "[]") if "antonyms_json" in keys else [],
            "revision_count": int(row["revision_count"] or 0) if "revision_count" in keys else 0,
            "source": row["source"],
            "mastery": float(row["mastery"]),
            "exposure_count": int(row["exposure_count"]),
            "taught_note": row["taught_note"],
        }

    def list_lexicon(self, *, source: str | None = None) -> list[dict[str, Any]]:
        """List persisted lexicon entries from SQLite."""
        with self.store._lock:
            if source:
                rows = self.store._conn.execute(
                    "SELECT * FROM speech_lexicon WHERE source = ? ORDER BY updated_at DESC, word ASC",
                    (source,),
                ).fetchall()
            else:
                rows = self.store._conn.execute("SELECT * FROM speech_lexicon ORDER BY role ASC, word ASC").fetchall()
            return [self._row_to_lexicon(r) for r in rows]

    def list_heard_words(self, *, ungrounded_only: bool = True, limit: int = 12) -> list[dict[str, Any]]:
        """List passively heard Indonesian words persisted in SQLite."""
        with self.store._lock:
            query = (
                "SELECT * FROM speech_heard_words WHERE grounded = 0 "
                "ORDER BY exposure_count DESC, last_heard_at DESC, rowid DESC LIMIT ?"
                if ungrounded_only
                else "SELECT * FROM speech_heard_words ORDER BY exposure_count DESC, last_heard_at DESC, rowid DESC LIMIT ?"
            )
            rows = self.store._conn.execute(query, (int(limit),)).fetchall()
            return [
                {
                    "word": r["word"],
                    "syllables": json.loads(r["syllables_json"] or "[]"),
                    "exposure_count": int(r["exposure_count"]),
                    "sample_context": r["sample_context"],
                    "grounded": bool(r["grounded"]),
                    "last_heard_at": r["last_heard_at"],
                }
                for r in rows
            ]

    def observe_user_utterance(self, text: str) -> dict[str, Any]:
        """Passively record valid unfamiliar content words heard during conversation."""
        tokens = re.findall(r"[a-zA-Z]+", str(text or "").lower())
        lex_words = {item["word"] for item in self.list_lexicon()}
        now = utc_now_iso()
        snippet = str(text or "").strip()[:140]
        newly_heard: list[str] = []
        seen_turn: set[str] = set()

        with self.store._lock:
            for tok in tokens:
                if (
                    len(tok) < 4
                    or tok in seen_turn
                    or tok in STOPWORDS_ID
                    or tok in COLLOQUIAL_SLANG_MAP
                    or is_laughter_token(tok)
                ):
                    continue
                seen_turn.add(tok)
                morph = analyze_morphology(tok, known_roots=lex_words | STOPWORDS_ID)
                if any(cand in lex_words or cand in STOPWORDS_ID for cand in morph["candidates"]):
                    continue
                syll = syllabify_indonesian(tok)
                if not syll["pronounceable"]:
                    continue
                self.store._conn.execute(
                    """
                    INSERT INTO speech_heard_words(
                        word, syllables_json, exposure_count, sample_context, grounded, last_heard_at
                    ) VALUES (?, ?, 1, ?, 0, ?)
                    ON CONFLICT(word) DO UPDATE SET
                        exposure_count = speech_heard_words.exposure_count + 1,
                        sample_context = excluded.sample_context,
                        last_heard_at = excluded.last_heard_at
                    """,
                    (tok, json.dumps(syll["syllables"], ensure_ascii=False), snippet, now),
                )
                newly_heard.append(tok)
            self.store._conn.commit()
        return {"turn_heard": newly_heard, "ungrounded_words": self.list_heard_words(ungrounded_only=True, limit=8)}

    def get_profile(self, *, include_vocab: bool = False) -> dict[str, Any]:
        """Return persistent developmental speaking stage progress & vocabulary summary."""
        with self.store._lock:
            stage_rows = self.store._conn.execute("SELECT * FROM speech_stage_state ORDER BY stage_id ASC").fetchall()
            vocab_count = int(self.store._conn.execute("SELECT COUNT(*) FROM speech_lexicon").fetchone()[0])
            user_taught_count = int(
                self.store._conn.execute("SELECT COUNT(*) FROM speech_lexicon WHERE source = 'user_taught'").fetchone()[0]
            )
            heard_ungrounded_count = int(
                self.store._conn.execute("SELECT COUNT(*) FROM speech_heard_words WHERE grounded = 0").fetchone()[0]
            )
            utt_count = int(self.store._conn.execute("SELECT COUNT(*) FROM speech_utterances WHERE passed = 1").fetchone()[0])

        stages = [
            {
                "stage_id": int(r["stage_id"]),
                "stage_name": r["stage_name"],
                "title_id": r["title_id"],
                "status": r["status"],
                "exam_score": float(r["exam_score"]),
                "passed_cases": int(r["passed_cases"]),
                "total_cases": int(r["total_cases"]),
                "receipt_id": r["receipt_id"],
            }
            for r in stage_rows
        ]
        passed_stages = [s["stage_id"] for s in stages if s["status"] == "PASSED"]
        current_stage = max(passed_stages) if passed_stages else 0
        current_spec = next((s for s in stages if s["stage_id"] == current_stage), None)
        profile: dict[str, Any] = {
            "current_stage": current_stage,
            "current_stage_name": current_spec["stage_name"] if current_spec else "pre_speech",
            "current_stage_title": current_spec["title_id"] if current_spec else "Tahap 0: Belum Dilatih",
            "graduated": current_stage == 4,
            "vocab_count": vocab_count,
            "user_taught_count": user_taught_count,
            "heard_ungrounded_count": heard_ungrounded_count,
            "verified_utterances": utt_count,
            "stages": stages,
        }
        if include_vocab:
            profile["user_taught_words"] = self.list_lexicon(source="user_taught")
            profile["heard_words"] = self.list_heard_words(ungrounded_only=True, limit=15)
            profile["lexicon_sample"] = self.list_lexicon()[:30]
        return profile

    def teach_word(
        self,
        word: str,
        meaning_id: str,
        *,
        role: str = "",
        contexts: list[str] | None = None,
        example: str = "",
        note: str = "",
        is_correction: bool = False,
        synonyms: list[str] | None = None,
        antonyms: list[str] | None = None,
    ) -> dict[str, Any]:
        """Teach or revise an Indonesian word grounded with syllables, meaning, examples, and role in SQLite."""
        clean_word = re.sub(r"[^a-zA-Z]", "", str(word or "")).lower()
        clean_meaning = str(meaning_id or "").strip()
        if not clean_word or not clean_meaning:
            return {"accepted": False, "reason": "kata_atau_makna_kosong"}
        syll = syllabify_indonesian(clean_word)
        if not syll["pronounceable"]:
            return {"accepted": False, "reason": f"kata_tidak_memenuhi_fonotaktik:{syll['reason']}", "syllabification": syll}

        resolved_role = infer_indonesian_pos(clean_word, clean_meaning, explicit_role=role)
        resolved_contexts = list(dict.fromkeys([c.strip().lower() for c in (contexts or ["khusus"]) if c.strip()]))

        heard_ctx = ""
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT sample_context FROM speech_heard_words WHERE word = ?",
                (clean_word,),
            ).fetchone()
            if row and row["sample_context"]:
                heard_ctx = str(row["sample_context"]).strip()

        examples_list: list[str] = []
        if example.strip():
            examples_list.append(example.strip())
        if heard_ctx and heard_ctx.lower() != clean_meaning.lower() and heard_ctx not in examples_list:
            examples_list.append(heard_ctx)
        if not examples_list:
            examples_list.append(f"{clean_word.capitalize()}: {clean_meaning}.")

        kb_rel = SEMANTIC_RELATIONS.get(clean_word, {})
        syns = list(dict.fromkeys(list(synonyms or []) + list(kb_rel.get("synonyms") or [])))
        ants = list(dict.fromkeys(list(antonyms or []) + list(kb_rel.get("antonyms") or [])))
        default_note = (
            f"Diralat oleh pengguna ({resolved_role})"
            if is_correction
            else f"Diajarkan langsung oleh pengguna ({resolved_role})"
        )
        entry = self._upsert_lexicon_word(
            word=clean_word,
            syllables=syll["syllables"],
            role=resolved_role,
            meaning_id=clean_meaning,
            contexts=resolved_contexts,
            examples=examples_list,
            domains=resolved_contexts,
            synonyms=syns,
            antonyms=ants,
            is_correction=is_correction,
            source="user_taught",
            mastery=0.9 if is_correction else 0.85,
            note=note or default_note,
        )
        return {"accepted": True, "entry": entry, "syllabification": syll}

    def lookup_word(
        self,
        raw_token: str,
        *,
        allow_fuzzy: bool = True,
        lex_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Resolve an input word against persisted SQLite lexicon via exact, stem, slang, or strict fuzzy lookup."""
        clean = re.sub(r"[^a-z-]", "", str(raw_token or "").lower()).strip("-")
        if not clean or is_laughter_token(clean):
            return None
        lmap = lex_map if lex_map is not None else {item["word"]: item for item in self.list_lexicon()}
        if not lmap:
            return None

        mapped = COLLOQUIAL_SLANG_MAP.get(clean.replace("-", ""), clean)
        morph = analyze_morphology(mapped, known_roots=set(lmap.keys()))
        if morph["root"] in lmap:
            return lmap[morph["root"]]
        for cand in morph["candidates"]:
            if cand in lmap:
                return lmap[cand]

        plain = mapped.replace("-", "")
        if not allow_fuzzy or len(plain) < 6 or clean in STOPWORDS_ID or plain in STOPWORDS_ID:
            return None
        max_dist = 1 if len(plain) < 7 else 2
        best_dist = max_dist + 1
        best_entry: dict[str, Any] | None = None
        for known, entry in lmap.items():
            if not known or known[0] != plain[0] or (max_dist == 2 and known[:2] != plain[:2]):
                continue
            dist = bounded_edit_distance(plain, known)
            if dist < best_dist:
                best_dist = dist
                best_entry = entry
        return best_entry if best_dist <= max_dist else None

    def find_grounded_words(self, text: str) -> list[dict[str, Any]]:
        """Extract unique SQLite lexicon matches appearing in text, prioritizing user-taught terms."""
        lex_map = {item["word"]: item for item in self.list_lexicon()}
        tokens = re.findall(r"[a-zA-Z]+", text.lower())
        seen: set[str] = set()
        matches: list[dict[str, Any]] = []
        for tok in tokens:
            if is_laughter_token(tok):
                continue
            can_fuzzy = len(tok) >= 6 and tok not in STOPWORDS_ID
            entry = self.lookup_word(tok, allow_fuzzy=can_fuzzy, lex_map=lex_map)
            if entry and entry["word"] not in seen:
                seen.add(entry["word"])
                matches.append(entry)
        matches.sort(key=lambda e: (0 if e["source"] == "user_taught" else 1, e["word"]))
        return matches

    @staticmethod
    def _semantic_target_contexts(cues: dict[str, Any] | None) -> set[str]:
        active = set((cues or {}).get("active_domains") or [])
        c = cues or {}
        if c.get("is_confused_or_negative"):
            active.update({"empati", "bantuan", "tugas"})
        if c.get("is_question"):
            active.update({"tanya", "memori", "verifikasi"})
        if c.get("is_positive"):
            active.update({"positif", "empati", "belajar"})
        if c.get("is_greeting") or c.get("asks_wellbeing"):
            active.update({"sapaan", "identitas", "verifikasi"})
        if c.get("mentions_speech"):
            active.update({"bahasa", "belajar", "komunikasi"})
        return active

    @staticmethod
    def _score_role_candidate(
        entry: dict[str, Any],
        *,
        preferred_words: set[str],
        target_contexts: set[str],
        seed_num: int,
        idx: int,
    ) -> tuple[int, int, str]:
        score = 0
        if entry["word"] in preferred_words:
            score += 40 if entry["source"] == "user_taught" else 20
        if entry["source"] == "user_taught":
            score += 12
        entry_ctxs = set(entry.get("contexts", [])) | set(entry.get("domains", []))
        score += len(entry_ctxs & target_contexts) * 8
        tie_rot = (idx - seed_num) % 97
        return (-score, tie_rot, entry["word"])

    def compose_telegraphic_phrase(
        self,
        pattern: tuple[str, ...],
        *,
        preferred_words: list[dict[str, Any]] | None = None,
        user_text: str = "",
        history_turns: int = 0,
    ) -> dict[str, Any]:
        """Compose a grammatical 2-3 word Stage-3 phrase ranked dynamically by context, domains, and turn."""
        if pattern not in TELEGRAPHIC_PATTERNS:
            return {"valid": False, "reason": f"pola_tidak_didukung:{pattern}", "phrase": ""}
        lexicon = self.list_lexicon()
        by_role: dict[str, list[dict[str, Any]]] = {}
        for item in lexicon:
            by_role.setdefault(item["role"], []).append(item)

        cues = self._extract_conversational_cues(user_text) if user_text else {}
        target_ctxs = self._semantic_target_contexts(cues)
        pref_set = {item["word"] for item in (preferred_words or [])}
        seed_num = sum(ord(ch) for ch in user_text) + history_turns

        chosen: list[tuple[str, str]] = []
        used_words: set[str] = set()
        for role in pattern:
            raw_pool = [e for e in by_role.get(role, []) if e["word"] not in used_words]
            if not raw_pool:
                return {"valid": False, "reason": f"peran_kosong:{role}", "phrase": ""}
            ranked = sorted(
                enumerate(raw_pool),
                key=lambda pair: self._score_role_candidate(
                    pair[1],
                    preferred_words=pref_set,
                    target_contexts=target_ctxs,
                    seed_num=seed_num,
                    idx=pair[0],
                ),
            )
            pick = ranked[0][1]["word"]
            used_words.add(pick)
            chosen.append((pick, role))
        res = validate_telegraphic_phrase(chosen)
        res["tokens"] = chosen
        return res

    def _run_stage_1_exam(self, task_id: str) -> dict[str, Any]:
        holdout_valid = {
            "bernyanyi": ["ber", "nya", "nyi"],
            "menyayangi": ["me", "nya", "ya", "ngi"],
            "kebersamaan": ["ke", "ber", "sa", "ma", "an"],
            "keterampilan": ["ke", "te", "ram", "pi", "lan"],
            "pengalaman": ["pe", "nga", "la", "man"],
            "struktur": ["struk", "tur"],
            "kompleks": ["kom", "pleks"],
            "bangun": ["ba", "ngun"],
        }
        holdout_invalid = ("bcdfg", "strkkk", "123!", "xztpq", "qzxw")
        passed_cases = 0
        total_cases = len(holdout_valid) + len(holdout_invalid) + 3

        sample_sylls: list[dict[str, Any]] = []
        for word, expected in holdout_valid.items():
            res = syllabify_indonesian(word)
            sample_sylls.append(res)
            if res["pronounceable"] and res["syllables"] == expected:
                passed_cases += 1

        for bad in holdout_invalid:
            if not syllabify_indonesian(bad)["pronounceable"]:
                passed_cases += 1

        babble = synthesize_babble(consonants=["d", "l", "r"], vowels=["e", "o"], count=4, seed=3)
        if len(babble) == 4 and all(b["pronounceable"] and set(b["word"]).issubset({"d", "l", "r", "e", "o"}) for b in babble):
            passed_cases += 1
        babble_alt = synthesize_babble(consonants=["m", "p", "n"], vowels=["a", "u"], count=4, seed=5)
        if len(babble_alt) == 4 and babble_alt != babble:
            passed_cases += 1
        if echo_input_syllables("Halo dunia indah") == ["ha-lo", "du-ni-a", "in-dah"]:
            passed_cases += 1

        ok = passed_cases == total_cases
        out_payload = {"passed_cases": passed_cases, "total_cases": total_cases, "babble_sample": [b["hyphenated"] for b in babble]}
        receipt = self.store.record_receipt(
            task_id=task_id,
            action_kind="speech_stage_1_exam",
            input_data=json.dumps({"holdout_words": sorted(holdout_valid), "holdout_invalid": list(holdout_invalid)}, sort_keys=True, ensure_ascii=False),
            output_data=json.dumps(out_payload, sort_keys=True, ensure_ascii=False),
            command_or_operation="stage1_phonotactics_and_babbling_holdout",
            exit_code=0 if ok else 1,
            stdout_text=json.dumps(out_payload, ensure_ascii=False),
            verified_by="speech_stage1_holdout_verifier",
            passed=ok,
        )
        return self._save_stage_result(
            stage_id=1,
            passed=ok,
            passed_cases=passed_cases,
            total_cases=total_cases,
            receipt_id=receipt["receipt_id"],
            evidence={"sample_syllables": sample_sylls[:4], "babble_sample": [b["hyphenated"] for b in babble]},
        )

    def _run_stage_2_exam(self, task_id: str) -> dict[str, Any]:
        seeded_count = self._batch_upsert_curriculum_lexicon()
        lex_list = self.list_lexicon()
        lex_map = {item["word"]: item for item in lex_list}

        holdout_probes = (
            ("belajr", "belajar"),
            ("katakan", "kata"),
            ("mengingat", "ingat"),
            ("terdengar", "dengar"),
            ("tuliskan", "tulis"),
            ("membantu", "bantu"),
            ("bersiap", "siap"),
            ("memperbaiki", "baik"),
            ("diperjelas", "jelas"),
            ("memperhatikan", "hati"),
            ("pelajarannya", "ajar"),
            ("ngomong", "bicara"),
        )
        taught_items = [item for item in lex_list if item["source"] == "user_taught"][:5]
        passed_cases = 0
        total_cases = len(holdout_probes) + len(taught_items) + 3
        resolved_map: dict[str, str] = {}

        for probe, expected in holdout_probes:
            hit = self.lookup_word(probe, lex_map=lex_map)
            resolved_map[probe] = hit["word"] if hit else ""
            if hit is not None and hit["word"] == expected:
                passed_cases += 1

        for item in taught_items:
            hit = self.lookup_word(item["word"], allow_fuzzy=False, lex_map=lex_map)
            if hit is not None and hit["meaning_id"] == item["meaning_id"]:
                passed_cases += 1

        vocab_count = len(lex_list)
        roles_covered = {item["role"] for item in lex_list}
        if vocab_count >= seeded_count:
            passed_cases += 1
        if all(item["syllables"] for item in lex_list):
            passed_cases += 1
        if VALID_POS_ROLES.issubset(roles_covered):
            passed_cases += 1

        ok = passed_cases == total_cases
        out_payload = {"passed_cases": passed_cases, "total_cases": total_cases, "vocab_count": vocab_count, "resolved": resolved_map}
        receipt = self.store.record_receipt(
            task_id=task_id,
            action_kind="speech_stage_2_exam",
            input_data=json.dumps({"probes": [p for p, _ in holdout_probes]}, sort_keys=True, ensure_ascii=False),
            output_data=json.dumps(out_payload, sort_keys=True, ensure_ascii=False),
            command_or_operation="stage2_holophrase_lexicon_and_holdout",
            exit_code=0 if ok else 1,
            stdout_text=json.dumps(out_payload, ensure_ascii=False),
            verified_by="speech_stage2_holdout_verifier",
            passed=ok,
        )
        return self._save_stage_result(
            stage_id=2,
            passed=ok,
            passed_cases=passed_cases,
            total_cases=total_cases,
            receipt_id=receipt["receipt_id"],
            evidence={"vocab_count": vocab_count, "resolved_probes": resolved_map},
        )

    def _run_stage_3_exam(self, task_id: str) -> dict[str, Any]:
        valid_patterns = (
            ("aktor", "aksi"),
            ("aksi", "objek"),
            ("negasi", "aksi"),
            ("objek", "sifat"),
            ("waktu", "aktor", "aksi"),
            ("aktor", "emosi", "keterangan"),
            ("aktor", "aksi", "tempat"),
            ("aktor", "aksi", "objek"),
            ("aktor", "negasi", "sifat"),
        )
        invalid_probes = (
            [("kata", "objek"), ("halo", "sapaan")],
            [("belajar", "aksi"), ("aku", "aktor")],
            [("aku", "aktor"), ("aku", "aktor")],
        )
        passed_cases = 0
        total_cases = len(valid_patterns) + len(invalid_probes) + 1
        samples: list[str] = []

        for idx, pat in enumerate(valid_patterns):
            built = self.compose_telegraphic_phrase(pat, user_text=f"uji kalimat {idx}", history_turns=idx)
            if built["valid"]:
                passed_cases += 1
                samples.append(built["phrase"])

        for bad in invalid_probes:
            if not validate_telegraphic_phrase(bad)["valid"]:
                passed_cases += 1

        p_a = self.compose_telegraphic_phrase(("aktor", "aksi", "objek"), user_text="aku bingung sekali", history_turns=1)
        p_b = self.compose_telegraphic_phrase(("aktor", "aksi", "objek"), user_text="bicara memori kata baru", history_turns=3)
        if p_a["valid"] and p_b["valid"] and p_a["phrase"] != p_b["phrase"]:
            passed_cases += 1

        ok = passed_cases == total_cases
        out_payload = {"passed_cases": passed_cases, "total_cases": total_cases, "samples": samples}
        receipt = self.store.record_receipt(
            task_id=task_id,
            action_kind="speech_stage_3_exam",
            input_data=json.dumps({"patterns": ["+".join(p) for p in valid_patterns]}, sort_keys=True, ensure_ascii=False),
            output_data=json.dumps(out_payload, sort_keys=True, ensure_ascii=False),
            command_or_operation="stage3_telegraphic_grammar_holdout",
            exit_code=0 if ok else 1,
            stdout_text=json.dumps(out_payload, ensure_ascii=False),
            verified_by="speech_stage3_holdout_verifier",
            passed=ok,
        )
        return self._save_stage_result(
            stage_id=3,
            passed=ok,
            passed_cases=passed_cases,
            total_cases=total_cases,
            receipt_id=receipt["receipt_id"],
            evidence={"telegraphic_samples": samples},
        )

    def _run_stage_4_exam(self, task_id: str) -> dict[str, Any]:
        prompts = (
            "Halo ACE, bagaimana kabarmu hari ini?",
            "Aku masih bingung memahami langkah awalnya.",
            "Mantap, aku senang melihat latihan ini jalan pelan!",
            "Apa arti bukti nyata dalam memori belajar?",
            "Apa sinonim kata tenang?",
            "Lawan kata gelap apa?",
            "gmn kbr lu skrg, blm paham kata baru?",
        )
        passed_cases = 0
        total_cases = len(prompts) + 1
        prior_replies: list[str] = []

        for idx, prompt in enumerate(prompts):
            reply_obj = self.compose_conversational_reply(
                user_text=prompt,
                conversation_id="__exam_stage4__",
                mode_label="Offline Lokal",
                offline_mode=True,
                latest_task=None,
                active_skills_count=len(self.store.list_skills(active_only=True)),
                tested_caps_count=0,
                recent_assistant_texts=prior_replies,
                history_turns=idx,
                override_stage=4,
                persist_utterance=False,
            )
            if reply_obj["verification"]["passed"]:
                passed_cases += 1
                prior_replies.append(reply_obj["reply"])

        if len(set(prior_replies)) == len(prompts):
            passed_cases += 1

        ok = passed_cases == total_cases
        out_payload = {"passed_cases": passed_cases, "total_cases": total_cases, "distinct_replies": len(set(prior_replies))}
        receipt = self.store.record_receipt(
            task_id=task_id,
            action_kind="speech_stage_4_exam",
            input_data=json.dumps({"prompts": list(prompts)}, sort_keys=True, ensure_ascii=False),
            output_data=json.dumps(out_payload, sort_keys=True, ensure_ascii=False),
            command_or_operation="stage4_contextual_utterance_holdout",
            exit_code=0 if ok else 1,
            stdout_text=json.dumps(out_payload, ensure_ascii=False),
            verified_by="speech_stage4_holdout_verifier",
            passed=ok,
        )
        return self._save_stage_result(
            stage_id=4,
            passed=ok,
            passed_cases=passed_cases,
            total_cases=total_cases,
            receipt_id=receipt["receipt_id"],
            evidence={"sample_reply": prior_replies[0] if prior_replies else ""},
        )

    def _stage_runners(self) -> tuple[Any, ...]:
        return (
            self._run_stage_1_exam,
            self._run_stage_2_exam,
            self._run_stage_3_exam,
            self._run_stage_4_exam,
        )

    def _promote_graduated_speech_skill(
        self,
        *,
        task_id: str,
        stage_ids: list[int],
        receipt_ids: list[str],
        conversation_id: str,
        vocab_count: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        skill = self.store.save_skill(
            name="keterampilan_berbicara_bertahap_id",
            domain="linguistics_speech_production",
            preconditions=["Memori leksikon SQLite & pustaka ace_indo_nlp tersedia lokal"],
            boundary_limitations=["Ujaran dalam moda teks/percakapan Bahasa Indonesia tanpa sintesis audio suara"],
            procedure_steps=[spec["title_id"] for spec in SPEECH_STAGE_SPECS],
            verification_template={"stages": stage_ids, "receipt_ids": receipt_ids},
            source_task_ids=[task_id],
        )
        self.store.set_frontier_capability(
            capability_id="cap_keterampilan_berbicara_id",
            name_id="Keterampilan Berbicara Bahasa Indonesia Bertahap (4 Tahap + Pustaka Bahasa Indonesia)",
            category="bahasa",
            status="KNOWN_AND_TESTED",
            evidence_ref=receipt_ids[-1],
        )
        self.store.save_learning_experience(
            task_id=task_id,
            failure_signature="speech_production_baseline_untrained",
            root_cause="Respons percakapan sebelumnya memakai templat statis tanpa pustaka morfologi, anaphora & memori leksikon",
            strategy_before="static_offline_greeting_template",
            strategy_after="developmental_4stage_speech_engine_with_indo_nlp",
            delta_change="Mengintegrasikan pustaka ace_indo_nlp (fonotaktik, morfologi Nazief-Adriani, 190+ kata semantik, anaphora, ralat definisi)",
            extracted_rule="Bangun ujaran Bahasa Indonesia bertahap dari suku kata tervalidasi, leksikon semantik, dan fakta runtime terverifikasi.",
            applicable_when=["Percakapan teks Bahasa Indonesia lokal/offline", "Pengajaran & ralat kata baru lewat chat"],
            not_applicable_when=["Sintesis gelombang suara audio/TTS"],
            verification_evidence={"stage_receipts": receipt_ids, "vocab_count": vocab_count},
            reusable_skill_candidate=True,
        )
        updated_task = self.store.update_task(
            task_id,
            status="COMPLETED",
            verification_summary={"passed": True, "receipt_ids": receipt_ids, "vocab_count": vocab_count},
        )
        self.store.emit_event(
            conversation_id=conversation_id,
            task_id=task_id,
            kind="skill_learned",
            status="COMPLETED",
            summary_code="speech_4stage_graduated",
            technical_detail={"skill_name": "keterampilan_berbicara_bertahap_id", "vocab_count": vocab_count},
            verification_passed=True,
        )
        return skill, updated_task

    def train_stage(
        self,
        target_stage: int,
        *,
        conversation_id: str = "conv_utama",
        user_request: str = "",
        auto_prerequisites: bool = False,
    ) -> dict[str, Any]:
        """Train and verify a single developmental speaking stage with strict sequential prerequisites."""
        stage_num = int(target_stage)
        if stage_num not in (1, 2, 3, 4):
            raise ValueError(f"Tahap berbicara harus 1..4, bukan {target_stage!r}")

        prof_before = self.get_profile()
        missing = [s["stage_id"] for s in prof_before["stages"] if s["stage_id"] < stage_num and s["status"] != "PASSED"]
        if missing and not auto_prerequisites:
            return {
                "passed": False,
                "blocked_by_stage": missing[0],
                "missing_prerequisites": missing,
                "target_stage": stage_num,
                "task": None,
                "profile": prof_before,
            }

        spec = SPEECH_STAGE_SPECS[stage_num - 1]
        task = self.store.create_task(
            conversation_id=conversation_id,
            kind="learning_task",
            title_id=f"Latihan {spec['title_id']}",
            user_request=user_request or f"Latih berbicara tahap {stage_num}",
            normalized_goal=f"Kuasai dan uji {spec['title_id']} secara holdout",
            priority=9.5,
        )
        self.store.update_task(task["task_id"], status="LEARNING")
        self.store.emit_event(
            conversation_id=conversation_id,
            task_id=task["task_id"],
            kind="task_started",
            status="LEARNING",
            summary_code=f"speech_stage_{stage_num}_started",
            technical_detail={"title_id": spec["title_id"], "goal": f"melatih berbicara tahap {stage_num}/4"},
        )

        runners = self._stage_runners()
        to_run = [*missing, stage_num] if auto_prerequisites else [stage_num]
        stage_results = [runners[sid - 1](task["task_id"]) for sid in to_run]
        last_res = stage_results[-1]
        if not all(r["passed"] for r in stage_results):
            failed = next(r for r in stage_results if not r["passed"])
            upd = self.store.update_task(
                task["task_id"],
                status="FAILED_WITH_RECOVERY_STATE",
                verification_summary={"passed": False, "failed_stage": failed["stage_id"]},
            )
            self.store.emit_event(
                conversation_id=conversation_id,
                task_id=task["task_id"],
                kind="skill_learned",
                status="FAILED",
                summary_code="speech_stage_exam_failed",
                technical_detail={"skill_name": f"tahap_bicara_{failed['stage_id']}", "stage": failed["stage_id"]},
                verification_passed=False,
            )
            return {"passed": False, "target_stage": stage_num, "stages": stage_results, "task": upd, "profile": self.get_profile()}

        prof_after = self.get_profile()
        skill_obj: dict[str, Any] | None = None
        if prof_after["graduated"]:
            all_stage_ids = [s["stage_id"] for s in prof_after["stages"]]
            all_receipts = [s["receipt_id"] or last_res["receipt_id"] for s in prof_after["stages"]]
            skill_obj, updated_task = self._promote_graduated_speech_skill(
                task_id=task["task_id"],
                stage_ids=all_stage_ids,
                receipt_ids=all_receipts,
                conversation_id=conversation_id,
                vocab_count=prof_after["vocab_count"],
            )
        else:
            updated_task = self.store.update_task(
                task["task_id"],
                status="COMPLETED",
                verification_summary={"passed": True, "stage_id": stage_num, "receipt_id": last_res["receipt_id"]},
            )
            self.store.emit_event(
                conversation_id=conversation_id,
                task_id=task["task_id"],
                kind="skill_learned",
                status="COMPLETED",
                summary_code=f"speech_stage_{stage_num}_passed",
                technical_detail={
                    "skill_name": f"tahap_bicara_{stage_num}_{spec['stage_name']}",
                    "stage": stage_num,
                    "vocab_count": prof_after["vocab_count"],
                },
                verification_passed=True,
            )

        return {
            "passed": True,
            "target_stage": stage_num,
            "stage_result": last_res,
            "stages": stage_results,
            "skill": skill_obj,
            "task": updated_task,
            "profile": self.get_profile(include_vocab=True),
        }

    def train_and_graduate(
        self,
        *,
        conversation_id: str = "conv_utama",
        user_request: str = "Pelajari skill berbicara bertahap 4 tahap",
    ) -> dict[str, Any]:
        """Run Stages 1->4 sequentially with unseen holdout checks, then promote verified skill."""
        task = self.store.create_task(
            conversation_id=conversation_id,
            kind="learning_task",
            title_id="Kurikulum Pengembangan Skill Berbicara 4 Tahap",
            user_request=user_request,
            normalized_goal="Kuasai keterampilan berbicara Bahasa Indonesia dari fonotaktik hingga ujaran kontekstual",
            priority=9.5,
        )
        self.store.update_task(task["task_id"], status="LEARNING")
        self.store.emit_event(
            conversation_id=conversation_id,
            task_id=task["task_id"],
            kind="task_started",
            status="LEARNING",
            summary_code="speech_curriculum_started",
            technical_detail={"title_id": "Skill Berbicara 4 Tahap", "goal": "melatih keterampilan berbicara bertahap"},
        )

        stage_results: list[dict[str, Any]] = []
        for fn in self._stage_runners():
            res = fn(task["task_id"])
            stage_results.append(res)
            if not res["passed"]:
                self.store.update_task(
                    task["task_id"],
                    status="FAILED_WITH_RECOVERY_STATE",
                    verification_summary={"passed": False, "failed_stage": res["stage_id"]},
                )
                self.store.emit_event(
                    conversation_id=conversation_id,
                    task_id=task["task_id"],
                    kind="skill_learned",
                    status="FAILED",
                    summary_code="speech_stage_exam_failed",
                    technical_detail={"skill_name": f"tahap_bicara_{res['stage_id']}", "stage": res["stage_id"]},
                    verification_passed=False,
                )
                return {"passed": False, "task": self.store.get_task(task["task_id"]), "stages": stage_results, "profile": self.get_profile()}

        profile = self.get_profile()
        skill, updated_task = self._promote_graduated_speech_skill(
            task_id=task["task_id"],
            stage_ids=[r["stage_id"] for r in stage_results],
            receipt_ids=[r["receipt_id"] for r in stage_results],
            conversation_id=conversation_id,
            vocab_count=profile["vocab_count"],
        )
        return {
            "passed": True,
            "task": updated_task,
            "skill": skill,
            "stages": stage_results,
            "profile": self.get_profile(include_vocab=True),
        }

    @staticmethod
    def _extract_conversational_cues(user_text: str, *, pending_word: str = "") -> dict[str, Any]:
        return analyze_discourse_cues(user_text, pending_word=pending_word)

    def verify_utterance(
        self,
        *,
        utterance: str,
        user_text: str,
        stage_id: int,
        latest_task: dict[str, Any] | None,
        offline_mode: bool,
        recent_assistant_texts: list[str],
    ) -> dict[str, Any]:
        """Score an outgoing Indonesian utterance against stage bounds, anti-hallucination, and novelty gates."""
        words = re.findall(r"[A-Za-z0-9_'-]+", utterance)
        min_words = 2 if stage_id <= 2 else (3 if stage_id == 3 else 5)
        max_words = 35 if stage_id == 1 else (48 if stage_id == 2 else (60 if stage_id == 3 else 260))
        bounds_ok = min_words <= len(words) <= max_words

        hallucination_violations: list[str] = []
        low_u = utterance.lower()
        if latest_task is None and any(
            p in low_u
            for p in ("berkas telah kubuat", "sudah kuselesaikan tugas", "skrip selesai dijalankan", "semua tes berhasil dijalankan")
        ):
            hallucination_violations.append("claimed_nonexistent_task")
        if offline_mode and any(p in low_u for p in ("terhubung ke internet", "api cloud berhasil", "mengakses internet")):
            hallucination_violations.append("claimed_network_while_offline")

        norm_col, _ = normalize_colloquial(user_text)
        user_tokens = set(re.findall(r"[a-z]+", user_text.lower())) | set(re.findall(r"[a-z]+", norm_col))
        out_tokens = set(re.findall(r"[a-z]+", low_u))
        overlap = user_tokens & out_tokens
        runtime_grounded = any(k in low_u for k in ("ace", "tahap", "offline", "lokal", "kosakata", "leksikon"))
        if stage_id == 4 and len(user_tokens) >= 4:
            grounding_ok = bool(overlap) or ("tahap" in low_u) or ("kosakata" in low_u) or ("leksikon" in low_u)
        else:
            grounding_ok = bool(overlap) or runtime_grounded

        non_repetitive = utterance.strip() not in [r.strip() for r in recent_assistant_texts[-4:]]
        passed = bool(bounds_ok and not hallucination_violations and grounding_ok and non_repetitive)
        score = round(
            (int(bounds_ok) + int(not hallucination_violations) + int(grounding_ok) + int(non_repetitive)) / 4.0,
            4,
        )
        return {
            "passed": passed,
            "score": score,
            "word_count": len(words),
            "bounds_ok": bounds_ok,
            "grounding_ok": grounding_ok,
            "non_repetitive": non_repetitive,
            "hallucination_violations": hallucination_violations,
        }

    def _pick_curiosity_word(
        self,
        *,
        user_text: str,
        recent_assistant_texts: list[str],
        exclude_word: str = "",
    ) -> dict[str, Any] | None:
        recent_joined = " ".join(recent_assistant_texts[-4:]).lower()
        heard = self.list_heard_words(ungrounded_only=True, limit=25)
        turn_tokens = set(re.findall(r"[a-z]+", user_text.lower()))
        candidates: list[tuple[tuple[int, int, int, int, int, str], dict[str, Any]]] = []
        for item in heard:
            w = item["word"]
            if (
                w == exclude_word
                or len(w) < 4
                or w in STOPWORDS_ID
                or w in COLLOQUIAL_SLANG_MAP
                or is_laughter_token(w)
                or f"`{w}`" in recent_joined
                or f"'{w}'" in recent_joined
            ):
                continue
            if w in turn_tokens or item["exposure_count"] >= 2:
                prefixed = 1 if w.startswith(("me", "di", "ber", "ter")) and len(w) > 5 else 0
                score = (
                    0 if item["exposure_count"] >= 2 else 1,
                    0 if w in turn_tokens else 1,
                    prefixed,
                    -item["exposure_count"],
                    -len(w),
                    w,
                )
                candidates.append((score, item))
        candidates.sort(key=lambda pair: pair[0])
        return candidates[0][1] if candidates else None

    @staticmethod
    def _should_ask_curiosity(stage_id: int, cues: dict[str, Any], user_text: str) -> bool:
        if stage_id < 2:
            return False
        if cues.get("is_greeting") or cues.get("asks_wellbeing") or cues.get("is_thanks"):
            return False
        if cues.get("dialogue_act", "general") != "general":
            return False
        return len(re.findall(r"[a-zA-Z]+", str(user_text or ""))) > 3

    def _compose_stage1_utterance(self, user_text: str, mode_label: str, history_turns: int) -> tuple[list[str], dict[str, Any] | None]:
        user_syls = echo_input_syllables(user_text, max_words=2)
        phonemes = tokenize_phonemes(user_text)
        c_pool = list(dict.fromkeys(ph for ph in phonemes if ph in CONSONANTS or ph in DIGRAPHS))
        v_pool = list(dict.fromkeys(ph for ph in phonemes if ph in VOWELS))
        bab = synthesize_babble(
            consonants=c_pool[:4] if c_pool else None,
            vowels=v_pool[:3] if v_pool else None,
            count=2,
            seed=history_turns,
        )
        echo_parts = user_syls + [b["hyphenated"] for b in bab[:2]]
        utterance = " · ".join(dict.fromkeys(echo_parts)) or "ba-ba · ma-ma"
        return [f"`{utterance}` [ACE Tahap `1/4` — tiru suku kata; {mode_label}]"], None

    def _compose_stage2_utterance(
        self,
        *,
        user_text: str,
        grounded: list[dict[str, Any]],
        profile: dict[str, Any],
        mode_label: str,
        recent_assistant_texts: list[str],
    ) -> tuple[list[str], dict[str, Any] | None]:
        taught_hits = [w for w in grounded if w["source"] == "user_taught"]
        primary = taught_hits[0] if taught_hits else (grounded[0] if grounded else None)
        if primary:
            holo = f"**{primary['word']}** (*{primary['meaning_id']}*)"
        else:
            holo = "**dengar** · **belajar**"
        curious = self._pick_curiosity_word(user_text=user_text, recent_assistant_texts=recent_assistant_texts)
        ask_tail = f" — kata `{curious['word']}` artinya apa?" if curious else ""
        return [f"{holo}{ask_tail} [ACE Tahap `2/4`: {profile['vocab_count']} kata; {mode_label}]"], curious

    def _select_stage3_pattern(self, cues: dict[str, Any]) -> tuple[str, ...]:
        if cues["is_question"] and not cues["is_greeting"]:
            return ("tanya", "objek") if cues["mentions_speech"] else ("aktor", "aksi", "objek")
        if cues["is_confused_or_negative"]:
            return ("aktor", "aksi", "objek")
        if cues["is_greeting"]:
            return ("sapaan", "aktor")
        return ("aktor", "aksi", "objek")

    def _compose_stage3_utterance(
        self,
        *,
        user_text: str,
        cues: dict[str, Any],
        grounded: list[dict[str, Any]],
        profile: dict[str, Any],
        mode_label: str,
        history_turns: int,
        recent_assistant_texts: list[str],
    ) -> tuple[list[str], dict[str, Any] | None]:
        pattern = self._select_stage3_pattern(cues)
        phrase_obj = self.compose_telegraphic_phrase(
            pattern,
            preferred_words=grounded,
            user_text=user_text,
            history_turns=history_turns,
        )
        tele = phrase_obj["phrase"] if phrase_obj["valid"] else "kita belajar kata"
        taught_hits = [w for w in grounded if w["source"] == "user_taught"]
        note = f"; ingat `{taught_hits[0]['word']}` = *{taught_hits[0]['meaning_id']}*" if taught_hits else ""
        curious = self._pick_curiosity_word(user_text=user_text, recent_assistant_texts=recent_assistant_texts)
        ask = f" Kata `{curious['word']}` maksudnya apa?" if curious else ""
        return [f"*\"{tele}\"* [ACE Tahap `3/4`: telegrafik, {profile['vocab_count']} kata, {mode_label}{note}].{ask}"], curious

    def _compose_natural_dialogue_turn(
        self,
        *,
        stage_id: int,
        user_text: str,
        cues: dict[str, Any],
        grounded: list[dict[str, Any]],
        profile: dict[str, Any],
        mode_label: str,
        latest_task: dict[str, Any] | None,
        recent_assistant_texts: list[str],
        history_turns: int,
        conversation_context: dict[str, Any] | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> tuple[list[str], dict[str, Any] | None, dict[str, str]]:
        q_target = cues.get("lexicon_qa_target")
        if q_target:
            lex_map = {item["word"]: item for item in self.list_lexicon()}
            entry = self.lookup_word(q_target["word"], allow_fuzzy=False, lex_map=lex_map)
            clauses = format_lexicon_qa_clauses(
                query_target=q_target,
                entry=entry,
                grounded=grounded,
                mode_label=mode_label,
                known_roots=set(lex_map.keys()),
            )
            return clauses, None, {"last_topic": q_target["word"], "last_bot_question": ""}

        curious = (
            self._pick_curiosity_word(user_text=user_text, recent_assistant_texts=recent_assistant_texts)
            if self._should_ask_curiosity(stage_id, cues, user_text)
            else None
        )
        turn = realize_indonesian_turn(
            user_text=user_text,
            cues=cues,
            grounded=grounded,
            profile=profile,
            mode_label=mode_label,
            latest_task=latest_task,
            recent_assistant_texts=recent_assistant_texts,
            history_turns=history_turns,
            curious_word=curious,
            conversation_context=conversation_context,
            recent_messages=recent_messages,
            stage_id=stage_id,
        )
        ctx_meta = {"last_topic": turn["next_topic"], "last_bot_question": turn["bot_question"]}
        return turn["clauses"], curious, ctx_meta

    def _build_stage_clauses(
        self,
        *,
        stage_id: int,
        user_text: str,
        cues: dict[str, Any],
        grounded: list[dict[str, Any]],
        profile: dict[str, Any],
        mode_label: str,
        latest_task: dict[str, Any] | None,
        recent_assistant_texts: list[str],
        history_turns: int,
        conversation_context: dict[str, Any] | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> tuple[list[str], dict[str, Any] | None, dict[str, str]]:
        if stage_id in (0, 4):
            return self._compose_natural_dialogue_turn(
                stage_id=stage_id,
                user_text=user_text,
                cues=cues,
                grounded=grounded,
                profile=profile,
                mode_label=mode_label,
                latest_task=latest_task,
                recent_assistant_texts=recent_assistant_texts,
                history_turns=history_turns,
                conversation_context=conversation_context,
                recent_messages=recent_messages,
            )
        if stage_id == 1:
            c1, cur1 = self._compose_stage1_utterance(user_text, mode_label, history_turns)
            return c1, cur1, {}
        if stage_id == 2:
            c2, cur2 = self._compose_stage2_utterance(
                user_text=user_text,
                grounded=grounded,
                profile=profile,
                mode_label=mode_label,
                recent_assistant_texts=recent_assistant_texts,
            )
            return c2, cur2, {}
        c3, cur3 = self._compose_stage3_utterance(
            user_text=user_text,
            cues=cues,
            grounded=grounded,
            profile=profile,
            mode_label=mode_label,
            history_turns=history_turns,
            recent_assistant_texts=recent_assistant_texts,
        )
        return c3, cur3, {}

    def record_verified_utterance(
        self,
        *,
        conversation_id: str,
        stage_id: int,
        reply: str,
        grounded_words: list[str],
        active_skills_count: int,
        tested_caps_count: int,
        verification: dict[str, Any],
        history_turns: int,
    ) -> None:
        """Persist an evaluated conversational utterance and verification score into SQLite."""
        utt_id = "utt_" + hashlib.sha256(f"{conversation_id}:{history_turns}:{utc_now_iso()}:{reply}".encode("utf-8")).hexdigest()[:12]
        with self.store._lock:
            self.store._conn.execute(
                """
                INSERT INTO speech_utterances(
                    utterance_id, conversation_id, stage_id, intent, utterance_text,
                    grounding_json, verification_score, passed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utt_id,
                    conversation_id,
                    stage_id,
                    "GENERAL_CONVERSATION",
                    reply,
                    json.dumps({"grounded_words": grounded_words, "skills": active_skills_count, "caps": tested_caps_count}, ensure_ascii=False),
                    float(verification["score"]),
                    1 if verification["passed"] else 0,
                    utc_now_iso(),
                ),
            )
            self.store._conn.commit()

    def build_gguf_speech_prompt_context(
        self,
        *,
        user_text: str,
        latest_task: dict[str, Any] | None,
        mode_label: str,
    ) -> str:
        """Build developmental lexicon, domain, and runtime grounding context for local GGUF generation."""
        prof = self.get_profile(include_vocab=True)
        taught = prof.get("user_taught_words", [])[:8]
        taught_str = "; ".join(f"{w['word']} = {w['meaning_id']}" for w in taught) or "belum ada"
        heard = prof.get("heard_words", [])[:3]
        heard_str = ", ".join(h["word"] for h in heard) or "tidak ada"
        cues = self._extract_conversational_cues(user_text)
        dom_str = ", ".join(cues.get("active_domains") or []) or "percakapan umum"
        task_str = f"{latest_task['title_id']} ({latest_task['status']})" if latest_task else "belum ada tugas aktif"
        return (
            f"Kamu adalah ACE dalam mode {mode_label}. Kemampuan bicaramu berada di Tahap {prof['current_stage']}/4 "
            f"({prof['vocab_count']} kosakata SQLite; domain aktif: {dom_str}). "
            f"Status tugas nyata saat ini: {task_str}. Jangan pernah mengarang tugas selesai atau akses internet bila offline. "
            f"Kosakata ajaran pengguna yang wajib diingat bila relevan: {taught_str}. "
            f"Kata asing yang baru terdengar dan boleh ditanyakan artinya: {heard_str}. "
            f"Jawab pesan pengguna dengan Bahasa Indonesia yang santai, hangat, dan mengalir seperti teman ngobrol (pakai 'aku/kamu', "
            f"jangan kaku seperti robot, dan jangan mengulang perkenalan di setiap balasan). "
            f"Tetap jujur, tuntas dalam 2-4 kalimat utuh, dan relevan terhadap: {user_text[:120]}"
        )

    def compose_conversational_reply(
        self,
        *,
        user_text: str,
        conversation_id: str,
        mode_label: str,
        offline_mode: bool,
        latest_task: dict[str, Any] | None,
        active_skills_count: int,
        tested_caps_count: int,
        recent_assistant_texts: list[str],
        history_turns: int,
        override_stage: int | None = None,
        persist_utterance: bool = True,
        observe_turn: bool = True,
        conversation_context: dict[str, Any] | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Compose and verify a stage-appropriate grounded Indonesian utterance."""
        if persist_utterance and observe_turn:
            self.observe_user_utterance(user_text)
        profile = self.get_profile()
        stage_id = int(override_stage if override_stage is not None else profile["current_stage"])
        pending_word = str((conversation_context or {}).get("pending_curiosity_word", "")).strip()
        cues = self._extract_conversational_cues(user_text, pending_word=pending_word)
        grounded = self.find_grounded_words(user_text)

        clauses, asked_curious, ctx_meta = self._build_stage_clauses(
            stage_id=stage_id,
            user_text=user_text,
            cues=cues,
            grounded=grounded,
            profile=profile,
            mode_label=mode_label,
            latest_task=latest_task,
            recent_assistant_texts=recent_assistant_texts,
            history_turns=history_turns,
            conversation_context=conversation_context,
            recent_messages=recent_messages,
        )
        reply = "\n\n".join(clauses)
        ver = self.verify_utterance(
            utterance=reply,
            user_text=user_text,
            stage_id=stage_id,
            latest_task=latest_task,
            offline_mode=offline_mode,
            recent_assistant_texts=recent_assistant_texts,
        )
        if persist_utterance:
            if not conversation_id.startswith("__"):
                ctx_updates: dict[str, Any] = dict(ctx_meta)
                if asked_curious is not None:
                    ctx_updates["pending_curiosity_word"] = asked_curious["word"]
                if ctx_updates:
                    self.store.update_conversation_context(conversation_id, ctx_updates)
            self.record_verified_utterance(
                conversation_id=conversation_id,
                stage_id=stage_id,
                reply=reply,
                grounded_words=[g["word"] for g in grounded],
                active_skills_count=active_skills_count,
                tested_caps_count=tested_caps_count,
                verification=ver,
                history_turns=history_turns,
            )

        return {"reply": reply, "stage_id": stage_id, "grounded_words": [g["word"] for g in grounded], "verification": ver}


def _format_teach_word_reply(
    engine: SpeechDevelopmentEngine,
    frame: dict[str, Any],
    *,
    conversation_id: str = "",
) -> tuple[str, dict[str, Any] | None]:
    taught = frame.get("taught_word", {})
    is_corr = bool(taught.get("is_correction", False))
    is_ana = bool(taught.get("is_anaphora", False))
    res = engine.teach_word(
        taught.get("word", ""),
        taught.get("meaning_id", ""),
        role=taught.get("role", ""),
        is_correction=is_corr,
    )
    if not res["accepted"]:
        return (
            f"Kata `{taught.get('word', '')}` belum bisa kusimpan karena alasan `{res['reason']}`. "
            "Pastikan kata berbahasa Indonesia yang bisa dilafalkan dan sertakan maknanya (contoh: *\"ajarkan kata merdu artinya indah didengar\"*).",
            None,
        )
    if conversation_id:
        engine.store.update_conversation_context(conversation_id, {"pending_curiosity_word": ""})
    entry = res["entry"]
    phrase = engine.compose_telegraphic_phrase(("aktor", "aksi", "objek"), preferred_words=[entry], user_text=entry["word"])
    sample_phrase = f" Contoh gabungan: *\"{phrase['phrase']}\"*." if phrase.get("valid") else ""
    if is_corr:
        action_prefix = f"Arti kata **`{entry['word']}`** kuralat dan perbarui (revisi ke-`{entry['revision_count']}`)"
    elif is_ana:
        action_prefix = f"Terima kasih penjelasannya! Kata **`{entry['word']}`** yang baru kubahas"
    else:
        action_prefix = f"Kata baru **`{entry['word']}`**"
    return (
        f"{action_prefix} (`{'-'.join(entry['syllables'])}`, peran `{entry['role']}`) "
        f"sudah kusimpan ke leksikon persisten dengan makna: *{entry['meaning_id']}*.{sample_phrase}",
        None,
    )


def _format_train_speech_reply(
    engine: SpeechDevelopmentEngine,
    frame: dict[str, Any],
    text: str,
    conversation_id: str,
) -> tuple[str, dict[str, Any] | None]:
    target = frame.get("target_stage", "all")
    if target == "next":
        cur = engine.get_profile()["current_stage"]
        target = min(4, cur + 1)

    if isinstance(target, int):
        res = engine.train_stage(target, conversation_id=conversation_id, user_request=text)
        if not res["passed"] and res.get("blocked_by_stage"):
            req = res["blocked_by_stage"]
            return (
                f"Belum bisa loncat langsung ke **Tahap {target}/4** karena **Tahap {req}/4** masih berstatus `LOCKED`. "
                f"Selesaikan dulu secara bertahap dengan mengirim *\"latih tahap {req}\"* (atau *\"lanjut tahap berikutnya\"*).",
                None,
            )
        prof = res["profile"]
        sr = res.get("stage_result") or (res.get("stages") or [{}])[-1]
        if not res["passed"]:
            return (f"Latihan **Tahap {target}/4** belum lulus ujian *holdout* (`{sr.get('status', 'FAILED')}`).", res["task"])
        sample = engine.compose_conversational_reply(
            user_text=text,
            conversation_id=conversation_id,
            mode_label="Latihan",
            offline_mode=engine.store.is_offline(),
            latest_task=res["task"],
            active_skills_count=len(engine.store.list_skills(active_only=True)),
            tested_caps_count=0,
            recent_assistant_texts=[],
            history_turns=target,
            override_stage=target,
            persist_utterance=False,
        )
        grad_note = (
            f"\n\nSelamat! Keempat tahap tuntas dan skill `{res['skill']['name']}` berstatus `KNOWN_AND_TESTED`."
            if res.get("skill")
            else f"\n\nJika siap melanjutkan, kirim *\"latih tahap {target + 1}\"* atau *\"lanjut tahap berikutnya\"*."
        )
        return (
            f"Latihan **{SPEECH_STAGE_SPECS[target - 1]['title_id']}** lulus ({sr.get('passed_cases', 0)}/{sr.get('total_cases', 0)} holdout, "
            f"receipt `{sr.get('receipt_id', '')}`, kosakata `{prof['vocab_count']}`).\n\n"
            f"Contoh ujaran tahap `{target}/4`: {sample['reply']}{grad_note}",
            res["task"],
        )

    grad = engine.train_and_graduate(conversation_id=conversation_id, user_request=text)
    prof = grad["profile"]
    stage_lines = "\n".join(
        f"- Tahap {s['stage_id']} (`{s['stage_name']}`): `{s['status']}` ({s['passed_cases']}/{s['total_cases']} kasus holdout, receipt `{s['receipt_id']}`)"
        for s in prof["stages"]
    )
    if grad["passed"]:
        return (
            f"Latihan **Skill Berbicara 4 Tahap** selesai dan seluruh ujian *holdout* lulus! "
            f"Skill `{grad['skill']['name']}` serta kapabilitas `cap_keterampilan_berbicara_id` berstatus `KNOWN_AND_TESTED` "
            f"dengan **{prof['vocab_count']} kosakata** persisten.\n\n{stage_lines}\n\n"
            "Sekarang kamu bisa mengajakku mengobrol biasa, bertanya sinonim/antonim, atau mengajari maupun meralat kata secara alami.",
            grad["task"],
        )
    return (f"Latihan **Skill Berbicara** berhenti di tahap yang belum lulus ujian *holdout*:\n\n{stage_lines}", grad["task"])


def handle_speech_chat_intent(
    *,
    engine: SpeechDevelopmentEngine,
    frame: dict[str, Any],
    text: str,
    conversation_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """Execute TRAIN_SPEECH, TEACH_WORD, or SPEECH_STATUS intents and format concise Indonesian replies."""
    intent = frame.get("intent")
    if intent == "TEACH_WORD":
        return _format_teach_word_reply(engine, frame, conversation_id=conversation_id)
    if intent == "TRAIN_SPEECH":
        return _format_train_speech_reply(engine, frame, text, conversation_id)

    prof = engine.get_profile(include_vocab=True)
    taught_words = ", ".join(f"`{w['word']}`" for w in prof.get("user_taught_words", [])[:8]) or "belum ada kata ajaran pengguna"
    heard_words = ", ".join(f"`{w['word']}` ({w['exposure_count']}x)" for w in prof.get("heard_words", [])[:6]) or "belum ada"
    return (
        f"Perkembangan bicara **ACE** saat ini: **{prof['current_stage_title']}** (Tahap `{prof['current_stage']}/4`, lulus penuh: `{prof['graduated']}`).\n"
        f"- Total leksikon persisten: **{prof['vocab_count']} kata** (ajaran pengguna: {prof['user_taught_count']})\n"
        f"- Kata ajaran pengguna: {taught_words}\n"
        f"- Kata asing yang baru terdengar (menunggu makna): {heard_words}\n"
        f"- Ujaran kontekstual terverifikasi: {prof['verified_utterances']}",
        None,
    )
