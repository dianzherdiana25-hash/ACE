"""Periksa padanan kutipan dan status tautan dari snapshot HTTP yang sudah direkam."""
from ._contracts import (ResearchError, anchor, cli, day, decode, identifier, integer,
                         items, obj, schema, source_bytes, text)
from .internal_citation_index import canonical_citation


def validate_citations(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.citation-validation-plan.v1", ("as_of", "max_age_days", "snapshot", "citations"))
    current = day(plan["as_of"])
    cap = integer(plan["max_age_days"], "Usia snapshot", 0, 36500)
    archive = obj(plan["snapshot"], ("path", "sha256"))
    records = decode(source_bytes(root, archive["path"], archive["sha256"], 1000000))
    schema(records, "ace.institute.http-snapshot.v1", ("entries",))
    captured = {}
    for item in items(records["entries"], 200, 1):
        obj(item, ("url", "captured", "status", "redirect", "document"))
        value = text(item["url"], "Locator snapshot", 450)
        target = canonical_citation(value)
        if target is None or target in captured:
            raise ResearchError("URL snapshot tidak sah atau ganda.")
        stamp = day(item["captured"])
        status = integer(item["status"], "Status dari snapshot", 100, 599)
        if stamp > current:
            raise ResearchError("Snapshot berasal dari masa depan relatif ke as-of.")
        captured[target] = (stamp, status, item)
    results = []
    seen = set()
    for row in items(plan["citations"], 300, 1):
        obj(row, ("id", "locator", "excerpt", "line"))
        key = identifier(row["id"], "Sitasi")
        if key in seen:
            raise ResearchError("Sitasi memiliki ID duplikat.")
        seen.add(key)
        start = canonical_citation(text(row["locator"], "Locator sitasi", 450))
        excerpt = text(row["excerpt"], "Kutipan sitasi", 800)
        line = integer(row["line"], "Baris kutipan pada snapshot", 1, 100000)
        chain = []
        decision = None
        linked = None
        if start is None:
            decision = "invalid_locator"
        while decision is None:
            if start in chain or len(chain) >= 6:
                decision = "redirect_cycle_or_limit"
                break
            chain.append(start)
            if start not in captured:
                decision = "snapshot_missing"
                break
            stamp, status, item = captured[start]
            if (current - stamp).days > cap:
                decision = "stale_snapshot"
            elif 300 <= status < 400:
                if not isinstance(item["redirect"], str) or not canonical_citation(item["redirect"]):
                    decision = "redirect_unresolved"
                else:
                    start = canonical_citation(item["redirect"])
            elif not 200 <= status < 300:
                decision = "observed_http_failure"
            elif item["document"] is None:
                decision = "snapshot_body_missing"
            else:
                doc = obj(item["document"], ("path", "sha256"))
                lines = source_bytes(root, doc["path"], doc["sha256"], 500000).decode("utf-8").splitlines()
                linked = {**doc, "line": line, "captured": item["captured"], "status": status}
                decision = "matched_in_snapshot" if line <= len(lines) and excerpt in lines[line - 1] else "excerpt_mismatch"
        results.append({"id": key, "chain": chain, "status": decision, "evidence": linked})
    return {"schema": "ace.institute.citation-validation.v1", "plan_sha256": expected, "snapshot": archive,
            "as_of": plan["as_of"], "scope": "offline_http_snapshot", "citations": results,
            "matched": sum(row["status"] == "matched_in_snapshot" for row in results)}


if __name__ == "__main__":
    raise SystemExit(cli(validate_citations, __doc__, rooted=True))
