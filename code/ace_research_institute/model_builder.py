"""Pasang regresi linier lokal dan nilai terhadap baseline pada baris holdout eksplisit."""
from decimal import Decimal, localcontext
from fractions import Fraction

from ._contracts import ResearchError, anchor, cli, fmt, identifier, integer, items, obj, schema, source_bytes
from ._tabular import NUMBERS, load


def _solve(matrix, vector):
    system = [[*row, outcome] for row, outcome in zip(matrix, vector, strict=True)]
    n = len(system)
    for axis in range(n):
        pivot = max(range(axis, n), key=lambda index: abs(system[index][axis]))
        scale = system[pivot][axis]
        if not scale:
            raise ResearchError("Matriks training singular dan koefisien tidak teridentifikasi.")
        system[pivot], system[axis] = system[axis], system[pivot]
        column = [value / scale for value in system[axis]]
        system[axis] = column
        for index, row in enumerate(system):
            if index == axis or not row[axis]:
                continue
            multiple = row[axis]
            system[index] = [value - multiple * baseline for value, baseline in zip(row, column, strict=True)]
    return [row[-1] for row in system]


def _regression(observations, axes):
    xtx = [[Fraction(0) for _ in range(axes)] for _ in range(axes)]
    xty = [Fraction(0) for _ in range(axes)]
    for profile, response, _ in observations:
        for i, bound in enumerate(profile):
            for j in range(i + 1):
                xtx[i][j] += bound * profile[j]
            xty[i] += bound * response
    for i in range(axes):
        for j in range(i):
            xtx[j][i] = xtx[i][j]
    return _solve(xtx, xty)


def _decimal(value):
    with localcontext() as context:
        context.prec = 25
        return fmt(Decimal(value.numerator) / Decimal(value.denominator))


def fit(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.regression-plan.v1", ("data", "format", "features", "target", "training_through_line"))
    link = obj(plan["data"], ("path", "sha256"))
    table = load(source_bytes(root, link["path"], link["sha256"], 3_000_000), link["sha256"], plan["format"])
    features = [identifier(value, "Fitur") for value in items(plan["features"], 6, 1)]
    y = identifier(plan["target"], "Target")
    if len(set(features)) != len(features) or y in features or any(
            key not in table.columns or table.columns[key][0] not in NUMBERS for key in [*features, y]):
        raise ResearchError("Fitur dan target numerik harus terdaftar dan berbeda.")
    cutoff = integer(plan["training_through_line"], "Batas baris train", 2, 100_001)
    train, holdout, incomplete = [], [], []
    if len(table.rows) > 20_000:
        raise ResearchError("Regresi eksak melampaui anggaran jumlah baris.")
    for row in table.rows:
        cells = row["cells"]
        if row["line"] <= cutoff < row["end_line"]:
            raise ResearchError("Split memotong record CSV lintas baris.")
        if any(cells[key] is None for key in [*features, y]):
            incomplete.append(row["line"])
            continue
        details = ([Fraction(1), *(Fraction(cells[key]) for key in features)], Fraction(cells[y]), row["line"])
        (train if row["line"] <= cutoff else holdout).append(details)
    axes = len(features) + 1
    if len(train) <= axes or not holdout:
        raise ResearchError("Training harus melampaui jumlah koefisien serta memiliki baris holdout.")
    coef = _regression(train, axes)
    mean = sum(value for _, value, _ in train) / len(train)
    scores = []
    comparisons = []
    for profile, actual, line in holdout:
        predicted = sum(a * b for a, b in zip(profile, coef, strict=True))
        errors = (abs(predicted - actual), abs(mean - actual))
        scores.append(errors)
        comparisons.append({"line": line, "actual": _decimal(actual), "prediction": _decimal(predicted),
                            "abs_error": _decimal(errors[0]), "baseline_abs_error": _decimal(errors[1])})
    actual_mae, baseline_mae = [sum(row) / len(holdout) for row in zip(*scores, strict=True)]
    return {"schema": "ace.institute.linear-fit.v1", "plan_sha256": expected, "source": link,
            "method": "linear_least_squares_exact_fraction", "split": cutoff, "target": y,
            "coefficient": {"intercept": _decimal(coef[0]), **{key: _decimal(value) for key, value in zip(features, coef[1:], strict=True)}},
            "training_n": len(train), "holdout_n": len(holdout), "training_target_mean": _decimal(mean),
            "holdout_mae": _decimal(actual_mae), "baseline_mae": _decimal(baseline_mae), "delta_mae": _decimal(actual_mae - baseline_mae),
            "predictions": comparisons, "missing_lines": incomplete, "rejected": list(table.rejected)}


if __name__ == "__main__":
    raise SystemExit(cli(fit, __doc__, rooted=True))
