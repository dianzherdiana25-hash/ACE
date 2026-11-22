"""Bandingkan revisi dengan tujuan penulis, umpan balik, dan elemen wajib yang harus bertahan."""
from difflib import SequenceMatcher
from hashlib import sha256
import re

from ._contracts import (ProductionError, anchor, cli, identifier, integer,
                         items, obj, schema, source_bytes, text)


TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _document(row, root):
    obj(row, ("path", "sha256"))
    source = source_bytes(root, row["path"], row["sha256"], 120000)
    lines = [line.strip() for line in source.decode("utf-8").splitlines()]
    if len(lines) > 500 or not any(lines):
        raise ProductionError("Draf tulisan perlu isi di bawah batas 500 baris.")
    return lines


def review_revision(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.writing-revision-plan.v1", ("before", "after", "max_words", "required", "feedback"))
    initial = _document(plan["before"], root)
    revised = _document(plan["after"], root)
    length = integer(plan["max_words"], "Batas kata", 1, 20000)
    body = "\n".join(revised)
    words = len(TOKEN.findall(body))
    rules = {}
    for row in items(plan["required"], 70, 1):
        obj(row, ("id", "must_remain", "source_ref"))
        key = identifier(row["id"], "Syarat tulisan")
        if key in rules:
            raise ProductionError("Syarat revisi ganda.")
        snippet = text(row["must_remain"], "Frasa wajib", 150)
        pointer = text(row["source_ref"], "Pointer syarat")
        rules[key] = {"id": key, "before": any(snippet in line for line in initial),
                      "after": any(snippet in line for line in revised), "source_ref": pointer}
    comments = []
    observed = set()
    for row in items(plan["feedback"], 70):
        obj(row, ("id", "line", "prompt", "source_ref"))
        key = identifier(row["id"], "Umpan balik reviewer")
        if key in observed:
            raise ProductionError("ID umpan balik berulang.")
        observed.add(key)
        line = integer(row["line"], "Baris draf awal", 1, len(initial))
        comments.append({"id": key, "line": line, "directive": text(row["prompt"], "Umpan balik revisi"),
                         "source_ref": text(row["source_ref"], "Pointer umpan balik")})
    changes = []
    spans = SequenceMatcher(a=initial, b=revised, autojunk=False).get_opcodes()
    for tag, i, j, k, l in spans:
        if tag == "equal":
            continue
        changes.append({"operation": tag, "before_lines": [i + 1, j + 1], "after_lines": [k + 1, l + 1],
                        "before_sha256": sha256("\n".join(initial[i:j]).encode()).hexdigest(),
                        "after_sha256": sha256("\n".join(revised[k:l]).encode()).hexdigest(),
                        "related_feedback": [row["id"] for row in comments if i < row["line"] <= j]})
    blockers = [key for key, row in sorted(rules.items()) if not row["after"]]
    followed = {key for change in changes for key in change["related_feedback"]}
    return {"schema": "ace.teaching.writing-revision.v1", "plan_sha256": expected, "before": plan["before"], "after": plan["after"],
            "word_count": words, "word_limit": length, "changes": changes, "required_elements": list(rules.values()),
            "blockers": blockers + (["word_limit"] if words > length else []), "feedback": comments,
            "feedback_outside_changed_lines": sorted(observed - followed)}


if __name__ == "__main__":
    raise SystemExit(cli(review_revision, __doc__, rooted=True))
