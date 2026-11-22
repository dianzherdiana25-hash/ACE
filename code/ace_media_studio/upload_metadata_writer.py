"""Siapkan metadata unggahan dari fakta yang telah disetujui, dengan provenance per baris."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys
import unicodedata

from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, integer, obj, read, schema, text)


TAG = re.compile(r"[^\W_]+(?:[-_][^\W_]+)*", re.UNICODE)


def _tag(raw):
    label = unicodedata.normalize("NFC", text(raw, "Tag", 40)).casefold()
    if not TAG.fullmatch(label):
        raise ContractError("Tag hanya menerima huruf, digit atau penghubung.")
    return label


def prepare_metadata(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.metadata-plan.v1", ("platform", "media_sha256", "title", "source_ref",
                                              "limits", "facts", "tags", "credits"))
    platform = identifier(plan["platform"], "Profil platform")
    source = text(plan["source_ref"], "Pointer konteks")
    anchor = digest(plan["media_sha256"])
    title = text(plan["title"], "Judul", 200)
    limits = obj(plan["limits"], ("title", "description", "tags"))
    title_cap = integer(limits["title"], "Batas judul", 1, 200)
    desc_cap = integer(limits["description"], "Batas deskripsi", 10, 4000)
    tags_cap = integer(limits["tags"], "Batas tag", 0, 40)
    facts = []
    blocked = []
    seen = set()
    for row in entries(plan["facts"], 50, 1):
        obj(row, ("id", "text", "source_ref", "approved"))
        key = identifier(row["id"], "ID fakta")
        if key in seen or type(row["approved"]) is not bool:
            raise ContractError("ID fakta ganda atau penanda persetujuan tidak sah.")
        seen.add(key)
        body = text(row["text"], "Fakta", 500)
        pointer = text(row["source_ref"], "Pointer fakta")
        if row["approved"]:
            facts.append((body, {"kind": "fact", "id": key, "source_ref": pointer, "sha256": sha256(body.encode()).hexdigest()}))
        else:
            blocked.append({"rule": "unapproved_fact", "id": key, "source_ref": pointer})
    if not facts:
        blocked.append({"rule": "no_approved_description"})
    credits = []
    names = set()
    for row in entries(plan["credits"], 40):
        obj(row, ("asset", "credit", "license_ref"))
        item = identifier(row["asset"], "Aset kredit")
        if item in names:
            raise ContractError("Kredit aset ganda.")
        names.add(item)
        credit = text(row["credit"], "Kredit", 200)
        locator = text(row["license_ref"], "Pointer lisensi")
        desc = f"Kredit {item}: {credit} ({locator})"
        credits.append((desc, {"kind": "credit", "id": item, "source_ref": locator,
                               "sha256": sha256(desc.encode()).hexdigest()}))
    tags = sorted({_tag(tag) for tag in entries(plan["tags"], 100)})
    rows = [*facts, *credits]
    description = "\n".join(body for body, _ in rows)
    for field, value, maximum in (("title", title, title_cap), ("description", description, desc_cap), ("tags", tags, tags_cap)):
        if len(value) > maximum:
            blocked.append({"rule": "platform_limit", "field": field, "actual": len(value), "maximum": maximum})
    return {"schema": "ace.media.metadata-receipt.v1", "plan_sha256": expected,
            "platform": platform, "media_sha256": anchor, "source_ref": source, "status": "hold" if blocked else "ready",
            "upload_fields": None if blocked else {"title": title, "description": description, "tags": tags},
            "line_sources": [{"line": index, **item} for index, (_, item) in enumerate(rows, 1)], "blocking": blocked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = prepare_metadata(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(receipt["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
