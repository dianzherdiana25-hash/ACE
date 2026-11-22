"""Lacak perubahan tiap klaim sepanjang riwayat laporan ber-anchor dan tanggal yang tegas."""
from collections import defaultdict
from hashlib import sha256

from ._contracts import (ResearchError, anchor, cli, day, decode, digest,
                         identifier, items, obj, schema, source_bytes, text)


def evolution(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.claim-history-plan.v1", ("history",))
    projected = []
    seen = set()
    question = None
    for row in items(plan["history"], 90, 1):
        obj(row, ("date", "id", "path", "sha256"))
        published = day(row["date"])
        key = identifier(row["id"], "Versi")
        if key in seen:
            raise ResearchError("Identitas versi laporan ganda.")
        seen.add(key)
        raw = source_bytes(root, row["path"], row["sha256"], 3_000_000)
        revision = decode(raw)
        schema(revision, "ace.institute.deep-report.v1", ("plan_sha256", "claim_check_sha256", "title", "question",
                "sections", "limitations", "summary", "sources", "markdown_sha256", "markdown"))
        if sha256(revision["markdown"].encode()).hexdigest() != digest(revision["markdown_sha256"]):
            raise ResearchError("Badan laporan berbeda dari hash.")
        origin = text(revision["question"], "Pertanyaan laporan")
        if question is not None and question != origin:
            raise ResearchError("Versi riwayat harus menjawab pertanyaan sama.")
        question = origin
        claims = {}
        for section in items(revision["sections"], 30, 1):
            for card in items(section["claims"], 80, 1):
                identity = identifier(card["id"], "Klaim")
                if identity in claims:
                    raise ResearchError("Klaim pada satu versi ganda.")
                claims[identity] = {"status": card["status"], "scope": card["dimensions"], "amount": card["amount"],
                                    "evidence": sorted({(ref["path"], ref["line"], ref["sha256"]) for ref in card["sources"]})}
        projected.append((published, key, row, claims))
    ordered = sorted(projected)
    paths = defaultdict(list)
    former = {}
    transitions = []
    for date, key, reference, current in ordered:
        for name in sorted(former.keys() | current.keys()):
            before, after = former.get(name), current.get(name)
            status = None if after is None else after["status"]
            if before != after:
                changed = (["added" if before is None else "removed"] if after is None or before is None else
                           sorted(field for field in before if before[field] != after[field]))
                event = {"version": key, "date": date.isoformat(), "claim": name, "status": status,
                         "previous_status": None if before is None else before["status"], "changed": changed,
                         "report": {"path": reference["path"], "sha256": reference["sha256"]}}
                paths[name].append(event)
                transitions.append(event)
        former = current
    return {"schema": "ace.institute.claim-history.v1", "plan_sha256": expected, "question": question,
            "ordered_versions": [row[1] for row in ordered], "transitions": transitions,
            "latest": {name: row["status"] for name, row in sorted(former.items())}, "timeline": dict(sorted(paths.items()))}


if __name__ == "__main__":
    raise SystemExit(cli(evolution, __doc__, rooted=True))
