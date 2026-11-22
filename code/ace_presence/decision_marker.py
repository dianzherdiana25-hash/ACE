"""Catat putusan yang diucapkan dalam sesi beserta pelaku, waktu, dan label status eksplisit."""
import re

from ._contracts import anchor, cli, identifier, items, obj, schema, source_bytes
from ._journal import load_export

PATTERN = re.compile(r"^(?:Putusan|Decision) \[(approved|rejected|deferred)\] ([a-z][a-z0-9_]{0,63}): (.+)$", re.I)

def decisions(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.decision-plan.v1", ("dialogue", "authorized_speakers"))
    authorized = {identifier(value, "Pembicara") for value in items(plan["authorized_speakers"], 100, 1)}
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    results = []
    current = {}
    for event in doc["events"]:
        turn = event["turn"]
        match = PATTERN.fullmatch(turn["message"])
        if not match or not match[3].strip() or turn["speaker"] not in authorized:
            continue
        key = match[2].lower()
        record = {"decision": key, "status": match[1].lower(), "text": match[3], "at": turn["at"],
                  "speaker": turn["speaker"], "turn_sha256": event["sha256"], "previous": current.get(key)}
        results.append(record)
        current[key] = event["sha256"]
    return {"source": ref, "decisions": results, "latest": current}

if __name__ == "__main__":
    raise SystemExit(cli(decisions, __doc__, rooted=True))
