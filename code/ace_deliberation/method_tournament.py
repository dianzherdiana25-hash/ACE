"""Bandingkan metode deliberasi pada kasus dan rubrik yang sama.

Turnamen mengurutkan hasil replay penilaian. Setiap pasangan dinilai pada
seluruh kasus terdaftar. Seri tetap seri. Waktu dan biaya dilaporkan
terpisah dari kualitas agar pilihan satuan tidak mengganti pemenang.
"""
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from ._advanced import InputError, integer, json_main, labels, rows, shape, text, unique
from .brier_scorer import _rational


MAX_METHODS = 16
MAX_CASES = 1_000


@dataclass(frozen=True, slots=True)
class Scorecard:
    method: str
    case: str
    points: int
    cost: int
    elapsed_ms: int
    decision_ref: str
    score_ref: str

    @classmethod
    def read(cls, row):
        shape(row, ("method", "case", "points", "cost_units", "elapsed_ms", "decision_ref", "score_ref"))
        return cls(
            text(row["method"], "metode"), text(row["case"], "kasus"),
            integer(row["points"], 0, 100), integer(row["cost_units"], 0, 10**9),
            integer(row["elapsed_ms"], 0, 86_400_000), text(row["decision_ref"], "sumber putusan"),
            text(row["score_ref"], "sumber penilaian"),
        )

    def export(self):
        return {"method": self.method, "case": self.case, "points": self.points,
                "cost_units": self.cost, "elapsed_ms": self.elapsed_ms,
                "decision_ref": self.decision_ref, "score_ref": self.score_ref}


def _pair(left, right, cases, observed):
    trials = []
    value_a = value_b = ties = 0
    for case in cases:
        a, b = observed[left, case], observed[right, case]
        delta = a.points - b.points
        if delta > 0:
            value_a += 1
        elif delta < 0:
            value_b += 1
        else:
            ties += 1
        trials.append({"case": case, "difference": delta,
                       "left_score_ref": a.score_ref, "right_score_ref": b.score_ref})
    return {"left": left, "right": right, "left_wins": value_a, "right_wins": value_b, "ties": ties,
            "winner": left if value_a > value_b else right if value_b > value_a else None,
            "mean_point_delta": _rational(Fraction(sum(item["difference"] for item in trials), len(cases))),
            "trials": trials}


def _standings(methods, cases, observed, matches):
    points = defaultdict(int)
    match_wins = defaultdict(int)
    match_losses = defaultdict(int)
    for match in matches:
        left, right, winner = match["left"], match["right"], match["winner"]
        if winner is None:
            points[left] += 1
            points[right] += 1
        else:
            loser = right if winner == left else left
            points[winner] += 2
            match_wins[winner] += 1
            match_losses[loser] += 1
    totals = []
    for method in methods:
        scorecards = [observed[method, case] for case in cases]
        total = sum(scorecard.points for scorecard in scorecards)
        totals.append((method, points[method], total, scorecards))
    totals.sort(key=lambda row: (-row[1], -row[2], row[0]))

    output = []
    best = None
    rank = 0
    for number, (method, standing, total, scorecards) in enumerate(totals, 1):
        if (standing, total) != best:
            rank = number
            best = standing, total
        output.append({
            "method": method, "rank": rank, "match_points": standing, "pair_wins": match_wins[method],
            "pair_losses": match_losses[method], "mean_quality": _rational(Fraction(total, len(cases))),
            "total_cost_units": sum(row.cost for row in scorecards),
            "total_elapsed_ms": sum(row.elapsed_ms for row in scorecards),
            "scorecards": [row.export() for row in scorecards],
        })
    return output


def _influence(methods, cases, observed, matches, original):
    if len(cases) < 2:
        return []
    totals = {method: sum(observed[method, case].points for case in cases) for method in methods}
    output = []
    for case in cases:
        points = dict.fromkeys(methods, 0)
        for match in matches:
            left, right = match["left"], match["right"]
            a, b = observed[left, case].points, observed[right, case].points
            gap = match["left_wins"] - match["right_wins"] - ((a > b) - (a < b))
            points[left] += 2 if gap > 0 else int(gap == 0)
            points[right] += 2 if gap < 0 else int(gap == 0)
        rank = {method: (points[method], totals[method] - observed[method, case].points)
                for method in methods}
        best = max(rank.values())
        leaders = [method for method in methods if rank[method] == best]
        output.append({"case_removed": case, "leading_methods": leaders, "leader_set_changed": leaders != original})
    return output


def run_tournament(raw):
    shape(raw, ("methods", "cases", "rubric_ref", "scorecards"))
    methods = sorted(labels(raw["methods"], 2, MAX_METHODS, "metode"))
    cases = sorted(labels(raw["cases"], 1, MAX_CASES, "kasus"))
    rubric = text(raw["rubric_ref"], "rubrik")
    expected = {(method, case) for method in methods for case in cases}
    observed, references = {}, {rubric}
    for row in rows(raw["scorecards"], 0, len(expected)):
        scorecard = Scorecard.read(row)
        key = scorecard.method, scorecard.case
        if key not in expected or key in observed:
            raise InputError("Scorecard tidak ada di jadwal atau tercatat dua kali.")
        unique(scorecard.decision_ref, references)
        unique(scorecard.score_ref, references)
        observed[key] = scorecard
    missing = [{"method": method, "case": case} for method, case in sorted(expected - observed.keys())]
    common = {"schema": "ace.method-tournament.v1", "rubric_ref": rubric,
              "methods": methods, "cases": cases, "missing_scorecards": missing}
    if missing:
        return {**common, "status": "incomplete", "standings": [], "matches": [],
                "leading_methods": [], "case_influence": []}
    matches = [_pair(a, b, cases, observed) for a, b in combinations(methods, 2)]
    standings = _standings(methods, cases, observed, matches)
    leaders = [row["method"] for row in standings if row["rank"] == 1]
    return {**common, "status": "complete" if len(leaders) == 1 else "tied",
            "standings": standings, "matches": matches, "leading_methods": leaders,
            "case_influence": _influence(methods, cases, observed, matches, leaders)}


def main(argv=None):
    return json_main(argv, __doc__, run_tournament)


if __name__ == "__main__":
    raise SystemExit(main())
