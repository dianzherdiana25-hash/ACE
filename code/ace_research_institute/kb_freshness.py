"""Audit umur bukti per topik serta kemampuan sumber mandiri untuk menutup celah."""
from ._contracts import ResearchError, anchor, cli, day, identity, integer, items, obj, schema, text, words
from .source_collector import collect


def freshness(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.freshness-plan.v1", ("register_plan", "policies"))
    catalog = plan["register_plan"]
    register = collect(catalog, identity(catalog), root)
    policy = {}
    for row in items(plan["policies"], 80, 1):
        obj(row, ("topic", "maximum_age_days", "minimum_groups"))
        topic = text(row["topic"], "Topik kebijakan", 100).casefold()
        if words(topic) != {topic} or topic in policy:
            raise ResearchError("Kebijakan topik memerlukan satu token unik.")
        policy[topic] = (integer(row["maximum_age_days"], "TTL bukti", 0, 36500),
                         integer(row["minimum_groups"], "Grup minimum", 1, 100))
    if not set(policy) <= set(register["topics"]):
        raise ResearchError("Kebijakan merujuk topik yang belum terdaftar.")
    current = day(register["as_of"])
    report = []
    for topic, (cap, minimum) in sorted(policy.items()):
        rows = []
        for item in register["sources"]:
            if topic not in item["memberships"]:
                continue
            sample = (current - day(item["published"])).days
            holds = list(item["hold_reasons"])
            state = "held" if holds else ("fresh" if sample <= cap else "stale")
            rows.append({"id": item["id"], "path": item["path"], "sha256": item["sha256"],
                         "group": item["independence_group"], "age_days": sample, "status": state, "source_holds": holds})
        counted = sorted({item["group"] for item in rows if item["status"] == "fresh"})
        report.append({"topic": topic, "latest_fresh_age_days": min((row["age_days"] for row in rows if row["status"] == "fresh"), default=None),
                       "max_age_days": cap, "minimum_groups": minimum, "fresh_groups": counted,
                       "status": "fresh_coverage" if len(counted) >= minimum else "refresh_needed", "sources": rows})
    return {"schema": "ace.institute.kb-freshness.v1", "plan_sha256": expected,
            "as_of": register["as_of"], "register_sha256": identity(register), "topics": report}


if __name__ == "__main__":
    raise SystemExit(cli(freshness, __doc__, rooted=True))
