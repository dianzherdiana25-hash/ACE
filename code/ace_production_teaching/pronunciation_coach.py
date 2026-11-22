"""Berikan latihan pengucapan dari perbedaan unit teks transkrip, dengan posisi dan sumber."""
import re
import unicodedata

from ._contracts import ProductionError, anchor, cli, items, obj, schema, text


UNITS = re.compile(r"ng|ny|sy|kh|[a-z]", re.ASCII)
VOWELS = set("aiueo")


def _tokens(value):
    clean = unicodedata.normalize("NFKD", value.casefold())
    cleaned = "".join(char for char in clean if not unicodedata.combining(char))
    words = re.findall(r"[a-z]+", cleaned, re.ASCII)
    tokens = [(unit[0], position) for position, word in enumerate(words, 1) for unit in UNITS.finditer(word)]
    if not tokens or len(tokens) > 500:
        raise ProductionError("Transkrip perlu 1–500 unit alfabet Latin.")
    return tokens


def _align(target, actual):
    m, n = len(target), len(actual)
    distance = [[0] * (n + 1) for _ in range(m + 1)]
    moves = {}
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 or j == 0:
                distance[i][j] = 2 * (i + j)
                moves[i, j] = "omit" if i else "extra"
                continue
            a, b = target[i - 1][0], actual[j - 1][0]
            cost = 0 if a == b else (1 if a in VOWELS and b in VOWELS else 2)
            winner, _, kind = min((distance[i - 1][j - 1] + cost, 0, "match" if not cost else "substitute"),
                                  (distance[i - 1][j] + 2, 1, "omit"), (distance[i][j - 1] + 2, 2, "extra"))
            distance[i][j] = winner
            moves[i, j] = kind
    found = []
    i, j = m, n
    while i or j:
        move = moves[i, j]
        target_unit = target[i - 1] if move != "extra" else None
        observed = actual[j - 1] if move != "omit" else None
        if move != "match":
            found.append({"kind": move, "target": None if target_unit is None else target_unit[0],
                          "target_word": None if target_unit is None else target_unit[1],
                          "observed": None if observed is None else observed[0],
                          "observed_word": None if observed is None else observed[1]})
        i -= move != "extra"
        j -= move != "omit"
    return distance[m][n], list(reversed(found))


def coach(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.pronunciation-plan.v1", ("language", "target", "attempt", "exercises"))
    if plan["language"] != "id":
        raise ProductionError("Peta grapheme tersedia untuk bahasa Indonesia.")
    refs = []
    for label in ("target", "attempt"):
        item = obj(plan[label], ("transcript", "source_ref"))
        refs.append((text(item["source_ref"], "Pointer transkrip"), _tokens(text(item["transcript"], "Transkrip", 1600))))
    distance, suggestions = _align(refs[0][1], refs[1][1])
    activities = {}
    for row in items(plan["exercises"], 100):
        obj(row, ("unit", "prompt", "source_ref"))
        key = row["unit"]
        if not isinstance(key, str) or not UNITS.fullmatch(key) or key in activities:
            raise ProductionError("Unit latihan ganda atau tidak dikenal.")
        activities[key] = {"prompt": text(row["prompt"], "Arahan artikulasi", 350),
                           "source_ref": text(row["source_ref"], "Pointer latihan")}
    for item in suggestions:
        item["practice"] = activities.get(item["target"])
    denominator = max(len(refs[0][1]), len(refs[1][1])) * 2
    return {"schema": "ace.teaching.transcript-coaching.v1", "plan_sha256": expected, "language": "id",
            "basis": "weighted_grapheme_alignment", "target_ref": refs[0][0], "attempt_ref": refs[1][0],
            "weighted_distance": distance, "similarity_bp": max(0, (denominator - distance) * 10000 // denominator),
            "mismatches": suggestions}


if __name__ == "__main__":
    raise SystemExit(cli(coach, __doc__))
