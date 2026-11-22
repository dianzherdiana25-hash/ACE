"""Ukur artefak native dan hasil latihan pada learner simulasi dengan kunci terpisah."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._artifacts import evidence
from ._contracts import (ProductionError, anchor, canonical, decode, identifier, identity,
                         digest, integer, items, obj, read, schema, source_bytes)
from .artifact_qa import audit
from .chart_builder import make_chart
from .document_builder import make_document
from .exercise_generator import OPERATIONS, generate
from .grader import assess
from .misconception_tracker import track
from .sheet_builder import make_workbook
from .slide_builder import make_slides


def _asset_set(spec, stage):
    obj(spec, ("document", "workbook", "slides", "chart"))
    files, _ = make_document(spec["document"], identity(spec["document"]))
    workbook, _ = make_workbook(spec["workbook"], identity(spec["workbook"]))
    slides, _ = make_slides(spec["slides"], identity(spec["slides"]))
    chart, _ = make_chart(spec["chart"], identity(spec["chart"]))
    files.update({"workbook.xlsx": workbook, "slides.pptx": slides, "chart.svg": chart})
    minimum = {"docx": {"paragraphs": 2, "tables": 1}, "pdf": {"pages": 1}, "xlsx": {"sheets": 1, "formulas": 1},
               "pptx": {"slides": 1}, "svg": {"accessible_title": 1}}
    rows = []
    for name, raw in sorted(files.items()):
        path = stage / name
        path.write_bytes(raw)
        kind = path.suffix[1:]
        rows.append({"path": name, "sha256": sha256(raw).hexdigest(), "format": kind, "minimum": minimum[kind]})
    if len(rows) != len(minimum):
        raise ProductionError("Bench perlu PDF, DOCX, XLSX, PPTX, dan SVG.")
    plan = {"schema": "ace.production.artifact-qa-plan.v1", "artifacts": rows}
    return files, audit(plan, identity(plan), stage)


def _signatures(result):
    values = []
    questions = {row["id"]: row for row in result["questions"]}
    for row in [*result["practice_key"], *result["held_out_key"]]:
        args = row["operands"]
        if row["method"] in ("addition", "multiplication"):
            args = sorted(args)
        values.append((questions[row["id"]]["topic"], row["method"], *args))
    return set(values)


def _respond(problem, topic, learner):
    familiarity = learner.get(topic, 0)
    op = problem["method"]
    a, b = problem["operands"]
    if familiarity >= problem["level"]:
        return str(OPERATIONS[op](a, b))
    if op == "addition":
        return str(a - b)
    return str(a + b)


def _score(result, levels):
    question_by_id = {row["id"]: row for row in result["questions"]}
    rows = []
    for card in result["held_out_key"]:
        question = question_by_id[card["id"]]
        reply = _respond(card | {"level": question["level"]}, question["topic"], levels)
        rows.append({"id": card["id"], "level": question["level"], "topic": question["topic"],
                     "question_sha256": card["question_sha256"], "prediction": reply,
                     "matches_key": reply == card["answer"]})
    if not rows:
        raise ProductionError("Bench learner memerlukan butir held-out yang benar-benar dinilai.")
    return rows


def _simulate(spec):
    obj(spec, ("pre", "post", "initial_knowledge", "interventions"))
    tools = {phase: generate(spec[phase], identity(spec[phase])) for phase in ("pre", "post")}
    if _signatures(tools["pre"]) & _signatures(tools["post"]):
        raise ProductionError("Soal sebelum dan sesudah berbagi operand dan konsep yang sama.")
    prior = {}
    for item in items(spec["initial_knowledge"], 30, 1):
        obj(item, ("topic", "level"))
        label = identifier(item["topic"], "Topik learner simulasi")
        if label in prior:
            raise ProductionError("Topik learner simulasi ganda.")
        prior[label] = integer(item["level"], "Penguasaan awal", 0, 8)
    final = dict(prior)
    intervention = []
    seen = set()
    for row in items(spec["interventions"], 30, 1):
        obj(row, ("id", "topic", "increment_level"))
        key = identifier(row["id"], "Intervensi")
        topic = identifier(row["topic"], "Topik intervensi")
        if key in seen or topic not in final:
            raise ProductionError("Intervensi ganda atau topik belum terdaftar.")
        seen.add(key)
        delta = integer(row["increment_level"], "Asumsi kenaikan level", 1, 8)
        final[topic] = min(8, final[topic] + delta)
        intervention.append({**row, "later_level": final[topic]})
    pre = _score(tools["pre"], prior)
    post = _score(tools["post"], final)
    if sorted((row["topic"], row["level"]) for row in pre) != sorted((row["topic"], row["level"]) for row in post):
        raise ProductionError("Komposisi held-out pre/post tidak setara.")
    a, b = (sum(row["matches_key"] for row in title) for title in (pre, post))
    return {"before": pre, "after": post, "before_passed": a, "after_passed": b, "count_per_arm": len(pre),
            "gain_bp": (b - a) * 10000 // len(pre),
            "relative_gain_bp": (b - a) * 10000 // a if a else None,
            "model_assumptions": intervention, "scope": "deterministic_learner_simulation"}


def _diagnostics(spec, stage):
    obj(spec, ("grades", "tracker"))
    tracker = dict(spec["tracker"])
    tracker["grades"] = []
    for index, row in enumerate(items(spec["grades"], 48, 1), 1):
        obj(row, ("date", "grade"))
        plan = row["grade"]
        receipt = assess(plan, identity(plan))
        path = f"grade_{index:02d}.json"
        raw = canonical(receipt) + b"\n"
        (stage / path).write_bytes(raw)
        tracker["grades"].append({"path": path, "sha256": sha256(raw).hexdigest(), "date": row["date"]})
    return track(tracker, identity(tracker), stage)


def run_bench(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.bench-plan.v1", ("scope", "artifacts", "simulation", "diagnosis", "gold"))
    if plan["scope"] != "closed_fixture":
        raise ProductionError("Bench diimplementasikan untuk fixture tertutup.")
    pointer = obj(plan["gold"], ("path", "sha256"))
    truth = decode(source_bytes(root, pointer["path"], pointer["sha256"], 120000))
    schema(truth, "ace.teaching.bench-gold.v1", ("expected_recurring",))
    recurring = {identifier(value, "Miskonsepsi terlabel") for value in items(truth["expected_recurring"], 80, 1)}
    with TemporaryDirectory(prefix="ace-teaching-bench-") as temporary:
        stage = Path(temporary)
        assets, qa = _asset_set(plan["artifacts"], stage)
        diagnosis = _diagnostics(plan["diagnosis"], stage)
    simulations = _simulate(plan["simulation"])
    actual = {row["id"] for row in diagnosis["patterns"] if row["state"] == "recurring"}
    detection = len(actual & recurring) * 10000 // len(recurring)
    false_positives = sorted(actual - recurring)
    qa_rate = qa["pass_count"] * 10000 // qa["total"]
    learning_gain = simulations["relative_gain_bp"]
    groups = {"artifact_first_pass_bp": qa_rate, "simulation_gain_bp": simulations["gain_bp"],
              "simulation_relative_gain_bp": learning_gain, "misconception_detection_bp": detection}
    okay = qa_rate >= 9000 and learning_gain is not None and learning_gain >= 2500 and detection >= 8000 and not false_positives
    assets.update({"artifact_qa.json": canonical(qa) + b"\n", "learner_trials.json": canonical(simulations) + b"\n",
                   "diagnosis.json": canonical(diagnosis) + b"\n"})
    return assets, {"schema": "ace.teaching.bench-result.v1", "plan_sha256": expected, "scope": plan["scope"],
                    "status": "fixture_pass" if okay else "fixture_hold", "metrics": groups, "gold": pointer,
                    "false_positive_misconceptions": false_positives, "artifacts": evidence(assets),
                    "details": {"artifact_passed": qa["pass_count"], "artifact_count": qa["total"],
                                "learner_pre_passed": simulations["before_passed"], "learner_post_passed": simulations["after_passed"],
                                "learner_items_per_arm": simulations["count_per_arm"], "detected": len(actual & recurring),
                                "misconceptions_in_key": len(recurring)}}


def summarize_fixture(report, root):
    """Periksa bukti draf yang ditempatkan di workspace sebelum meringkasnya."""
    schema(report, "ace.teaching.bench-result.v1", ("plan_sha256", "scope", "status", "metrics", "gold",
                                                   "false_positive_misconceptions", "artifacts", "details"))
    if report["scope"] != "closed_fixture":
        raise ProductionError("Cakupan receipt pengajaran harus closed_fixture.")
    digest(report["plan_sha256"])
    artifact_types = ("artifact_qa.json", "chart.svg", "diagnosis.json", "document.docx", "document.pdf",
                      "learner_trials.json", "slides.pptx", "workbook.xlsx")
    obj(report["artifacts"], artifact_types)
    for filename, row in report["artifacts"].items():
        obj(row, ("sha256", "bytes"))
        length = integer(row["bytes"], "Ukuran artefak", 1, 12_000_000)
        raw = source_bytes(root, filename, row["sha256"], length)
        if len(raw) != length:
            raise ProductionError("Ukuran artefak tidak sama dengan receipt.")
    details = obj(report["details"], ("artifact_passed", "artifact_count", "learner_pre_passed", "learner_post_passed",
                                       "learner_items_per_arm", "detected", "misconceptions_in_key"))
    assets = integer(details["artifact_count"], "Jumlah artefak", 1, 16)
    passes = integer(details["artifact_passed"], "Artefak lulus", 0, assets)
    arm = integer(details["learner_items_per_arm"], "Jumlah soal per arm", 1, 1000)
    pre = integer(details["learner_pre_passed"], "Jawaban benar sebelum", 0, arm)
    post = integer(details["learner_post_passed"], "Jawaban benar sesudah", 0, arm)
    misconception = integer(details["misconceptions_in_key"], "Miskonsepsi", 1, 160)
    hits = integer(details["detected"], "Miskonsepsi terdeteksi", 0, misconception)
    metrics = {"artifact_first_pass_bp": 10000 * passes // assets, "simulation_gain_bp": 10000 * (post - pre) // arm,
               "simulation_relative_gain_bp": 10000 * (post - pre) // pre if pre else None,
               "misconception_detection_bp": 10000 * hits // misconception}
    if metrics != report["metrics"]:
        raise ProductionError("Metrik tidak sesuai dengan denominator di receipt.")
    relative = metrics["simulation_relative_gain_bp"]
    passed = metrics["artifact_first_pass_bp"] >= 9000 and relative is not None and relative >= 2500 and (
        metrics["misconception_detection_bp"] >= 8000 and not report["false_positive_misconceptions"])
    status = "fixture_pass" if passed else "fixture_hold"
    if report["status"] != status:
        raise ProductionError("Status receipt berbeda dari kriteria fixture.")
    return {"scope": report["scope"], "fixture_status": status, "metrics": metrics, "details": details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        files, report = run_bench(decode(read(args.plan)), args.expect_sha256, args.root)
        args.output.mkdir()
        for name, raw in files.items():
            (args.output / name).write_bytes(raw)
        (args.output / "run.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "fixture_pass")


if __name__ == "__main__":
    raise SystemExit(main())
