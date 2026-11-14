"""Pure-Python Indonesian Computational Linguistics & Developmental Speech Library (`ace_indo_nlp`).

Unified offline-first facade exporting phonotactics, morphology, lexical semantics,
pragmatic discourse analysis, and compositional Indonesian realization.
"""
from __future__ import annotations

from .discourse import (
    analyze_discourse_cues,
    clean_definition_tail,
    extract_meaning_query,
    extract_query_target,
    format_lexicon_qa_clauses,
    is_question_or_empty_tail,
    parse_teaching_or_correction,
    realize_indonesian_clauses,
)
from .lexicon_kb import (
    CORE_INDONESIAN_LEXICON,
    NON_TEACHABLE_WORDS_ID,
    QUESTION_WORDS_ID,
    SEMANTIC_RELATIONS,
    STOPWORDS_ID,
    TELEGRAPHIC_PATTERNS,
    VALID_POS_ROLES,
    infer_indonesian_pos,
)
from .morphology import (
    COLLOQUIAL_SLANG_MAP,
    analyze_morphology,
    bounded_edit_distance,
    normalize_colloquial,
    stem_candidates,
    stem_word,
)
from .phonotactics import (
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

__all__ = [
    "COLLOQUIAL_SLANG_MAP",
    "CONSONANTS",
    "CORE_INDONESIAN_LEXICON",
    "DIGRAPHS",
    "NON_TEACHABLE_WORDS_ID",
    "QUESTION_WORDS_ID",
    "SEMANTIC_RELATIONS",
    "STOPWORDS_ID",
    "TELEGRAPHIC_PATTERNS",
    "VALID_CODA_CLUSTERS",
    "VALID_ONSET_CLUSTERS",
    "VALID_POS_ROLES",
    "VOWELS",
    "analyze_discourse_cues",
    "analyze_morphology",
    "bounded_edit_distance",
    "clean_definition_tail",
    "echo_input_syllables",
    "extract_meaning_query",
    "extract_query_target",
    "format_lexicon_qa_clauses",
    "infer_indonesian_pos",
    "is_question_or_empty_tail",
    "normalize_colloquial",
    "parse_teaching_or_correction",
    "realize_indonesian_clauses",
    "stem_candidates",
    "stem_word",
    "syllabify_indonesian",
    "synthesize_babble",
    "tokenize_phonemes",
]
