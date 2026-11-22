"""Nilai jawaban terbuka dari rubrik istilah yang eksplisit dan jelaskan kredit tiap kriteria."""
import re
import unicodedata

from ._contracts import ProductionError, anchor, cli, identifier, integer, items, obj, schema, text


def _clean(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _terms(raw):
    found = []
    for phrase in items(raw, 25):
        literal = _clean(text(phrase, "Frasa rubrik", 70))
        found.append((literal, re.compile(r"(?<!\w)" + re.escape(literal) + r"(?!\w)")))
    if len({label for label, _ in found}) != len(found):
        raise ProductionError("Frasa rubrik duplikat.")
    return found


def assess(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.open-grade-plan.v1", ("exercise", "response", "criteria", "passing_bp"))
    exercise = identifier(plan["exercise"], "Latihan")
    reply = obj(plan["response"], ("text", "source_ref"))
    response = _clean(text(reply["text"], "Jawaban terbuka", 5000))
    pointer = text(reply["source_ref"], "Pointer jawaban")
    cutoff = integer(plan["passing_bp"], "Ambang lulus", 1, 10000)
    output = []
    known = set()
    for rule in items(plan["criteria"], 65, 1):
        obj(rule, ("id", "weight", "hits_needed", "must_mention", "contradictions", "source_ref"))
        key = identifier(rule["id"], "Kriteria")
        if key in known:
            raise ProductionError("Kriteria penilaian duplikat.")
        known.add(key)
        threshold = integer(rule["weight"], "Bobot", 1, 10000)
        indicators = _terms(rule["must_mention"])
        hazards = _terms(rule["contradictions"])
        minimum = integer(rule["hits_needed"], "Frasa minimum", 1, len(indicators))
        observed = [label for label, pattern in indicators if pattern.search(response)]
        counter = [label for label, pattern in hazards if pattern.search(response)]
        credited = 0 if counter else threshold * min(len(observed), minimum) // minimum
        output.append({"id": key, "weight_bp": threshold, "earned_bp": credited, "hit": observed, "opposed_by": counter,
                       "minimum_hits": minimum, "source_ref": text(rule["source_ref"], "Pointer rubrik"),
                       "status": "contradiction" if counter else ("met" if len(observed) >= minimum else "partial_or_missing")})
    if sum(row["weight_bp"] for row in output) != 10000:
        raise ProductionError("Rubrik perlu bobot total 10.000 basis point.")
    score = sum(row["earned_bp"] for row in output)
    return {"schema": "ace.teaching.open-grade.v1", "plan_sha256": expected, "exercise": exercise,
            "response_source": pointer, "method": "explicit_literal_phrase_rubric",
            "score_bp": score, "criteria": output, "status": "passes_rubric" if score >= cutoff else "needs_review"}


if __name__ == "__main__":
    raise SystemExit(cli(assess, __doc__))
