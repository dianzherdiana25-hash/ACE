"""Pelajari ringkasan ekstraktif dari anotasi kalimat dengan provenance.

Bobot kata berasal dari perbedaan tingkat kemunculan pada kalimat yang
dipilih dan dilewatkan. Kalimat diekspor persis dari sumber dalam urutan
dokumen dan tunduk pada anggaran karakter. Held-out menentukan
precision/recall ekstraksi pada anotasi yang tidak ikut fit.
"""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
import re
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_DOCUMENTS = 2000
MAX_SENTENCES = 250
MAX_VOCAB = 20_000
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text):
    return set(TOKEN.findall(unicodedata.normalize("NFC", text).casefold()))


def _document(row, refs):
    sentences, ids = [], set()
    for node in entries(row, MAX_SENTENCES):
        object_fields(node, ("id", "source_ref", "text"))
        key = reference(node["id"], ids, "ID kalimat")
        pointer = reference(node["source_ref"], refs, "rujukan kalimat")
        text = string(node["text"], "kalimat", max_chars=3000, preserve=True)
        words = _tokens(text)
        if not words:
            raise InputError("Kalimat memerlukan token yang dapat dibaca.")
        sentences.append({"id": key, "source_ref": pointer, "text": text, "tokens": words})
    if not sentences:
        raise InputError("Dokumen kosong.")
    return sentences, ids


def _documents(rows, recipe):
    grouped = {}
    ids, refs, content = set(), {recipe}, set()
    for row in entries(rows, MAX_DOCUMENTS):
        object_fields(row, ("id", "family_id", "split", "annotation_ref", "sentences", "selected_ids"))
        key = reference(row["id"], ids, "ID dokumen")
        annotation = reference(row["annotation_ref"], refs, "rujukan anotasi")
        family = string(row["family_id"], "keluarga dokumen")
        split = row["split"]
        if split not in ("train", "held_out"):
            raise InputError("Partisi dokumen tidak dikenal.")
        sentences, sentence_ids = _document(row["sentences"], refs)
        marks = set()
        for label in entries(row["selected_ids"], MAX_SENTENCES):
            reference(label, marks, "pilihan anotasi")
        if not marks or not marks <= sentence_ids:
            raise InputError("Anotasi harus menunjuk kalimat dokumen.")
        signature = identity([" ".join(sentence["text"].split()) for sentence in sentences])
        if signature in content:
            raise InputError("Teks dokumen diulang.")
        content.add(signature)
        grouped[key] = (family, split, annotation, sentences, marks)
    families = {}
    for family, split, *_ in grouped.values():
        if families.setdefault(family, split) != split:
            raise InputError("Keluarga dokumen dipakai lintas partisi.")
    return grouped


def _fit(documents):
    positive, negative = Counter(), Counter()
    positives = negatives = 0
    for _, split, _, sentences, marks in documents.values():
        if split != "train":
            continue
        for sentence in sentences:
            if sentence["id"] in marks:
                positives += 1
                positive.update(sentence["tokens"])
            else:
                negatives += 1
                negative.update(sentence["tokens"])
        if len(positive.keys() | negative.keys()) > MAX_VOCAB:
            raise InputError("Kosakata tempa melampaui batas.")
    if not positives or not negatives:
        raise InputError("Fit membutuhkan kalimat train dipilih dan dilewatkan.")
    # Selisih laju bersmoothing Laplace, tanpa bobot floating point.
    denominator = (positives + 2) * (negatives + 2)
    words = sorted(positive.keys() | negative.keys())
    weights = {word: (positive[word] + 1) * (negatives + 2) - (negative[word] + 1) * (positives + 2)
               for word in words}
    return {"schema": "ace.forge-extractive-lexicon.v1", "positive_sentences": positives,
            "negative_sentences": negatives, "denominator": denominator, "word_weights": weights}


def _choose(sentences, weights, budget, count):
    priorities = []
    for index, row in enumerate(sentences):
        hits = sum(weights.get(token, 0) for token in row["tokens"])
        if hits > 0:
            priorities.append((-Fraction(hits, len(row["tokens"])), index))
    chosen, used = [], 0
    for _, index in sorted(priorities):
        length = len(sentences[index]["text"]) + bool(chosen)
        if used + length <= budget:
            used += length
            chosen.append(index)
            if len(chosen) == count:
                break
    return [sentences[index] for index in sorted(chosen)], used


