"""Terapkan batas topik yang ditetapkan pemilik kanal dan minta tinjauan untuk label asing."""
import re
from unicodedata import normalize

from ._contracts import PresenceError, anchor, cli, identifier, items, obj, schema, text

def adorn(value):
    return normalize("NFKC", value).casefold()

def check(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.topic-boundary.v1", ("channel", "policies", "message", "tags"))
    channel = identifier(plan["channel"], "Kanal")
    raw = adorn(text(plan["message"], "Pesan", 4500))
    supplied = {identifier(tag, "Label") for tag in items(plan["tags"], 60)}
    registry = {}
    for policy in items(plan["policies"], 100, 1):
        obj(policy, ("channel", "topics"))
        key = identifier(policy["channel"], "Kanal kebijakan")
        if key in registry:
            raise PresenceError("Kebijakan kanal berulang.")
        topics = {}
        for rule in items(policy["topics"], 80):
            obj(rule, ("id", "allow", "phrases"))
            topic = identifier(rule["id"], "Topik")
            phrases = [adorn(text(phrase, "Frasa", 100)) for phrase in items(rule["phrases"], 20)]
            if type(rule["allow"]) is not bool or topic in topics:
                raise PresenceError("Kebijakan topik ganda atau tidak sah.")
            topics[topic] = (rule["allow"], phrases)
        registry[key] = topics
    if channel not in registry:
        return {"status": "review", "blocked": [], "unrecognized": sorted(supplied)}
    registry = registry[channel]
    tagged = supplied | {key for key, (_, phrases) in registry.items()
                         if any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", raw) for phrase in phrases)}
    blocked = sorted(tag for tag in tagged if tag in registry and not registry[tag][0])
    unknown = sorted(tagged - registry.keys())
    status = "blocked" if blocked else "review" if unknown or not tagged else "allowed"
    return {"status": status, "blocked": blocked, "unrecognized": unknown}

if __name__ == "__main__":
    raise SystemExit(cli(check, __doc__))
