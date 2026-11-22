"""Bentuk postmortem kronologis dari journal dan lampirkan hanya sebab yang punya rujukan."""
from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema, text
from .incident_journal import index

def postmortem(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.postmortem.v1", ("journal", "incident", "findings", "followups"))
    incidents = index(plan["journal"], identity(plan["journal"]))
    key = identifier(plan["incident"], "Insiden")
    source = next((row for row in incidents["incidents"] if row["id"] == key), None)
    if source is None:
        raise GuardianError("Insiden postmortem tidak ada dalam journal.")
    refs = {event["sha256"] for event in source["events"]}
    observations = []
    for row in items(plan["findings"], 100):
        obj(row, ("status", "statement", "source"))
        text(row["statement"], "Temuan", 800)
        if row["source"] not in refs or row["status"] not in ("observed", "hypothesis"):
            raise GuardianError("Temuan perlu event insiden dan jenis pernyataan eksplisit.")
        observations.append(row)
    followups = []
    known = set()
    for row in items(plan["followups"], 100):
        obj(row, ("id", "proposal", "source"))
        item = identifier(row["id"], "Tindak lanjut")
        text(row["proposal"], "Usulan", 800)
        if item in known or row["source"] not in refs:
            raise GuardianError("Tindak lanjut ganda atau tanpa event asal.")
        known.add(item)
        followups.append(row)
    return {"incident": key, "state": source["state"], "component": source["component"],
            "timeline": source["events"], "findings": observations, "followups": followups,
            "root_cause": "operator_review_pending",
            "journal_head": incidents["head_sha256"]}

if __name__ == "__main__":
    raise SystemExit(cli(postmortem, __doc__))
