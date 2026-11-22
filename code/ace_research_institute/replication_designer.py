"""Pilih ukuran replikasi yang terjangkau di bawah asumsi power dua proporsi."""
from math import ceil, sqrt
from statistics import NormalDist

from ._contracts import ResearchError, anchor, cli, identifier, integer, items, number, obj, schema, text


def plan_replication(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.replication-design-plan.v1", ("hypothesis", "assumptions", "limits", "design_options"))
    options = obj(plan["assumptions"], ("baseline_rate", "replication_rate", "alpha", "desired_power", "source_ref"))
    p0, p1, alpha, power = [float(number(options[key], key)) for key in ("baseline_rate", "replication_rate", "alpha", "desired_power")]
    if not all(0 < p < 1 for p in (p0, p1, alpha, power)) or p0 == p1 or power <= 0.5:
        raise ResearchError("Asumsi power perlu peluang interior, beda proporsi, dan target di atas separuh.")
    proof = text(options["source_ref"], "Pointer asumsi power")
    average = (p0 + p1) / 2
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    delta = abs(p1 - p0)
    per_arm = ceil((z_alpha * sqrt(2 * average * (1 - average))
                    + z_power * sqrt(p0 * (1 - p0) + p1 * (1 - p1)))**2 / delta**2)
    limits = obj(plan["limits"], ("max_minutes", "max_units", "max_watt_seconds"))
    budget_minutes = integer(limits["max_minutes"], "Batas menit", 1, 1_000_000_000)
    budget_units = integer(limits["max_units"], "Batas unit", 2, 10**8)
    budget_energy = integer(limits["max_watt_seconds"], "Batas energi", 1, 10**14)
    choices = []
    known = set()
    for row in items(plan["design_options"], 60, 1):
        obj(row, ("id", "setup_minutes", "minutes_per_unit", "watt_seconds_per_unit", "capacity_units", "procedure_ref"))
        name = identifier(row["id"], "Opsi replikasi")
        if name in known:
            raise ResearchError("Opsi replikasi ganda.")
        known.add(name)
        units = 2 * per_arm
        setup = integer(row["setup_minutes"], "Setup", 0, 1_000_000)
        duration = setup + units * integer(row["minutes_per_unit"], "Menit per unit", 1, 1_000_000)
        consumption = units * integer(row["watt_seconds_per_unit"], "Energi per unit", 1, 1_000_000_000)
        capacity = integer(row["capacity_units"], "Kapasitas", 2, 10**8)
        blockers = [key for key, value, maximum in (("capacity", units, min(budget_units, capacity)),
                    ("minutes", duration, budget_minutes), ("energy", consumption, budget_energy)) if value > maximum]
        choices.append({"id": name, "total_units": units, "estimated_minutes": duration,
                        "estimated_watt_seconds": consumption, "blocked_by": blockers,
                        "procedure_ref": text(row["procedure_ref"], "Pointer metode")})
    choices.sort(key=lambda item: (bool(item["blocked_by"]), item["estimated_minutes"], item["estimated_watt_seconds"], item["id"]))
    winner = choices[0]["id"] if not choices[0]["blocked_by"] else None
    return {"schema": "ace.institute.replication-design.v1", "plan_sha256": expected,
            "hypothesis": text(plan["hypothesis"], "Hipotesis"), "hypothesis_assumptions": options,
            "assumption_source_ref": proof, "method": "normal_approximation_equal_two_arms_two_sided",
            "units_per_arm": per_arm, "selected_option": winner, "options": choices,
            "status": "draft" if winner else "no_feasible_design"}


if __name__ == "__main__":
    raise SystemExit(cli(plan_replication, __doc__))
