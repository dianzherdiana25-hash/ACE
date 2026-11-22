"""Temukan klaim dengan kenaikan observasi yang masih memerlukan verifikasi."""
from collections import defaultdict

from ._contracts import ResearchError, anchor, cli, day, decode, identifier, identity, integer, obj, schema, source_bytes
from .claim_checker import check_claims


def monitor(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.claim-watch-plan.v1", ("source", "as_of", "window_days", "minimum_new", "minimum_growth",
                                                       "claim_check"))
    now = day(plan["as_of"])
    span = integer(plan["window_days"], "Jendela", 1, 30)
    minimum_new = integer(plan["minimum_new"], "Observasi minimum", 1, 10**9)
    growth = integer(plan["minimum_growth"], "Kenaikan minimum", 1, 10**9)
    link = obj(plan["source"], ("path", "sha256"))
    raw = source_bytes(root, link["path"], link["sha256"], 1_000_000)
    check = check_claims(plan["claim_check"], identity(plan["claim_check"]), root)
    statuses = {item["id"]: item["status"] for item in check["claims"]}
    grouped = defaultdict(dict)
    for line, row in enumerate(raw.splitlines(), 1):
        if line > 12000:
            raise ResearchError("Baris observasi melebihi batas.")
        if not row.strip():
            continue
        item = obj(decode(row), ("claim", "origin", "date", "observations"))
        key = identifier(item["claim"], "Klaim diamati")
        origin = identifier(item["origin"], "Grup platform")
        seen = day(item["date"])
        count = integer(item["observations"], "Observasi cuplikan harian", 0, 10**9)
        if (origin, seen) in grouped[key] or seen > now:
            raise ResearchError("Observasi periode ganda atau berada di masa depan.")
        grouped[key][origin, seen] = (count, line)
    result = []
    held = []
    for key, data in sorted(grouped.items()):
        records = [{}, {}]
        for (source, observed), (count, line) in data.items():
            age = (now - observed).days
            if age < 2 * span:
                records[age // span][(source, age % span)] = (count, line)
        comparable = records[0].keys() & records[1].keys()
        recent, prior = [sum(frame[key][0] for key in comparable) for frame in records]
        delta = recent - prior
        if not comparable:
            held.append({"claim_id": key, "reason": "no_matched_observations"})
        elif recent >= minimum_new and delta >= growth and statuses.get(key) != "supported":
            result.append({"claim_id": key, "recent": recent, "prior": prior, "delta": delta, "matched_slots": len(comparable),
                           "status": statuses.get(key, "not_checked"),
                           "evidence_lines": [sorted(frame[key][1] for key in comparable) for frame in records]})
    result.sort(key=lambda row: (-row["delta"], row["claim_id"]))
    return {"schema": "ace.institute.claim-watch.v1", "plan_sha256": expected, "source": link,
            "claim_check_sha256": identity(check), "basis": "matched_origin_and_relative_day",
            "needs_review": result, "held": held}


if __name__ == "__main__":
    raise SystemExit(cli(monitor, __doc__, rooted=True))
