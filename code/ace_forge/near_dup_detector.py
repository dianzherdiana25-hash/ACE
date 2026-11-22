"""Temukan contoh nyaris sama lintas dataset dengan Jaccard token shingle.

Indeks token shingle mengajukan semua pasangan yang punya irisan.
Uji eksak berdasarkan ambang basis points memisahkan pasangan dan
cluster transitif. Report audit membawa rujukan kedua sisi dan
menyorot pasangan yang menyilang partisi train/held-out.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_DOCS = 5000
MAX_DATASETS = 80
MAX_TOKENS = 500
MAX_CANDIDATE_PAIRS = 200_000
MAX_POSTING_COMPARISONS = 2_000_000
TOKEN = re.compile(r"[^\W_]+(?:_[^\W_]+)*", re.UNICODE)


@dataclass(frozen=True, slots=True)
class Document:
    dataset: str
    key: str
    split: str
    ref: str
    shingles: frozenset

    @classmethod
    def read(cls, row, dataset, keys, width):
        object_fields(row, ("id", "prompt", "split", "source_ref"))
        identifier = reference(row["id"], keys, "ID contoh dalam dataset")
        split = string(row["split"], "partisi")
        if split not in ("train", "held_out", "candidate"):
            raise InputError("Partisi contoh tidak dikenal.")
        prompt = string(row["prompt"], "prompt", max_chars=12_000)
        normalized = unicodedata.normalize("NFKC", prompt).casefold()
        tokens = TOKEN.findall(normalized)
        if not 1 <= len(tokens) <= MAX_TOKENS:
            raise InputError("Prompt perlu token terbaca dan di bawah batas.")
        size = min(width, len(tokens))
        shingles = frozenset(tuple(tokens[i:i + size]) for i in range(len(tokens) - size + 1))
        return cls(dataset, identifier, split, string(row["source_ref"], "rujukan contoh"), shingles)

    def export(self):
        return {"dataset": self.dataset, "id": self.key, "split": self.split, "source_ref": self.ref}


def _groups(documents, matches):
    adjacent = defaultdict(set)
    for i, j in matches:
        adjacent[i].add(j)
        adjacent[j].add(i)
    seen = set()
    connected = []
    for root in sorted(adjacent):
        if root in seen:
            continue
        stack = [root]
        members = set()
        while stack:
            node = stack.pop()
            if node in members:
                continue
            members.add(node)
            stack.extend(adjacent[node] - members)
        seen.update(members)
        connected.append([documents[i].export() for i in sorted(members)])
    return connected


def scan(raw):
    object_fields(raw, ("protocol_ref", "shingle_width", "minimum_similarity_bp", "datasets"))
    reference_protocol = string(raw["protocol_ref"], "rujukan protokol")
    width = integer(raw["shingle_width"], 1, 8)
    cutoff = integer(raw["minimum_similarity_bp"], 1, 10_000)
    docs = []
    names = set()
    by_source = []
    for item in entries(raw["datasets"], MAX_DATASETS):
        object_fields(item, ("name", "source_ref", "rows"))
        name = reference(item["name"], names, "nama dataset")
        dataset_ref = string(item["source_ref"], "rujukan dataset")
        rows = entries(item["rows"], MAX_DOCS)
        if len(docs) + len(rows) > MAX_DOCS:
            raise InputError("Total contoh melebihi batas.")
        keys = set()
        docs.extend(Document.read(row, name, keys, width) for row in rows)
        by_source.append({"name": name, "source_ref": dataset_ref, "rows": len(rows),
                          "sha256": identity(sorted(rows, key=lambda row: row["id"]))})
    docs.sort(key=lambda doc: (doc.dataset, doc.key))
    postings = defaultdict(list)
    checks = 0
    pairs_checked = 0
    matches, edges = [], []
    for j, right in enumerate(docs):
        overlaps = defaultdict(int)
        for shingle in sorted(right.shingles):
            checks += len(postings[shingle])
            if checks > MAX_POSTING_COMPARISONS:
                raise InputError("Pemeriksaan indeks melebihi batas, kurangi ukuran corpus.")
            for i in postings[shingle]:
                if docs[i].dataset != right.dataset:
                    overlaps[i] += 1
            postings[shingle].append(j)
        pairs_checked += len(overlaps)
        if pairs_checked > MAX_CANDIDATE_PAIRS:
            raise InputError("Pasangan kandidat melebihi batas, kurangi ukuran corpus.")
        for i, shared in sorted(overlaps.items()):
            left = docs[i]
            union = len(left.shingles) + len(right.shingles) - shared
            if shared * 10_000 < cutoff * union:
                continue
            crossed = {left.split, right.split} == {"train", "held_out"}
            matches.append({"left": left.export(), "right": right.export(), "shared_shingles": shared,
                            "union_shingles": union, "similarity": _fraction(Fraction(shared, union)),
                            "crosses_train_held_out": crossed})
            edges.append((i, j))
    matches.sort(key=lambda row: (row["left"]["dataset"], row["left"]["id"], row["right"]["dataset"], row["right"]["id"]))
    return {"schema": "ace.forge-near-duplicate.v1", "protocol_ref": reference_protocol, "minimum_similarity_bp": cutoff,
            "shingle_width": width, "datasets": sorted(by_source, key=lambda row: row["name"]),
            "pairs_checked": pairs_checked, "cross_partition_pairs": sum(row["crosses_train_held_out"] for row in matches),
            "matches": matches, "connected_components": _groups(docs, edges)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        report = scan(decode(read_bytes(args.input, MAX_BYTES)))
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
