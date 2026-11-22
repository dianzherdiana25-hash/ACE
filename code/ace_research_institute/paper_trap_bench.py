"""Uji pembaca paper dengan tabel benar, angka pengalih, dan anotasi label terpisah."""
from ._contracts import ResearchError, anchor, cli, decode, identifier, identity, items, obj, schema, source_bytes
from .paper_reader import read_papers


def bench_traps(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.paper-trap-plan.v1", ("paper_plan", "gold"))
    source = obj(plan["gold"], ("path", "sha256"))
    gold = decode(source_bytes(root, source["path"], source["sha256"], 250000))
    schema(gold, "ace.institute.paper-trap-gold.v1", ("papers",))
    outputs = read_papers(plan["paper_plan"], identity(plan["paper_plan"]), root)
    answers = {item["id"]: item for item in outputs["papers"]}
    result = []
    seen = set()
    for row in items(gold["papers"], 40, 1):
        obj(row, ("id", "accept", "never_accept", "minimum_holds"))
        key = identifier(row["id"], "Kasus paper")
        if key not in answers or key in seen:
            raise ResearchError("ID label ganda atau paper tidak terdaftar.")
        seen.add(key)
        accepted = {identifier(val, "Klaim diharapkan") for val in items(row["accept"], 150)}
        distract = {identifier(val, "Klaim pengalih") for val in items(row["never_accept"], 150)}
        if accepted & distract or type(row["minimum_holds"]) is not int or row["minimum_holds"] < 0:
            raise ResearchError("Kunci trap berkonflik atau ambang hold tidak sah.")
        paper = answers[key]
        actual = {item["id"] for item in paper["claims"]}
        wrong = sorted(actual - accepted)
        missing = sorted(accepted - actual)
        held = len(paper["held"])
        result.append({"id": key, "paper_sha256": paper["paper_sha256"], "present": sorted(actual & accepted),
                       "false_accepts": wrong, "accepted_distractors": sorted(actual & distract), "missed_claims": missing,
                       "hold_rows": paper["held"], "status": "pass" if not (wrong or missing) and held >= row["minimum_holds"] else "hold"})
    if set(answers) != seen:
        raise ResearchError("Kunci tidak mencakup seluruh paper pengujian.")
    return {"schema": "ace.institute.paper-trap-result.v1", "plan_sha256": expected, "gold": source,
            "cases": result, "passed": sum(row["status"] == "pass" for row in result),
            "status": "fixture_pass" if all(row["status"] == "pass" for row in result) else "fixture_hold"}


if __name__ == "__main__":
    raise SystemExit(cli(bench_traps, __doc__, rooted=True))
