"""Nilai acceptance produk dari kontrak dan observasi yang tertambat.

Setiap kriteria spesifikasi perlu satu aturan operasional dan observasi
sesuai produk. Judge membedakan gagal dan bukti hilang. Kelulusan
memerlukan semua kriteria yang disepakati, tanpa agregasi yang menutupi gap.
"""
import argparse
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, identity, integer, obj, read, schema, text


def _criteria(spec):
    schema(spec, "ace.factory-product-spec.v1", ("brief_sha256", "product_id", "name", "surface", "objective",
                                                "objective_ref", "requirements", "constraints", "non_goals", "pending", "status"))
    if spec["status"] != "ready" or spec["pending"]:
        raise ContractError("Spesifikasi punya kriteria yang belum jelas.")
    criteria = {}
    for need in entries(spec["requirements"], 500, minimum=1):
        obj(need, ("id", "statement", "source_ref", "acceptance"))
        key = identifier(need["id"], "ID kebutuhan")
        for row in entries(need["acceptance"], 120, minimum=1):
            obj(row, ("statement", "source_ref"))
            pointer = text(row["source_ref"], "Rujukan spesifikasi", 250)
            if pointer in criteria:
                raise ContractError("Rujukan kriteria tidak unik.")
            criteria[pointer] = key
    return criteria


def _match(operator, expected, observed):
    if operator == "equals":
        return identity(expected) == identity(observed)
    if operator == "at_least":
        minimum = integer(expected, "Minimal", -2**63, 2**63 - 1)
        return type(observed) is int and observed >= minimum
    if operator == "has_all_items":
        required = {identity(item) for item in entries(expected, 200, minimum=1)}
        return isinstance(observed, list) and required <= {identity(item) for item in observed}
    raise ContractError("Jenis pembanding acceptance belum didukung.")


def _observations(observations, spec, expected, artifact):
    schema(observations, "ace.factory-observations.v1", ("product_id", "contract_sha256", "artifact_sha256", "records"))
    if observations["product_id"] != spec["product_id"] or observations["contract_sha256"] != expected:
        raise ContractError("Observasi memiliki identitas produk atau acceptance berbeda.")
    if observations["artifact_sha256"] != artifact:
        raise ContractError("Observasi menunjuk artefak yang berbeda.")
    records = {}
    for row in entries(observations["records"], 1000):
        obj(row, ("id", "value", "source_ref"))
        key = identifier(row["id"], "ID observasi")
        if key in records:
            raise ContractError("Observasi ganda.")
        records[key] = (row["value"], text(row["source_ref"], "Rujukan observasi", 250))
    return records


def evaluate(spec, contract, observed, expected, observation_anchor, artifact_anchor):
    checked(contract, expected)
    checked(observed, observation_anchor)
    checked(spec, contract.get("spec_sha256"))
    spec_items = _criteria(spec)
    digest(artifact_anchor)
    schema(contract, "ace.factory-acceptance-contract.v1", ("spec_sha256", "source_ref", "rules"))
    contract_ref = text(contract["source_ref"], "Rujukan rencana uji", 250)
    rules, names = {}, set()
    for row in entries(contract["rules"], 1000):
        obj(row, ("id", "criterion_ref", "operator", "expected", "source_ref"))
        name = identifier(row["id"], "ID aturan")
        key = text(row["criterion_ref"], "Rujukan kriteria", 250)
        if name in names or key in rules or key not in spec_items:
            raise ContractError("Aturan ganda atau rujukan kriteria tidak dikenal.")
        names.add(name)
        if row["operator"] == "at_least":
            integer(row["expected"], "Paling sedikit", -2**63, 2**63 - 1)
        elif row["operator"] == "has_all_items":
            entries(row["expected"], 200, minimum=1)
        elif row["operator"] != "equals":
            raise ContractError("Jenis pembanding acceptance belum didukung.")
        rules[key] = {"id": name, "operator": row["operator"], "expected": row["expected"],
                      "source_ref": text(row["source_ref"], "Rujukan aturan", 250)}
    records = _observations(observed, spec, expected, artifact_anchor)
    unexpected = sorted(records.keys() - names)
    outcomes = []
    for key, requirement in sorted(spec_items.items()):
        output = {"criterion_ref": key, "requirement": requirement}
        if key not in rules:
            outcomes.append({**output, "status": "missing_rule"})
            continue
        rule = rules[key]
        output.update({"rule": rule["id"], "rule_ref": rule["source_ref"], "expected_sha256": identity(rule["expected"])})
        if rule["id"] not in records:
            outcomes.append({**output, "status": "missing_observation"})
            continue
        value, pointer = records[rule["id"]]
        matched = _match(rule["operator"], rule["expected"], value)
        outcomes.append({**output, "observed_sha256": identity(value), "observed_ref": pointer,
                         "status": "passed" if matched else "failed"})
    counts = {key: sum(row["status"] == key for row in outcomes)
              for key in ("passed", "failed", "missing_rule", "missing_observation")}
    if counts["failed"]:
        status = "failed"
    elif unexpected or counts["missing_rule"] or counts["missing_observation"]:
        status = "incomplete"
    else:
        status = "passed"
    return {"schema": "ace.factory-acceptance-report.v1", "product_id": spec["product_id"], "artifact_sha256": artifact_anchor,
            "spec_sha256": contract["spec_sha256"], "contract_sha256": expected, "contract_ref": contract_ref,
            "observations_sha256": observation_anchor, "counts": counts, "results": outcomes,
            "unexpected_observations": unexpected, "status": status}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("spec", "contract", "observations"):
        parser.add_argument(name, type=Path)
    for name in ("contract-sha256", "observations-sha256", "artifact-sha256"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    try:
        output = evaluate(*(decode(read(getattr(args, name))) for name in ("spec", "contract", "observations")),
                          args.contract_sha256, args.observations_sha256, args.artifact_sha256)
        sys.stdout.buffer.write(canonical(output) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(output["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
