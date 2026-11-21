"""Tempa penerjemah frasa ID–EN dari pasangan yang disejajarkan.

Penopang terkuat harus unik sebelum frasa dipakai. Decoder memilih
segmentasi yang memberi cakupan token terbesar, lalu dukungan terbesar.
Bagian tanpa bukti tetap disalin dan ditandai. Petikan terjemahan
membawa rujukan pasangan latih tanpa membuat referensi baru.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import re
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


DIRECTIONS = ("en-id", "id-en")
MAX_ROWS = 3000
MAX_PHRASE = 8
MAX_TOKENS = 600
TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*|[^\w\s]", re.UNICODE)


def _key(text):
    normalized = unicodedata.normalize("NFC", text)
    return tuple(part.group().casefold() for part in TOKEN.finditer(normalized))


def _rows(raw, recipe):
    ids, refs, families, partitions = set(), {recipe}, {}, {}
    train, held = defaultdict(lambda: defaultdict(list)), []
    for row in entries(raw, MAX_ROWS):
        object_fields(row, ("id", "family_id", "split", "direction", "source", "target", "evidence_ref"))
        key = reference(row["id"], ids, "ID pasangan")
        proof = reference(row["evidence_ref"], refs, "rujukan pasangan")
        family = string(row["family_id"], "keluarga")
        split = row["split"]
        direction = row["direction"]
        if split not in ("train", "held_out") or families.setdefault(family, split) != split or direction not in DIRECTIONS:
            raise InputError("Partisi, arah, atau keluarga pasangan tidak sah.")
        source = string(row["source"], "frasa sumber", max_chars=5000, preserve=True)
        target = string(row["target"], "frasa target", max_chars=5000, preserve=True)
        left, right = _key(source), _key(target)
        if not 1 <= len(left) <= (MAX_PHRASE if split == "train" else MAX_TOKENS) or not 1 <= len(right) <= MAX_TOKENS:
            raise InputError("Panjang token pasangan di luar batas.")
        if partitions.setdefault((direction, left), split) != split:
            raise InputError("Frasa sumber identik ada di train dan held-out.")
        if split == "train":
            target = " ".join(unicodedata.normalize("NFC", target).split())
            train[direction, left][target].append(proof)
        else:
            held.append((key, direction, source, target, proof))
    if not train:
        raise InputError("Tempa penerjemah memerlukan pasangan train.")
    return train, held


def _decode(text, phrase_table):
    text = unicodedata.normalize("NFC", text)
    matches = list(TOKEN.finditer(text))
    if len(matches) > MAX_TOKENS:
        raise InputError("Masukan terjemah melampaui batas token.")
    tokens = _key(text)
    size = len(tokens)
    score = [(0, 0, 0)] * (size + 1)
    choices = [None] * size
    for index in range(size - 1, -1, -1):
        covered, support, neg_segments = score[index + 1]
        best = (covered, support, neg_segments - 1)
        selected = (index + 1, None)
        for end in range(index + 1, min(size, index + MAX_PHRASE) + 1):
            hit = phrase_table.get(tokens[index:end])
            if hit is None:
                continue
            words = sum(token[0].isalnum() for token in tokens[index:end])
            suffix = score[end]
            rank = (suffix[0] + words, suffix[1] + len(hit["evidence_refs"]), suffix[2] - 1)
            if rank > best:
                best, selected = rank, (end, hit)
        score[index], choices[index] = best, selected
    segments, pieces = [], []
    previous, index = 0, 0
    while index < size:
        end, hit = choices[index]
        start_pos, end_pos = matches[index].start(), matches[end-1].end()
        original = text[start_pos:end_pos]
        output = hit["target"] if hit is not None else original
        state = "translated" if hit is not None else "unresolved" if tokens[index][0].isalnum() else "punctuation"
        segments.append({"start": start_pos, "end": end_pos, "target": output, "status": state,
                         "evidence_refs": hit["evidence_refs"] if hit is not None else []})
        pieces.extend((text[previous:start_pos], output))
        previous, index = end_pos, end
    pieces.append(text[previous:])
    word_count = sum(token[0].isalnum() for token in tokens)
    return {"translation": "".join(pieces), "translated_words": score[0][0], "source_words": word_count,
            "coverage": _fraction(Fraction(score[0][0], word_count)) if word_count else None,
            "segments": segments, "offset_basis": "nfc_codepoints"}


def _phrase_table(raw):
    table, seen = defaultdict(dict), set()
    for row in entries(raw, MAX_ROWS):
        object_fields(row, ("direction", "tokens", "target", "evidence_refs"))
        direction = string(row["direction"], "arah")
        if direction not in DIRECTIONS:
            raise InputError("Arah kamus tidak sah.")
        source = tuple(string(token, "token frasa", max_chars=5000) for token in entries(row["tokens"], MAX_PHRASE))
        if not source or any(_key(part) != (part,) for part in source) or (direction, source) in seen:
            raise InputError("Token kamus tidak kanonis atau frasa ganda.")
        seen.add((direction, source))
        target = string(row["target"], "target frasa", max_chars=5000, preserve=True)
        refs = set()
        for ref in entries(row["evidence_refs"], MAX_ROWS):
            reference(ref, refs, "rujukan data latih")
        if not refs:
            raise InputError("Frasa kamus memerlukan bukti latih.")
        table[direction][source] = {"target": target, "evidence_refs": sorted(refs)}
    return table


def forge(raw, expected):
    object_fields(raw, ("recipe_ref", "minimum_support", "pairs"))
    if identity(raw) != digest(expected):
        raise InputError("Pasangan terjemah berbeda dari anchor.")
    recipe = string(raw["recipe_ref"], "rujukan resep")
    floor = integer(raw["minimum_support"], 1, MAX_ROWS)
    train, held = _rows(raw["pairs"], recipe)
    recorded, unresolved = [], []
    for (direction, tokens), candidates in sorted(train.items()):
        choices = sorted(candidates.items(), key=lambda row: (-len(row[1]), row[0]))
        target, refs = choices[0]
        tied = len(choices) > 1 and len(choices[1][1]) == len(refs)
        if tied or len(refs) < floor:
            unresolved.append({"direction": direction, "source_sha256": identity(tokens),
                               "reason": "tied" if tied else "insufficient_support", "support": len(refs)})
        else:
            recorded.append({"direction": direction, "tokens": list(tokens), "target": target,
                             "evidence_refs": sorted(refs)})
    table = _phrase_table(recorded)
    results = []
    for key, direction, source, target, proof in sorted(held):
        outcome = _decode(source, table[direction])
        results.append({"id": key, "direction": direction, "evidence_ref": proof, "coverage": outcome["coverage"],
                        "exact_token_match": _key(outcome["translation"]) == _key(target)})
    adapter = {"schema": "ace.forge-phrase-table.v1", "phrases": recorded}
    return {"schema": "ace.forge-translation-receipt.v1", "recipe_ref": recipe, "input_sha256": expected,
            "adapter": adapter, "adapter_sha256": identity(adapter), "unresolved_phrases": unresolved,
            "held_out": results, "held_out_exact_match": _fraction(Fraction(sum(row["exact_token_match"]
                for row in results), len(results))) if results else None}


def translate(raw, expected, adapter, expected_adapter):
    object_fields(raw, ("source_ref", "direction", "text"))
    object_fields(adapter, ("schema", "phrases"))
    if identity(raw) != digest(expected) or identity(adapter) != digest(expected_adapter):
        raise InputError("Query atau adaptor berbeda dari anchor.")
    if adapter["schema"] != "ace.forge-phrase-table.v1" or raw["direction"] not in DIRECTIONS:
        raise InputError("Arah atau skema penerjemah tidak dikenal.")
    source = string(raw["source_ref"], "rujukan masukan")
    text = string(raw["text"], "teks terjemah", max_chars=5000, preserve=True)
    table = _phrase_table(adapter["phrases"])
    return {"schema": "ace.forge-phrase-translation.v1", "source_ref": source,
            "query_sha256": expected, "adapter_sha256": expected_adapter, **_decode(text, table[raw["direction"]])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--expect-adapter-sha256")
    args = parser.parse_args(argv)
    if (args.adapter is None) != (args.expect_adapter_sha256 is None):
        parser.error("Adaptor dan anchor harus dipasangkan.")
    try:
        raw = decode(read_bytes(args.input, MAX_BYTES))
        if args.adapter:
            report = translate(raw, args.expect_input_sha256, decode(read_bytes(args.adapter, MAX_BYTES)),
                               args.expect_adapter_sha256)
        else:
            report = forge(raw, args.expect_input_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
