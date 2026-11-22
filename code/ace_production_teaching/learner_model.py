"""Ringkas penguasaan dari percobaan ber-provenance dan ketidakpastian yang dinyatakan."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import (ProductionError, anchor, cli, day, decode, identifier,
                         integer, items, number, obj, schema, source_bytes, text)


def posterior(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.learner-plan.v1", ("learner", "as_of", "topics", "attempts", "prior", "minimum_attempts"))
    learner = identifier(plan["learner"], "ID learner pseudonim")
    now = day(plan["as_of"])
    minimum = integer(plan["minimum_attempts"], "Jumlah percobaan minimum", 1, 1000)
    prior = obj(plan["prior"], ("alpha", "beta"))
    start_a, start_b = [Fraction(number(prior[part], "Prior beta")) for part in ("alpha", "beta")]
    if not 0 < start_a <= 100 or not 0 < start_b <= 100:
        raise ProductionError("Konstanta prior harus dalam 0..100 dan positif.")
    topic_ids = [identifier(topic, "Topik learner") for topic in items(plan["topics"], 200, 1)]
    if len(set(topic_ids)) != len(topic_ids):
        raise ProductionError("Daftar topik berisi duplikasi.")
    evidence = obj(plan["attempts"], ("path", "sha256"))
    data = source_bytes(root, evidence["path"], evidence["sha256"], 2_000_000)
    by_topic = defaultdict(list)
    all_ids = set()
    disregarded = []
    for line, raw in enumerate(data.splitlines(), 1):
        if line > 30000:
            raise ProductionError("Jumlah percobaan melebihi batas.")
        if not raw.strip():
            continue
        row = obj(decode(raw), ("id", "learner", "topic", "date", "earned", "possible", "source_ref"))
        key = identifier(row["id"], "Percobaan")
        if key in all_ids:
            raise ProductionError("ID percobaan ganda.")
        all_ids.add(key)
        target = identifier(row["learner"], "ID rekaman learner")
        topic = identifier(row["topic"], "Topik percobaan")
        date = day(row["date"])
        if target != learner or topic not in topic_ids or date > now:
            disregarded.append(line)
            continue
        possible = integer(row["possible"], "Poin tersedia", 1, 10000)
        earned = integer(row["earned"], "Poin diperoleh", 0, possible)
        pointer = text(row["source_ref"], "Pointer hasil latihan")
        by_topic[topic].append({"id": key, "line": line, "earned": earned, "possible": possible,
                                "source_ref": pointer, "date": row["date"]})
    output = {}
    for topic in sorted(topic_ids):
        observations = sorted(by_topic[topic], key=lambda row: (row["date"], row["id"]))
        credit = sum((Fraction(row["earned"], row["possible"]) for row in observations), Fraction(0))
        alpha, beta = start_a + credit, start_b + len(observations) - credit
        result = alpha / (alpha + beta)
        output[topic] = {"attempts": len(observations), "posterior_mean_bp": int(10000 * result),
                         "alpha_exact": [alpha.numerator, alpha.denominator], "beta_exact": [beta.numerator, beta.denominator],
                         "evidence_status": "observed" if len(observations) >= minimum else "insufficient_attempts",
                         "latest": observations[-1]["date"] if observations else None,
                         "evidence": observations}
    return {"schema": "ace.teaching.learner-model.v1", "plan_sha256": expected, "learner": learner, "as_of": plan["as_of"],
            "basis": "fractional_attempt_credit_with_beta_prior", "attempts_ref": evidence,
            "topic_posteriors": output, "disregarded_lines": disregarded}


if __name__ == "__main__":
    raise SystemExit(cli(posterior, __doc__, rooted=True))
