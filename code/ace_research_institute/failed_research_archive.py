"""Susun indeks draf kegagalan riset dengan kutipan sebab, hasil dan jejak metode."""
from ._contracts import ResearchError, anchor, cli, day, identifier, integer, items, obj, schema, source_bytes, text


STATES = ("null", "invalid_protocol", "insufficient_data", "replication_failed", "abandoned_with_evidence")


def index_failed(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.failed-archive-plan.v1", ("entries",))
    index = {}
    for row in items(plan["entries"], 220, 1):
        obj(row, ("id", "question", "closed_at", "failure_class", "report", "protocol", "notes"))
        key = identifier(row["id"], "Studi")
        if key in index or row["failure_class"] not in STATES:
            raise ResearchError("ID studi ganda atau kelas gagal tidak dikenal.")
        closed_at = day(row["closed_at"])
        protocol = obj(row["protocol"], ("path", "sha256"))
        source_bytes(root, protocol["path"], protocol["sha256"])
        proof = obj(row["report"], ("path", "sha256", "line", "excerpt"))
        lines = source_bytes(root, proof["path"], proof["sha256"]).decode("utf-8").splitlines()
        line = integer(proof["line"], "Baris hasil", 1, len(lines))
        excerpt = text(proof["excerpt"], "Kutipan hasil", 600)
        if excerpt not in lines[line - 1]:
            raise ResearchError("Kutipan kegagalan tidak ditemukan di sumber.")
        notes = []
        for item in items(row["notes"], 25, 1):
            obj(item, ("line", "reason", "excerpt"))
            at = integer(item["line"], "Baris catatan", 1, len(lines))
            code = identifier(item["reason"], "Sebab kegagalan")
            exact = text(item["excerpt"], "Petikan sebab", 600)
            if exact not in lines[at - 1]:
                raise ResearchError("Catatan sebab tidak sesuai petikan.")
            notes.append({"reason": code, "line": at, "excerpt": exact})
        index[key] = {"id": key, "closed_at": closed_at.isoformat(), "question": text(row["question"], "Pertanyaan"),
                      "class": row["failure_class"], "result": proof, "protocol": protocol, "causes": notes}
    order = sorted(index.values(), key=lambda row: (row["closed_at"], row["id"]), reverse=True)
    return {"schema": "ace.institute.failed-research-index.v1", "plan_sha256": expected,
            "entries": order, "count_by_class": {state: sum(row["class"] == state for row in order) for state in STATES},
            "status": "draft_index"}


if __name__ == "__main__":
    raise SystemExit(cli(index_failed, __doc__, rooted=True))
