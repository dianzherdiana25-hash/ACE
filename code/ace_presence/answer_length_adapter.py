"""Sesuaikan panjang jawaban dengan memilih blok utuh dan mempertahankan informasi wajib."""
from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text

def adapt(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.answer-length.v1", ("max_chars", "blocks"))
    budget = integer(plan["max_chars"], "Anggaran kanal", 1, 16_000)
    records = []
    seen = set()
    for position, row in enumerate(items(plan["blocks"], 100, 1)):
        obj(row, ("id", "text", "required", "priority", "source"))
        key = identifier(row["id"], "Blok")
        size = len(text(row["text"], "Teks blok", 7000))
        text(row["source"], "Sumber blok")
        rank = integer(row["priority"], "Prioritas blok", 0, 100)
        if key in seen or type(row["required"]) is not bool:
            raise PresenceError("Duplikat blok atau marker wajib tidak sah.")
        seen.add(key)
        records.append((row["required"], rank, position, size, row))
    mandatory = [row for row in records if row[0]]
    required_cost = sum(row[3] for row in mandatory) + max(len(mandatory) - 1, 0)
    if required_cost > budget:
        return {"status": "requires_larger_channel", "min_chars": required_cost, "answer": None, "used": []}
    picked = list(mandatory)
    cost = required_cost
    for entry in sorted((row for row in records if not row[0]), key=lambda row: (-row[1], row[2])):
        additional = entry[3] + bool(picked)
        if cost + additional <= budget:
            picked.append(entry)
            cost += additional
    blocks = [row[4] for row in sorted(picked, key=lambda row: row[2])]
    return {"status": "ready", "answer": "\n".join(row["text"] for row in blocks),
            "used": [{"id": row["id"], "source": row["source"]} for row in blocks],
            "omitted": sorted(seen - {row["id"] for row in blocks}), "chars": cost}

if __name__ == "__main__":
    raise SystemExit(cli(adapt, __doc__))
