"""Tandai kebutuhan dukungan dari riwayat skor dan waktu, dengan kategori bukti yang kurang."""
from fractions import Fraction

from ._contracts import anchor, cli, day, identity, integer, obj, schema
from .learner_model import posterior


def flag(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.support-signal-plan.v1", ("profile", "thresholds"))
    profile = posterior(plan["profile"], identity(plan["profile"]), root)
    spec = obj(plan["thresholds"], ("minimum_recent", "low_average_bp", "inactivity_days", "downshift_bp"))
    n = integer(spec["minimum_recent"], "Percobaan terbaru", 2, 30)
    average_floor = integer(spec["low_average_bp"], "Ambang skor", 0, 10000)
    lapse = integer(spec["inactivity_days"], "Batas jeda", 1, 3650)
    down = integer(spec["downshift_bp"], "Turun minimum", 1, 10000)
    now = day(profile["as_of"])
    topics = []
    for key, result in profile["topic_posteriors"].items():
        observed = result["evidence"]
        count = len(observed)
        last = None if not observed else (now - day(observed[-1]["date"])).days
        signals = []
        current = None
        delta = None
        if count >= n:
            recent = [Fraction(row["earned"], row["possible"]) for row in observed[-n:]]
            current = int(sum(recent) * 10000 / n)
            if current <= average_floor:
                signals.append("recent_scores_below_floor")
        if count >= 2 * n:
            prior = [Fraction(row["earned"], row["possible"]) for row in observed[-2*n:-n]]
            delta = int(sum(prior) * 10000 / n) - current
            if delta >= down:
                signals.append("observed_downshift")
        if last is not None and last >= lapse:
            signals.append("last_observation_old")
        state = "support_signal" if signals else ("insufficient_recent_evidence" if count < n else "no_listed_signal")
        topics.append({"topic": key, "status": state, "signals": signals, "recent_average_bp": current,
                       "previous_minus_recent_bp": delta, "days_since_attempt": last,
                       "source_lines": [row["line"] for row in observed[-2*n:]]})
    return {"schema": "ace.teaching.support-signals.v1", "plan_sha256": expected, "scope": "rule_based_support_signals",
            "profile_sha256": identity(profile), "source": profile["attempts_ref"], "topics": topics}


if __name__ == "__main__":
    raise SystemExit(cli(flag, __doc__, rooted=True))
