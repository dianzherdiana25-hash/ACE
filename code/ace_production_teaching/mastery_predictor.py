"""Estimasi penguasaan pada tanggal target dengan half-life deklaratif dan batas prasyarat."""
from decimal import Decimal, localcontext
from fractions import Fraction

from ._contracts import ProductionError, anchor, cli, day, identifier, identity, integer, items, obj, schema, text
from .learner_model import posterior
from .topic_map import graph


def predict(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.mastery-plan.v1", ("profile", "graph", "forecast_on", "policies", "threshold_bp"))
    state = posterior(plan["profile"], identity(plan["profile"]), root)
    topics = graph(plan["graph"], identity(plan["graph"]))
    forecast = day(plan["forecast_on"])
    if not 0 <= (forecast - day(state["as_of"])).days <= 730:
        raise ProductionError("Tanggal forecast perlu setelah profil dan maksimal 730 hari.")
    threshold = integer(plan["threshold_bp"], "Ambang mastery", 1, 10000)
    policy = {}
    for row in items(plan["policies"], 400, 1):
        obj(row, ("topic", "half_life_days", "baseline_bp", "source_ref"))
        key = identifier(row["topic"], "Topik model")
        if key in policy or key not in topics["topics"]:
            raise ProductionError("Kebijakan topik ganda atau belum terdaftar.")
        policy[key] = {"half_life_days": integer(row["half_life_days"], "Paruh hari", 1, 10000),
                       "baseline_bp": integer(row["baseline_bp"], "Laju dasar", 0, 10000),
                       "source_ref": text(row["source_ref"], "Pointer asumsi")}
    projected = {}
    with localcontext() as context:
        context.prec = 28
        log2 = Decimal(2).ln()
        for name in topics["order"]:
            data = state["topic_posteriors"].get(name)
            config = policy.get(name)
            dependencies = topics["topics"][name]["required"]
            if config is None or data is None or data["evidence_status"] != "observed":
                projected[name] = {"topic": name, "status": "unmeasured", "estimate_bp": None}
                continue
            span = (forecast - day(data["latest"])).days
            factor = (-log2 * span / config["half_life_days"]).exp()
            fraction = Fraction(*data["alpha_exact"])
            anchor_value = fraction / (fraction + Fraction(*data["beta_exact"]))
            initial = Decimal(anchor_value.numerator) * 10000 / Decimal(anchor_value.denominator)
            base = config["baseline_bp"]
            raw = int(base + (initial - base) * factor)
            holds = [dep for dep in dependencies if projected[dep]["estimate_bp"] is None]
            ceiling = min((projected[dep]["estimate_bp"] for dep in dependencies if dep not in holds), default=10000)
            value = None if holds else min(raw, ceiling)
            label = "prerequisite_unmeasured" if holds else ("likely_above_threshold" if value >= threshold else "below_threshold")
            projected[name] = {"topic": name, "status": label, "estimate_bp": value, "without_prerequisite_cap_bp": raw,
                               "latest_evidence": data["latest"], "attempts": data["attempts"], "unmeasured_dependencies": holds,
                               "retention_assumption": config}
    return {"schema": "ace.teaching.mastery-forecast.v1", "plan_sha256": expected, "forecast_on": plan["forecast_on"],
            "basis": "declared_exponential_decay_and_prerequisite_cap", "topics": list(projected.values()),
            "learner_evidence_sha256": identity(state)}


if __name__ == "__main__":
    raise SystemExit(cli(predict, __doc__, rooted=True))
