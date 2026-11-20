"""Buktikan kuorum dari daftar yang berhak dan bukti kehadiran per kelas masalah.

Organ yang hadir tanpa hak untuk kelas itu tidak ikut hitungan. Penarikan
karena konflik memengaruhi penyebut hanya bila kebijakan menyatakannya.
Ketentuan peran dan jumlah hadir diperiksa bersama.
"""
from dataclasses import dataclass
from fractions import Fraction
import json
from math import ceil
from pathlib import Path


MAX_MEMBERS = 5_000
MAX_CLASSES = 100
MAX_BYTES = 5_000_000


class QuorumError(ValueError):
    """Kebijakan, daftar pemilih, atau bukti hadir tidak sah."""


def _shape(row, keys):
    if not isinstance(row, dict) or row.keys() != set(keys):
        raise QuorumError("Field kuorum tidak sesuai skema.")


def _text(value, field, limit=96):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise QuorumError(f"{field} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise QuorumError(f"{field} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise QuorumError(f"Jumlah wajib bilangan bulat {low}–{high}.")
    return value


def _sequence(value, maximum, label):
    if not isinstance(value, list) or len(value) > maximum:
        raise QuorumError(f"{label} wajib larik berbatas.")
    return value


@dataclass(frozen=True, slots=True)
class Policy:
    minimum: int
    fraction: Fraction
    roles: dict[str, int]
    denominator: str

    @classmethod
    def from_dict(cls, row):
        _shape(row, ("minimum", "fraction", "roles", "denominator"))
        ratio = row["fraction"]
        _shape(ratio, ("numerator", "denominator"))
        divisor = _integer(ratio["denominator"], 1, MAX_MEMBERS)
        numerator = _integer(ratio["numerator"], 0, divisor)
        roles = row["roles"]
        if not isinstance(roles, dict) or len(roles) > MAX_CLASSES:
            raise QuorumError("roles wajib peta jumlah minimum.")
        role_counts = {_text(role, "peran"): _integer(count, 1, MAX_MEMBERS) for role, count in roles.items()}
        if len(role_counts) != len(roles):
            raise QuorumError("Peran ganda.")
        if row["denominator"] not in ("roster", "non_recused"):
            raise QuorumError("Penyebut kebijakan harus roster atau non_recused.")
        return cls(_integer(row["minimum"], 1, MAX_MEMBERS), Fraction(numerator, divisor),
                   role_counts, row["denominator"])


@dataclass(frozen=True, slots=True)
class Member:
    id: str
    role: str
    classes: frozenset[str]

    @classmethod
    def from_dict(cls, row):
        _shape(row, ("id", "role", "classes"))
        names = [_text(item, "kelas") for item in _sequence(row["classes"], MAX_CLASSES, "classes")]
        if not names or len(set(names)) != len(names):
            raise QuorumError("Kelas wewenang kosong atau ganda.")
        return cls(_text(row["id"], "id"), _text(row["role"], "peran"), frozenset(names))


@dataclass(frozen=True, slots=True)
class Attendance:
    id: str
    status: str
    ref: str

    @classmethod
    def from_dict(cls, row):
        _shape(row, ("id", "status", "source_ref"))
        if row["status"] not in ("present", "absent", "recused"):
            raise QuorumError("Status kehadiran tidak dikenal.")
        return cls(_text(row["id"], "id"), row["status"], _text(row["source_ref"], "rujukan", 512))


def _index(raw, parse, field):
    result = {}
    for row in _sequence(raw, MAX_MEMBERS, field):
        item = parse(row)
        if item.id in result:
            raise QuorumError(f"ID ganda dalam {field}.")
        result[item.id] = item
    return result


def check_quorum(raw):
    """Kembalikan syarat dan bukti yang membentuk keputusan kuorum."""
    _shape(raw, ("problem_class", "policies", "roster", "attendance"))
    problem = _text(raw["problem_class"], "kelas masalah")
    policies = raw["policies"]
    if not isinstance(policies, dict) or not 1 <= len(policies) <= MAX_CLASSES:
        raise QuorumError("Kebijakan wajib peta kelas berbatas.")
    if problem not in policies:
        raise QuorumError("Kelas tanpa kebijakan kuorum.")
    policy = Policy.from_dict(policies[problem])
    roster = _index(raw["roster"], Member.from_dict, "roster")
    records = _index(raw["attendance"], Attendance.from_dict, "attendance")
    if records.keys() - roster.keys():
        raise QuorumError("Bukti hadir merujuk peserta yang tidak terdaftar.")
    if len({record.ref for record in records.values()}) != len(records):
        raise QuorumError("Rujukan kehadiran ganda.")

    eligible = {identifier for identifier, item in roster.items() if problem in item.classes}
    status = {state: sorted(identifier for identifier in eligible
                            if identifier in records and records[identifier].status == state)
              for state in ("present", "absent", "recused")}
    population = len(eligible) - (len(status["recused"]) if policy.denominator == "non_recused" else 0)
    fractional = ceil(policy.fraction * population)
    needed = max(policy.minimum, fractional)
    present = status["present"]
    role_results = []
    for name, count in sorted(policy.roles.items()):
        observed = sum(roster[identifier].role == name for identifier in present)
        role_results.append({"role": name, "required": count, "present": observed,
                             "met": observed >= count})
    shortage = max(0, needed - len(present))
    evidence = [{"id": identifier, "role": roster[identifier].role,
                 "eligible": identifier in eligible, "status": record.status, "source_ref": record.ref}
                for identifier, record in sorted(records.items())]
    return {"schema": "ace.quorum-engine.v1", "problem_class": problem,
            "quorum_met": not shortage and all(item["met"] for item in role_results),
            "denominator": {"policy": policy.denominator, "count": population},
            "fraction": {"numerator": policy.fraction.numerator,
                         "denominator": policy.fraction.denominator},
            "threshold": {"minimum": policy.minimum, "fractional": fractional, "required": needed},
            "present_count": len(present), "shortage": shortage, "by_status": status,
            "eligible_without_attendance": sorted(eligible - records.keys()),
            "ineligible": sorted(roster.keys() - eligible),
            "role_requirements": role_results, "attendance_evidence": evidence}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise QuorumError("Berkas kuorum melampaui batas.")
        result = check_quorum(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(not result["quorum_met"])


if __name__ == "__main__":
    raise SystemExit(main())
