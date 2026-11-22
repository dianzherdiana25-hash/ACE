"""Pertahankan istilah dan angka saat mencerminkan kutipan lewat korpus ID–EN terverifikasi."""
from collections import Counter
import re

from ._contracts import PresenceError, anchor, cli, decode, items, obj, schema, source_bytes, text

NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*%?(?!\w)")

def contains(message, phrase):
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", message, re.IGNORECASE) is not None

def mirror(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.mirror-plan.v1", ("parallel", "glossary", "from", "segments"))
    lang = plan["from"]
    if lang not in ("id", "en"):
        raise PresenceError("Bahasa asal perlu id atau en.")
    other = "en" if lang == "id" else "id"
    ref = obj(plan["parallel"], ("path", "sha256"))
    pairs = decode(source_bytes(root, ref["path"], ref["sha256"]))
    entries = {}
    glossary = [obj(entry, ("id", "en")) for entry in items(plan["glossary"], 200)]
    for entry in glossary:
        for key in ("id", "en"):
            text(entry[key], "Istilah", 150)
    for ordinal, row in enumerate(items(pairs, 1000), 1):
        obj(row, ("id", "en"))
        for key in ("id", "en"):
            text(row[key], "Segmen korpus", 1200)
        if row[lang] in entries:
            raise PresenceError("Segmen korpus asal ambigu.")
        entries[row[lang]] = (ordinal, row[other])
    rendered = []
    missing = []
    for ordinal, segment in enumerate(items(plan["segments"], 300), 1):
        source = text(segment, "Segmen", 1200)
        found = entries.get(source)
        if found is None:
            missing.append(ordinal)
            continue
        line, target = found
        if Counter(NUMBER.findall(source)) != Counter(NUMBER.findall(target)):
            raise PresenceError("Segmen korpus mengubah angka eksplisit.")
        if any(contains(source, row[lang]) != contains(target, row[other]) for row in glossary):
            raise PresenceError("Segmen tidak mempertahankan istilah glosarium.")
        rendered.append({"index": ordinal, "translation": target, "source_line": line})
    return {"source": ref, "target_language": other, "segments": rendered, "unmatched": missing}

if __name__ == "__main__":
    raise SystemExit(cli(mirror, __doc__, rooted=True))
