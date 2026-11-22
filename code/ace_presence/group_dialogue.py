"""Jaga giliran percakapan banyak pihak dan atribut pembicara ketika rekaman melompat."""
from ._contracts import PresenceError, anchor, cli, identifier, identity, items, obj, schema, text
from ._journal import instant

def assemble(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.group-plan.v1", ("participants", "turns"))
    allowed = []
    for participant in items(plan["participants"], 40, 2):
        obj(participant, ("id", "consent"))
        key = identifier(participant["id"], "Peserta")
        if participant["consent"] is not True or key in allowed:
            raise PresenceError("Partisipasi belum disetujui atau berulang.")
        allowed.append(key)
    output = []
    seen = set()
    last = None
    current = 0
    head = identity({"participants": allowed})
    for turn in items(plan["turns"], 400):
        obj(turn, ("id", "speaker", "at", "act", "message"))
        key = identifier(turn["id"], "Turn kelompok")
        when = instant(turn["at"])
        if key in seen or turn["speaker"] != allowed[current] or (last is not None and when < last):
            raise PresenceError("Identitas, giliran, atau waktu kelompok bertentangan.")
        if turn["act"] == "speak":
            text(turn["message"], "Giliran bicara", 1800)
        elif turn["act"] != "pass" or turn["message"] != "":
            raise PresenceError("Aksi giliran kelompok tidak dikenal.")
        current = (current + 1) % len(allowed)
        seen.add(key)
        last = when
        row = {"turn": turn, "index": len(output) + 1, "previous_sha256": head}
        head = identity(row)
        output.append({**row, "sha256": head})
    return {"turns": output, "head_sha256": head, "next_speaker": allowed[current]}

if __name__ == "__main__":
    raise SystemExit(cli(assemble, __doc__))
