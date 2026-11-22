"""Sajikan satu halaman status dari dokumen bernama yang sah dan nyatakan sumber yang tertahan."""
from ._contracts import GuardianError, anchor, cli, decode, identifier, items, obj, schema, text
from ._snapshots import fingerprint, read_fixture
from .snapshot_scheduler import instant

def one_page(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.one-page.v1", ("as_of", "panels"))
    now = instant(plan["as_of"])
    seen = set()
    panels = []
    for row in items(plan["panels"], 80, 1):
        obj(row, ("id", "path", "sha256", "title"))
        key = identifier(row["id"], "Panel")
        title = text(row["title"], "Judul panel", 150)
        if key in seen:
            raise GuardianError("Panel ganda.")
        seen.add(key)
        try:
            data = read_fixture(root, row["path"])
            if fingerprint(data)["sha256"] != row["sha256"]:
                raise GuardianError("Data panel berbeda.")
            obj_value = schema(decode(data), "ace.guardian.panel.v1", ("as_at", "status", "summary"))
            if instant(obj_value["as_at"]) > now:
                raise GuardianError("Sumber panel dari masa depan.")
            status = identifier(obj_value["status"], "Status panel")
            summary = text(obj_value["summary"], "Ringkasan sumber", 450)
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            status, summary = "unavailable", None
        panels.append({"id": key, "title": title, "status": status, "summary": summary,
                       "source": {"path": row["path"], "sha256": row["sha256"]}})
    return {"as_of": plan["as_of"], "panels": panels}

if __name__ == "__main__":
    raise SystemExit(cli(one_page, __doc__, rooted=True))
