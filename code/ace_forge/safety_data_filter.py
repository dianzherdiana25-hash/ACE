"""Saring calon data dengan kebijakan eksplisit sebelum tahap promosi.

Pencocokan frasa bertoken mendukung aturan bidang prompt atau target.
Pemeriksa bawaan mengenali beberapa bentuk umum konten sensitif. Report
membawa ID aturan dan bidang yang cocok tanpa menyalin teks atau nilai.
Keluaran filtered hanya berisi kandidat yang lolos kebijakan mekanis.
"""
import argparse
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES, MAX_ROWS, Source


BUILTINS = {
    "email_marker": re.compile(r"\b[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,120}\.[a-z]{2,32}\b", re.I),
    "private_key_marker": re.compile(r"-----BEGIN(?: [A-Z0-9]{1,12}){0,3} PRIVATE KEY-----", re.I),
    "credential_assignment": re.compile(r"\b(?:password|api[_ -]?key|access[_ -]?token|secret[_ -]?token)\s*[:=]\s*\S{4,}", re.I),
}
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
FIELDS = ("prompt", "target")


def _normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


@dataclass(slots=True)
class Node:
    edges: dict = field(default_factory=dict)
    suffix: int = 0
    rules: set = field(default_factory=set)


def _automaton(phrases):
    nodes = [Node()]
    for tokens, label in phrases:
        node = 0
        for token in tokens:
            child = nodes[node].edges.get(token)
            if child is None:
                child = len(nodes)
                nodes[node].edges[token] = child
                nodes.append(Node())
            node = child
        nodes[node].rules.add(label)
    pending = deque(nodes[0].edges.values())
    while pending:
        index = pending.popleft()
        for token, child in nodes[index].edges.items():
            fallback = nodes[index].suffix
            while fallback and token not in nodes[fallback].edges:
                fallback = nodes[fallback].suffix
            nodes[child].suffix = nodes[fallback].edges.get(token, 0)
            nodes[child].rules.update(nodes[nodes[child].suffix].rules)
            pending.append(child)
    return nodes


def _matched(nodes, text):
    result = set()
    index = 0
    for token in TOKEN.findall(text):
        while index and token not in nodes[index].edges:
            index = nodes[index].suffix
        index = nodes[index].edges.get(token, 0)
        result.update(nodes[index].rules)
    return result


def _policy(raw):
    object_fields(raw, ("policy_ref", "rules", "builtin_checks"))
    pointer = string(raw["policy_ref"], "rujukan kebijakan")
    builtin_names = set()
    for name in entries(raw["builtin_checks"], len(BUILTINS)):
        if reference(name, builtin_names, "pemeriksaan bawaan") not in BUILTINS:
            raise InputError("Pemeriksaan bawaan tidak dikenal.")
    used = set(BUILTINS)
    directory = {}
    times = []
    for row in entries(raw["rules"], 200):
        object_fields(row, ("id", "scope", "phrases"))
        key = reference(row["id"], used, "ID aturan")
        scope = row["scope"]
        if scope not in ("both", *FIELDS):
            raise InputError("Scope aturan tidak dikenal.")
        phrases = entries(row["phrases"], 30)
        if not phrases:
            raise InputError("Aturan memerlukan setidaknya satu frasa.")
        seen = set()
        for entry in phrases:
            line = string(entry, "frasa aturan", max_chars=200)
            normalized = tuple(TOKEN.findall(_normalize(line)))
            if not 1 <= len(normalized) <= 20 or normalized in seen:
                raise InputError("Frasa aturan kosong setelah normalisasi, terlalu panjang, atau ganda.")
            times.append((normalized, key))
            seen.add(normalized)
        directory[key] = scope
    if not directory and not builtin_names:
        raise InputError("Tidak ada pemeriksaan yang diaktifkan.")
    compiled = {field: _automaton((tokens, name) for tokens, name in times if directory[name] in ("both", field))
                for field in FIELDS}
    return pointer, compiled, builtin_names


def filter_candidates(raw, policy, expected_policy_sha256):
    if identity(policy) != digest(expected_policy_sha256):
        raise InputError("Kebijakan penyaringan berbeda dari anchor.")
    object_fields(raw, ("examples", "seed", "held_out_basis_points", "allowed_licenses"))
    pointer, matchers, builtins = _policy(policy)
    seed = integer(raw["seed"], 0, 2**64 - 1)
    held_out = integer(raw["held_out_basis_points"], 0, 10_000)
    licenses = set()
    for value in entries(raw["allowed_licenses"], 100):
        reference(value, licenses, "lisensi")
    if not licenses:
        raise InputError("Masukan harus mendeklarasikan lisensi kandidat.")
    seen = set()
    allowed, findings = [], []
    for example in entries(raw["examples"], MAX_ROWS):
        row = Source.read(example)
        if row.event_id in seen:
            raise InputError("ID contoh ganda.")
        seen.add(row.event_id)
        hits = []
        for field, content in (("prompt", row.prompt), ("target", row.target)):
            text = _normalize(content)
            labels = _matched(matchers[field], text)
            labels.update(key for key in builtins if BUILTINS[key].search(text))
            hits.extend({"rule_id": key, "field": field} for key in sorted(labels))
        if hits:
            findings.append({"event_id": row.event_id, "task_kind": row.task_kind, "findings": hits})
        else:
            allowed.append(row.export())
    allowed.sort(key=lambda row: row["event_id"])
    findings.sort(key=lambda row: row["event_id"])
    counts = Counter(tag["rule_id"] for row in findings for tag in row["findings"])
    report = {"schema": "ace.forge-safety-filter.v1", "policy_ref": pointer, "policy_sha256": expected_policy_sha256,
              "examples": len(seen), "passed": len(allowed), "held": len(findings), "rule_field_hits": dict(sorted(counts.items())),
              "findings": findings}
    filtered = {"seed": seed, "held_out_basis_points": held_out, "allowed_licenses": sorted(licenses), "examples": allowed}
    return filtered, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--expect-policy-sha256", required=True)
    parser.add_argument("--filtered", action="store_true", help="Cetak kandidat yang lolos untuk tahap berikutnya.")
    args = parser.parse_args(argv)
    try:
        filtered, report = filter_candidates(decode(read_bytes(args.candidates, MAX_BYTES)),
                                             decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256)
        sys.stdout.write(canonical(filtered if args.filtered else report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
