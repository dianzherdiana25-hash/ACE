"""Turunkan penjelasan aritmetika dari operand, serta cek kembali kunci yang terikat soal."""
from decimal import Decimal

from ._contracts import ProductionError, anchor, cli, fmt, identifier, identity, items, schema
from .exercise_generator import OPERATIONS, generate


def _steps(method, a, b, result):
    if method == "addition":
        return [{"label": "add_first_component", "operation": f"{a} + {b}", "result": result},
                {"label": "verify_by_subtraction", "operation": f"{result} - ({b})", "result": a}]
    if method == "difference":
        return [{"label": "subtract_second_component", "operation": f"{a} - ({b})", "result": result},
                {"label": "verify_by_addition", "operation": f"{result} + ({b})", "result": a}]
    if method == "multiplication":
        return [{"label": "multiply_factors", "operation": f"{a} × {b}", "result": result},
                {"label": "swap_factors", "operation": f"{b} × {a}", "result": result}]
    return [{"label": "divide_evenly", "operation": f"{a} ÷ {b}", "result": result},
            {"label": "check_remainder", "operation": f"{a} - ({b} × {result})", "result": 0}]


def explain_answers(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.explained-key-plan.v1", ("generator", "ids", "expected_key_sha256"))
    exercise = generate(plan["generator"], identity(plan["generator"]))
    all_keys = exercise["practice_key"] + exercise["held_out_key"]
    if identity(all_keys) != plan["expected_key_sha256"]:
        raise ProductionError("Kunci tidak cocok dengan anchor paket.")
    bank = {row["id"]: row for row in exercise["questions"]}
    keys = {row["id"]: row for row in all_keys}
    ids = [identifier(label, "Butir kunci") for label in items(plan["ids"], 200, 1)]
    if len(set(ids)) != len(ids) or not set(ids) <= keys.keys():
        raise ProductionError("Kunci meminta ID ganda atau tidak terdaftar.")
    findings = []
    for name in ids:
        key = keys[name]
        a, b = key["operands"]
        method = key["method"]
        outcome = OPERATIONS[method](a, b)
        if fmt(Decimal(outcome)) != key["answer"] or identity(bank[name]) != key["question_sha256"]:
            raise ProductionError("Perhitungan ulang tidak sesuai kunci atau prompt.")
        findings.append({"id": name, "question_sha256": key["question_sha256"], "steps": _steps(method, a, b, outcome),
                         "answer": outcome, "unit": key["unit"], "source_ref": bank[name]["source_ref"]})
    return {"schema": "ace.teaching.explained-key.v1", "plan_sha256": expected,
            "upstream_key_sha256": plan["expected_key_sha256"], "items": findings, "instructor_only": True}


if __name__ == "__main__":
    raise SystemExit(cli(explain_answers, __doc__))