def _limits(raw):
    return integer(raw["maximum_chars"], 1, 25_000), integer(raw["maximum_sentences"], 1, MAX_SENTENCES)


def forge(raw, expected):
    object_fields(raw, ("recipe_ref", "maximum_chars", "maximum_sentences", "documents"))
    if identity(raw) != digest(expected):
        raise InputError("Snapshot anotasi berbeda dari anchor.")
    ref = string(raw["recipe_ref"], "rujukan resep")
    budget, cap = _limits(raw)
    docs = _documents(raw["documents"], ref)
    adapter = _fit(docs)
    held = []
    gold_count = predicted = matched = 0
    for key, (family, split, annotation, sentences, gold) in sorted(docs.items()):
        if split != "held_out":
            continue
        answer, used = _choose(sentences, adapter["word_weights"], budget, cap)
        found = {row["id"] for row in answer}
        gold_count += len(gold)
        predicted += len(found)
        matched += len(found & gold)
        held.append({"id": key, "family_id": family, "annotation_ref": annotation, "chars": used,
                     "selected": [{"id": row["id"], "source_ref": row["source_ref"]} for row in answer],
                     "gold_count": len(gold), "matched": len(found & gold)})
    return {"schema": "ace.forge-summarizer-receipt.v1", "recipe_ref": ref, "input_sha256": expected,
            "adapter": adapter, "adapter_sha256": identity(adapter), "held_out": held,
            "precision": _fraction(Fraction(matched, predicted)) if predicted else None,
            "recall": _fraction(Fraction(matched, gold_count)) if gold_count else None}


def summarize(raw, expected, adapter, expected_adapter):
    object_fields(raw, ("document_ref", "maximum_chars", "maximum_sentences", "sentences"))
    object_fields(adapter, ("schema", "positive_sentences", "negative_sentences", "denominator", "word_weights"))
    if identity(raw) != digest(expected) or identity(adapter) != digest(expected_adapter):
        raise InputError("Input ringkasan berbeda dari anchor.")
    if adapter["schema"] != "ace.forge-extractive-lexicon.v1":
        raise InputError("Skema adaptor tidak dikenal.")
    counts = [integer(adapter[key], 1, MAX_DOCUMENTS * MAX_SENTENCES)
              for key in ("positive_sentences", "negative_sentences")]
    denominator = (counts[0] + 2) * (counts[1] + 2)
    if type(adapter["denominator"]) is not int or adapter["denominator"] != denominator:
        raise InputError("Denominator adaptor tidak sesuai.")
    weights = adapter["word_weights"]
    if not isinstance(weights, dict) or not 1 <= len(weights) <= MAX_VOCAB:
        raise InputError("Tabel bobot leksikal tidak sah.")
    for word, weight in weights.items():
        if _tokens(string(word, "token", max_chars=3000)) != {word}:
            raise InputError("Token adaptor tidak kanonis.")
        integer(weight, -denominator, denominator)
    budget, cap = _limits(raw)
    pointer = string(raw["document_ref"], "rujukan dokumen")
    sentences, _ = _document(raw["sentences"], {pointer})
    chunks, used = _choose(sentences, weights, budget, cap)
    return {"schema": "ace.forge-extractive-summary.v1", "document_ref": pointer,
            "query_sha256": expected, "adapter_sha256": expected_adapter, "chars": used,
            "status": "selected" if chunks else "no_supported_selection",
            "sentences": [{key: value for key, value in row.items() if key != "tokens"} for row in chunks],
            "summary": "\n".join(row["text"] for row in chunks)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--expect-adapter-sha256")
    args = parser.parse_args(argv)
    if (args.adapter is None) != (args.expect_adapter_sha256 is None):
        parser.error("Adaptor dan anchor wajib dipasangkan.")
    try:
        raw = decode(read_bytes(args.input, MAX_BYTES))
        if args.adapter:
            report = summarize(raw, args.expect_input_sha256, decode(read_bytes(args.adapter, MAX_BYTES)),
                               args.expect_adapter_sha256)
        else:
            report = forge(raw, args.expect_input_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
