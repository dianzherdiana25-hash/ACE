"""Rakit notulen ekstraktif dari penanda agenda, keputusan, dan tindak lanjut pada turn berizin."""
import re

from ._contracts import anchor, cli, identifier, items, obj, schema, source_bytes
from ._journal import load_export

MARKER = re.compile(r"^(Agenda|Keputusan|Tindak lanjut|Decision|Action): (.+)$", re.IGNORECASE)
TYPES = {"agenda": "agenda", "keputusan": "decisions", "decision": "decisions",
         "tindak lanjut": "actions", "action": "actions"}

def notes(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.notes.v1", ("dialogue", "allowed_speakers"))
    speakers = {identifier(value, "Pembicara") for value in items(plan["allowed_speakers"], 100, 1)}
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    groups = {key: [] for key in sorted(set(TYPES.values()))}
    for event in doc["events"]:
        turn = event["turn"]
        if turn["speaker"] not in speakers:
            continue
        match = MARKER.fullmatch(turn["message"])
        if match and match[2].strip():
            groups[TYPES[match[1].casefold()]].append(
                {"text": match[2], "id": turn["id"], "at": turn["at"],
                 "source_turn_sha256": event["sha256"], "speaker": turn["speaker"]})
    return {"session": doc["session"], "source": ref, **groups}

if __name__ == "__main__":
    raise SystemExit(cli(notes, __doc__, rooted=True))
