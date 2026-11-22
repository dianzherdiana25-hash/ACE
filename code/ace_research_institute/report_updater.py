"""Turunkan revisi laporan dari bukti terbaru dan catat delta tanpa mengubah riwayat."""
from hashlib import sha256

from ._contracts import ResearchError, anchor, cli, decode, identity, obj, schema, source_bytes
from .deep_report_writer import make_report


def _flatten(report):
    found = {}
    for section in report["sections"]:
        for claim in section["claims"]:
            key = claim["id"]
            if key in found:
                raise ResearchError("Laporan mengandung identitas klaim ganda.")
            found[key] = {"section": section["id"], "status": claim["status"], "dimensions": claim["dimensions"],
                          "amount": claim["amount"], "sources": sorted((item["path"], item["line"], item["sha256"])
                                                                        for item in claim["sources"])}
    return found


def update(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.update-plan.v1", ("previous", "new_plan"))
    pointer = obj(plan["previous"], ("path", "sha256"))
    past = decode(source_bytes(root, pointer["path"], pointer["sha256"], 3_000_000))
    schema(past, "ace.institute.deep-report.v1", ("plan_sha256", "claim_check_sha256", "title", "question",
                                                  "sections", "limitations", "summary", "sources", "markdown_sha256", "markdown"))
    if not isinstance(past["markdown"], str) or sha256(past["markdown"].encode()).hexdigest() != past["markdown_sha256"]:
        raise ResearchError("Dokumen sebelumnya tidak sesuai hash Markdown.")
    revised = make_report(plan["new_plan"], identity(plan["new_plan"]), root)
    if past["question"] != revised["question"]:
        raise ResearchError("Pandangan revisi membutuhkan pertanyaan yang sama.")
    older, newer = _flatten(past), _flatten(revised)
    combined = []
    for key in sorted(older.keys() | newer.keys()):
        left, right = older.get(key), newer.get(key)
        if left == right:
            continue
        if left is None or right is None:
            state = "added" if left is None else "removed"
            fields = []
        else:
            state = "changed"
            fields = sorted(name for name in left if left[name] != right[name])
        combined.append({"id": key, "type": state, "changed_fields": fields, "before": left, "after": right})
    return {"schema": "ace.institute.report-revision.v1", "plan_sha256": expected,
            "previous": pointer, "new_report_sha256": identity(revised), "change_list": combined,
            "unchanged_claims": sum(older.get(key) == newer.get(key) for key in older.keys() & newer.keys()),
            "new_report": revised}


if __name__ == "__main__":
    raise SystemExit(cli(update, __doc__, rooted=True))
