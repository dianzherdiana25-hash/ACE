"""Nilai jawaban probe yang direkam terhadap kunci berkomitmen.

Probe dikelompokkan per domain dan memakai daftar jawaban yang bisa
dicek secara mekanis. Kasus tanpa receipt tetap missing. Laporan
memuat hasil per kasus dan coverage tanpa menyalin jawaban atau kunci
held-out, sehingga bisa dipakai untuk telaah lintas artefak.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_PROBES = 18_000
MAX_INTEGER = 10**12
INTEGER_TEXT = re.compile(r"(?:0|-?[1-9][0-9]{0,12})")


def _fold(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@dataclass(frozen=True, slots=True)
class Question:
    key: str
    domain: str
    pointer: str
    mode: str
    accepted: frozenset

    @classmethod
    def read(cls, raw, ids, refs):
        object_fields(raw, ("id", "domain", "prompt_ref", "mode", "answers"))
        mode = raw["mode"]
        if mode not in ("integer", "exact", "folded_text"):
            raise InputError("Mode penilai probe tidak dikenal.")
        choices = []
        for item in entries(raw["answers"], 50):
            if mode == "integer":
                value = str(integer(item, -MAX_INTEGER, MAX_INTEGER))
            else:
                value = string(item, "kunci probe", max_chars=512, preserve=True)
                if mode == "folded_text":
                    value = _fold(value)
            choices.append(value)
        if not choices or len(set(choices)) != len(choices):
            raise InputError("Kunci probe harus terisi dan unik setelah normalisasi.")
        return cls(reference(raw["id"], ids, "ID probe"), string(raw["domain"], "domain"),
                   reference(raw["prompt_ref"], refs, "rujukan prompt"), mode, frozenset(choices))

    def grade(self, response):
        if not isinstance(response, str) or len(response) > 2000 or not response.strip() or "\x00" in response:
            return "invalid_format"
        if self.mode == "folded_text":
            value = _fold(response)
        elif self.mode == "integer":
            value = response.strip()
            if not INTEGER_TEXT.fullmatch(value) or abs(int(value)) > MAX_INTEGER:
                return "invalid_format"
        else:
            value = response
        return "correct" if value in self.accepted else "incorrect"


def _aggregate(rows, minimum):
    counts = Counter(row["outcome"] for row in rows)
    observed = len(rows) - counts["missing"]
    return {"questions": len(rows), "observed": observed, "correct": counts["correct"],
            "incorrect": counts["incorrect"], "invalid_format": counts["invalid_format"], "missing": counts["missing"],
            "coverage": _fraction(Fraction(observed, len(rows))) if rows else None,
            "accuracy": _fraction(Fraction(counts["correct"], observed)) if observed >= minimum else None,
            "status": "scored" if observed >= minimum else "insufficient_observations"}


def _macro(domains):
    comparable = [Fraction(**row["accuracy"]) for row in domains if row["accuracy"] is not None]
    if not comparable:
        return {"scored_domains": 0, "unknown_domains": len(domains), "mean_accuracy": None,
                "minimum_accuracy": None, "maximum_accuracy": None}
    return {"scored_domains": len(comparable), "unknown_domains": len(domains) - len(comparable),
            "mean_accuracy": _fraction(sum(comparable) / len(comparable)),
            "minimum_accuracy": _fraction(min(comparable)), "maximum_accuracy": _fraction(max(comparable))}


def probe(protocol, observations, expected_protocol):
    object_fields(protocol, ("protocol_ref", "artifact_sha256", "minimum_observed", "questions"))
    if identity(protocol) != digest(expected_protocol):
        raise InputError("Protokol probe atau kunci berbeda dari anchor.")
    source = string(protocol["protocol_ref"], "rujukan protokol")
    artifact = digest(protocol["artifact_sha256"])
    minimum = integer(protocol["minimum_observed"], 1, MAX_PROBES)
    question_ids, refs = set(), {source}
    questions = {item.key: item for item in (Question.read(raw, question_ids, refs)
                                             for raw in entries(protocol["questions"], MAX_PROBES))}
    if not questions:
        raise InputError("Protokol perlu setidaknya satu pertanyaan.")
    answered = {}
    for row in entries(observations, MAX_PROBES):
        object_fields(row, ("id", "artifact_sha256", "response", "receipt_ref"))
        key = string(row["id"], "ID hasil probe")
        if key not in questions or key in answered or digest(row["artifact_sha256"]) != artifact:
            raise InputError("Receipt probe duplikat, di luar roster, atau memakai artefak berbeda.")
        answered[key] = (questions[key].grade(row["response"]), reference(row["receipt_ref"], refs, "rujukan receipt"))
    records, groups = [], defaultdict(list)
    for key, question in sorted(questions.items()):
        verdict, proof = answered.get(key, ("missing", None))
        result = {"id": key, "domain": question.domain, "mode": question.mode,
                  "prompt_ref": question.pointer, "receipt_ref": proof, "outcome": verdict}
        records.append(result)
        groups[question.domain].append(result)
    domains = [{"domain": domain, **_aggregate(rows, minimum)} for domain, rows in sorted(groups.items())]
    return {"schema": "ace.forge-knowledge-probe.v1", "protocol_ref": source, "protocol_sha256": expected_protocol,
            "artifact_sha256": artifact, "observation_sha256": identity(observations),
            "summary": _aggregate(records, minimum), "macro": _macro(domains), "domains": domains,
            "records": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = probe(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                       args.expect_protocol_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
