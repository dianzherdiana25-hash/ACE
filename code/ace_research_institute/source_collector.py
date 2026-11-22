"""Saring kumpulan sumber lokal dengan custody, relevansi, dan kemandirian yang eksplisit."""
from hashlib import sha256

from ._contracts import ResearchError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text, words


KINDS = {"preregistered": 18, "peer_reviewed": 15, "official_series": 14,
         "technical_report": 10, "preprint": 6, "commentary": 0}


def _source(row, as_of, topics, max_age, root):
    obj(row, ("id", "path", "sha256", "title", "published", "kind", "independence_group", "declared_topics",
              "methods_ref", "data_ref", "license_ref"))
    key = identifier(row["id"], "ID sumber")
    group = identifier(row["independence_group"], "Grup sumber")
    source = text(row["title"], "Judul sumber")
    if row["kind"] not in KINDS:
        raise ResearchError("Kelas sumber belum didukung.")
    published = day(row["published"])
    the_age = (as_of - published).days
    declared = set()
    for term in items(row["declared_topics"], 30, 1):
        declared.update(words(text(term, "Topik yang dinyatakan", 100)))
    methods = None if row["methods_ref"] is None else text(row["methods_ref"], "Pointer metode")
    data = None if row["data_ref"] is None else text(row["data_ref"], "Pointer data")
    license_ref = None if row["license_ref"] is None else text(row["license_ref"], "Pointer lisensi")
    raw = source_bytes(root, row["path"], row["sha256"])
    content = raw.decode("utf-8")
    evidence_terms = set()
    matched_lines = []
    for line, line_text in enumerate(content.splitlines(), 1):
        overlap = words(line_text) & topics
        if overlap:
            evidence_terms.update(overlap)
            if len(matched_lines) < 8:
                matched_lines.append({"line": line, "terms": sorted(overlap)})
    overlap = evidence_terms & declared
    checks = {"source_kind": KINDS[row["kind"]], "methods_ref": 20 if methods else 0,
              "data_ref": 20 if data else 0, "license_ref": 10 if license_ref else 0,
              "relevance": 25 * len(overlap) // len(topics),
              "currency": 7 if 0 <= the_age <= max_age else 0}
    reasons = []
    if not overlap:
        reasons.append("no_declared_topic_observed")
    if the_age < 0:
        reasons.append("future_date")
    elif the_age > max_age:
        reasons.append("stale_source")
    if row["kind"] == "commentary":
        reasons.append("commentary_only")
    if not methods:
        reasons.append("methods_not_pointed")
    return {"id": key, "title": source, "independence_group": group, "path": row["path"], "sha256": sha256(raw).hexdigest(),
            "memberships": sorted(overlap), "supporting_lines": matched_lines, "published": row["published"],
            "kind": row["kind"], "age_days": the_age, "score": sum(checks.values()), "score_components": checks,
            "methods_ref": methods, "data_ref": data, "license_ref": license_ref, "hold_reasons": reasons}


def collect(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.source-plan.v1", ("topics", "as_of", "max_age_days", "minimum_score", "sources"))
    as_of = day(plan["as_of"])
    maximum_age = integer(plan["max_age_days"], "Umur maksimum sumber", 0, 36500)
    threshold = integer(plan["minimum_score"], "Ambang kredibilitas", 0, 100)
    topics = set()
    for term in items(plan["topics"], 20, 1):
        topics.update(words(text(term, "Topik", 110)))
    if not topics:
        raise ResearchError("Topik tidak memiliki kata indeks.")
    output = []
    known = set()
    unique = set()
    for row in items(plan["sources"], 150, 1):
        item = _source(row, as_of, topics, maximum_age, root)
        if item["id"] in known:
            raise ResearchError("ID sumber ganda.")
        known.add(item["id"])
        if item["score"] < threshold:
            item["hold_reasons"].append("insufficient_score")
        if item["sha256"] in unique:
            item["hold_reasons"].append("duplicate_source_bytes")
        elif not item["hold_reasons"]:
            unique.add(item["sha256"])
        output.append(item)
    output.sort(key=lambda item: (bool(item["hold_reasons"]), -item["score"], item["id"]))
    admitted = [row for row in output if not row["hold_reasons"]]
    groups = sorted({row["independence_group"] for row in admitted})
    return {"schema": "ace.institute.source-register.v1", "plan_sha256": expected, "as_of": plan["as_of"],
            "topics": sorted(topics), "independent_groups_admitted": groups, "admitted": len(admitted),
            "held": len(output) - len(admitted), "sources": output}


if __name__ == "__main__":
    raise SystemExit(cli(collect, __doc__, rooted=True))
