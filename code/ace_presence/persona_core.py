"""Simpan persona sebagai deskripsi berversi dengan perubahan tersumber dan namespace terbatas."""
from ._contracts import (
    PresenceError, anchor, cli, day, decode, identifier, identity, integer, items, obj, schema,
    source_bytes, text,
)


FIELDS = ("tone", "identifier", "languages", "boundaries")


def _profile(raw):
    obj(raw, FIELDS)
    tone = text(raw["tone"], "Nada persona", 130)
    label = identifier(raw["identifier"], "Identitas persona")
    languages = [identifier(value, "Bahasa") for value in items(raw["languages"], 8, 1)]
    boundaries = [text(value, "Batas persona", 160) for value in items(raw["boundaries"], 25, 1)]
    if len(set(languages)) != len(languages) or len(set(boundaries)) != len(boundaries):
        raise PresenceError("Bahasa atau batas persona ganda.")
    return {"tone": tone, "identifier": label, "languages": languages, "boundaries": boundaries}


def revise(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.persona-plan.v1", ("version", "effective", "parent", "profile", "evidence"))
    version = integer(plan["version"], "Versi persona", 1, 100000)
    stamp = day(plan["effective"])
    current = _profile(plan["profile"])
    previous = {}
    parent = None
    if version == 1:
        if plan["parent"] is not None:
            raise PresenceError("Persona versi pertama tidak memiliki parent.")
    else:
        link = obj(plan["parent"], ("path", "sha256"))
        data = decode(source_bytes(root, link["path"], link["sha256"], 200000))
        schema(data, "ace.presence.persona-version.v1", ("version", "effective", "parent_sha256", "profile", "evidence"))
        before = day(data["effective"])
        previous = _profile(data["profile"])
        if data["version"] != version - 1 or before >= stamp or previous["identifier"] != current["identifier"]:
            raise PresenceError("Urutan, identitas persona atau waktu parent tidak cocok.")
        parent = link["sha256"]
    delta = {name for name in FIELDS if current[name] != previous.get(name)}
    notes = {}
    for row in items(plan["evidence"], len(FIELDS), 1):
        obj(row, ("field", "source_ref"))
        key = row["field"]
        if key not in delta or key in notes:
            raise PresenceError("Pointer perubahan ganda atau menunjuk bidang tanpa perubahan.")
        notes[key] = text(row["source_ref"], "Pointer revisi persona")
    if notes.keys() != delta:
        raise PresenceError("Semua perubahan persona perlu rujukan.")
    output = {"schema": "ace.presence.persona-version.v1", "version": version,
              "effective": stamp.isoformat(), "parent_sha256": parent, "profile": current, "evidence": notes}
    return {"schema": "ace.presence.persona-revision.v1", "plan_sha256": expected,
            "profile_sha256": identity(output), "revision": output, "changed_fields": sorted(delta)}


if __name__ == "__main__":
    raise SystemExit(cli(revise, __doc__, rooted=True))
