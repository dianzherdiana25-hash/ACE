"""Audit izin sumber dataset terhadap katalog kebijakan yang dideklarasikan.

Ekspresi lisensi ditafsirkan sebagai alternatif OR dan kombinasi AND.
WITH memerlukan entri pengecualian eksplisit. Semua kewajiban yang
dipilih perlu rujukan bukti, sehingga catatan yang kurang tetap
menunggu telaah. Report mencatat semua alternatif yang dievaluasi.
"""
import argparse
from collections import Counter
from pathlib import Path
import re
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS


MAX_ALTERNATIVES = 128
TOKEN = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9.+:-]*|[()])")
OPERATORS = {"AND", "OR", "WITH"}


class Expression:
    def __init__(self, text):
        self.tokens = []
        offset = 0
        while offset < len(text):
            match = TOKEN.match(text, offset)
            if match is None:
                raise InputError("Tanda pada ekspresi lisensi tidak dikenal.")
            self.tokens.append(match[1])
            offset = match.end()
        self.index = 0

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def pop(self, token=None):
        item = self.peek()
        if item is None or (token is not None and item != token):
            raise InputError("Susunan ekspresi lisensi tidak sah.")
        self.index += 1
        return item

    def term(self):
        item = self.pop()
        if item in OPERATORS or item in "()":
            raise InputError("ID lisensi atau pengecualian tidak sah.")
        return item

    def primary(self, depth):
        if depth >= 12:
            raise InputError("Ekspresi lisensi terlalu dalam.")
        if self.peek() == "(":
            self.pop()
            alternatives = self.expression(depth + 1)
            self.pop(")")
            return alternatives
        key = self.term()
        if self.peek() == "WITH":
            self.pop()
            key += " WITH " + self.term()
        return {frozenset((key,))}

    def product(self, depth):
        left = self.primary(depth)
        while self.peek() == "AND":
            self.pop()
            right = self.primary(depth)
            if len(left) * len(right) > MAX_ALTERNATIVES * 4:
                raise InputError("Kombinasi lisensi melampaui batas.")
            left = {first | second for first in left for second in right}
            self.check_cap(left)
        return left

    def expression(self, depth=0):
        left = self.product(depth)
        while self.peek() == "OR":
            self.pop()
            left |= self.product(depth)
            self.check_cap(left)
        return left

    @staticmethod
    def check_cap(alternatives):
        if len(alternatives) > MAX_ALTERNATIVES:
            raise InputError("Kombinasi lisensi melampaui batas.")


def alternatives(raw):
    expr = Expression(string(raw, "ekspresi lisensi"))
    values = expr.expression()
    if expr.peek() is not None:
        raise InputError("Token setelah akhir ekspresi lisensi.")
    return sorted(tuple(sorted(keys)) for keys in values)


def _policy(raw):
    object_fields(raw, ("policy_ref", "licenses"))
    policy = string(raw["policy_ref"], "rujukan katalog izin")
    catalog = {}
    for row in entries(raw["licenses"], 300):
        object_fields(row, ("term", "training", "obligations", "rule_ref"))
        term = string(row["term"], "term lisensi")
        options = alternatives(term)
        if len(options) != 1 or len(options[0]) != 1 or options[0][0] != term or term in catalog:
            raise InputError("Setiap entri katalog harus satu term lisensi unik.")
        training = row["training"]
        if training not in ("allow", "deny", "review"):
            raise InputError("Status izin latih tidak dikenal.")
        required = set()
        for value in entries(row["obligations"], 20):
            reference(value, required, "kewajiban lisensi")
        catalog[term] = (training, required, string(row["rule_ref"], "rujukan aturan lisensi"))
    if not catalog:
        raise InputError("Katalog izin kosong.")
    return policy, catalog


def _index(raw):
    object_fields(raw, ("index_ref", "sources"))
    index_ref = string(raw["index_ref"], "rujukan indeks sumber")
    known = {}
    for row in entries(raw["sources"], MAX_ROWS):
        object_fields(row, ("evidence_ref", "source_ref", "notices"))
        evidence = string(row["evidence_ref"], "rujukan verifikasi")
        if evidence in known:
            raise InputError("Rujukan verifikasi ganda dalam indeks lisensi.")
        notices = row["notices"]
        if not isinstance(notices, dict) or len(notices) > 60:
            raise InputError("Indeks notice perlu objek dengan batas entri.")
        normalized = {}
        for key, pointer in notices.items():
            label = string(key, "jenis notice")
            if label in normalized:
                raise InputError("Jenis notice ganda.")
            normalized[label] = string(pointer, "rujukan notice")
        known[evidence] = (string(row["source_ref"], "rujukan asal"), normalized)
    return index_ref, known


def _option(terms, catalog, source, notices):
    denied, unresolved, refs, required = [], [], {}, set()
    for term in terms:
        if term not in catalog:
            unresolved.append(term)
            continue
        status, obligations, pointer = catalog[term]
        refs[term] = pointer
        required.update(obligations)
        if status == "deny":
            denied.append(term)
        if status == "review":
            unresolved.append(term)
    missing = sorted(required - notices.keys())
    status = "blocked" if denied else "review" if unresolved or missing or source is None else "eligible"
    return {"terms": list(terms), "status": status, "denied_terms": denied, "unresolved_terms": unresolved,
            "rule_refs": refs, "missing_notices": missing, "notice_refs": {key: notices[key] for key in sorted(required)
                                                                        if key in notices}}


def audit(dataset, manifest, expected_head, policy, expected_policy, source_index):
    if not verify(dataset, manifest, expected_head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    if identity(policy) != digest(expected_policy):
        raise InputError("Kebijakan lisensi berbeda dari anchor.")
    source, catalog = _policy(policy)
    index_ref, index = _index(source_index)
    rows = []
    for line in dataset.splitlines():
        case = decode(line)
        evidence, expression = (case["provenance"][key] for key in ("evidence_ref", "license"))
        original, notices = index.get(evidence, (None, {}))
        try:
            options = [_option(terms, catalog, original, notices) for terms in alternatives(expression)]
        except InputError:
            options = []
        states = {item["status"] for item in options}
        status = "eligible" if "eligible" in states else "blocked" if states == {"blocked"} else "review"
        rows.append({"event_id": case["payload"]["event_id"], "expression": expression, "evidence_ref": evidence,
                     "source_ref": original, "status": status, "options": options,
                     "diagnostic": "invalid_expression" if not options else "unmapped_source" if original is None else None})
    return {"schema": "ace.forge-license-audit.v1", "policy_ref": source, "policy_sha256": expected_policy,
            "source_index_ref": index_ref, "source_index_sha256": identity(source_index), "dataset_head_sha256": expected_head,
            "counts": dict(sorted(Counter(row["status"] for row in rows).items())),
            "records": sorted(rows, key=lambda row: row["event_id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("source_index", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                       args.expect_head, decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256,
                       decode(read_bytes(args.source_index, MAX_BYTES)))
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(any(row["status"] != "eligible" for row in result["records"]))


if __name__ == "__main__":
    raise SystemExit(main())
