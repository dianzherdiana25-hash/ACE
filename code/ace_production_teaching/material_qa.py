"""Nilai materi ajar dari cakupan tujuan, cuplikan sumber, kerahasiaan jawaban dan a11y."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, items, obj, schema, source_bytes, text
from .doc_a11y_checker import inspect_accessibility
from .hint_engine import leaks


def assess_material(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.material-plan.v1", ("material", "goals", "cards", "reserved_answers"))
    file = obj(plan["material"], ("path", "sha256"))
    audit = {"schema": "ace.production.doc-a11y-plan.v1", "file": file, "kind": "markdown"}
    structure = inspect_accessibility(audit, identity(audit), root)
    paragraphs = source_bytes(root, file["path"], file["sha256"], 1_000_000).decode("utf-8").splitlines()
    goals = {identifier(item, "Tujuan") for item in items(plan["goals"], 110, 1)}
    forbidden = [text(item, "Jawaban tertahan", 140) for item in items(plan["reserved_answers"], 40, 1)]
    exclusion = [{"line": index, "reason": "reserved_answer_present"} for index, row in enumerate(paragraphs, 1) if leaks(row, forbidden)]
    covered = set()
    result = []
    for row in items(plan["cards"], 200, 1):
        obj(row, ("goal", "material_phrase", "proof", "proof_excerpt"))
        topic = identifier(row["goal"], "Tujuan")
        if topic not in goals:
            raise ProductionError("Kartu materi merujuk tujuan yang belum dinyatakan.")
        evidence = obj(row["proof"], ("path", "sha256"))
        source = source_bytes(root, evidence["path"], evidence["sha256"], 200000).decode("utf-8")
        material_phrase = text(row["material_phrase"], "Petikan bahan", 120)
        proof = text(row["proof_excerpt"], "Petikan bukti", 300)
        lines = [index for index, row in enumerate(paragraphs, 1) if material_phrase in row]
        state = bool(lines) and proof in source
        if state:
            covered.add(topic)
        result.append({"goal": topic, "material_lines": lines, "source": evidence, "source_match": proof in source, "pass": state})
    missing = sorted(goals - covered)
    passed = not (missing or exclusion or structure["findings"])
    return {"schema": "ace.teaching.material-qa.v1", "plan_sha256": expected, "source": file,
            "status": "pass" if passed else "hold", "goal_coverage": result, "missing_goals": missing,
            "answer_findings": exclusion, "structural_findings": structure["findings"]}


if __name__ == "__main__":
    raise SystemExit(cli(assess_material, __doc__, rooted=True))
