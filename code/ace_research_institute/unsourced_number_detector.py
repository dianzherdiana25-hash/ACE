"""Temukan angka draf tanpa sitasi yang dapat diikuti, sebelum verifikasi nilai dilakukan."""
from collections import defaultdict

from ._contracts import (ResearchError, anchor, cli, identifier, integer,
                         items, obj, schema, source_bytes)
from .number_provenance import scan_prose


def locate_unsourced(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.unsourced-number-plan.v1", ("draft", "references", "annotations"))
    draft = obj(plan["draft"], ("path", "sha256"))
    content = source_bytes(root, draft["path"], draft["sha256"], 500000).decode("utf-8")
    numbers = dict(scan_prose(content))
    if len(numbers) > 1500:
        raise ResearchError("Draf terlalu banyak angka untuk audit.")
    known = {}
    for row in items(plan["references"], 250):
        obj(row, ("id", "path", "sha256", "line"))
        key = identifier(row["id"], "Rujukan prosa")
        if key in known:
            raise ResearchError("ID rujukan ganda.")
        source = source_bytes(root, row["path"], row["sha256"], 250000).decode("utf-8").splitlines()
        line = integer(row["line"], "Baris rujukan", 1, len(source))
        known[key] = {"path": row["path"], "sha256": row["sha256"], "line": line,
                      "nonempty": bool(source[line - 1].strip())}
    pointers = defaultdict(set)
    for row in items(plan["annotations"], 2500):
        obj(row, ("line", "column", "ref"))
        slot = (integer(row["line"], "Baris angka", 1, 500000), integer(row["column"], "Kolom angka", 1, 500000))
        pointers[slot].add(identifier(row["ref"], "ID sitasi"))
    results = []
    for (line, column), (raw, _, _) in sorted(numbers.items()):
        refs = sorted(pointers[line, column])
        linked = [known[ref] for ref in refs if ref in known and known[ref]["nonempty"]]
        if not linked:
            reason = "missing_annotation" if not refs else "no_resolvable_pointer"
            results.append({"line": line, "column": column, "token": raw, "reason": reason, "ref_ids": refs})
    unmatched = [{"line": line, "column": column} for line, column in sorted(
        {key for key, value in pointers.items() if value} - numbers.keys())]
    return {"schema": "ace.institute.unsourced-number-report.v1", "plan_sha256": expected,
            "draft": draft, "audit_scope": "citation_presence_only",
            "numbers_found": len(numbers), "without_pointer": results, "unmatched_annotations": unmatched}


if __name__ == "__main__":
    raise SystemExit(cli(locate_unsourced, __doc__, rooted=True))
