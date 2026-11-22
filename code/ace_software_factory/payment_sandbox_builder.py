"""Simulasikan lifecycle pembayaran fiktif untuk verifier produk lokal.

Mesin memakai unit pengujian dan bersifat in-memory. Receipt dicetak
sebagai data pengujian, dengan penolakan, idempotency dan rekonsiliasi.
Tidak ada adapter pembayaran, credential atau pemanggilan eksternal.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text


MAX_UNITS = 10**12


@dataclass
class Authorization:
    account: str
    reserved: int
    captured: int = 0
    refunded: int = 0
    voided: bool = False


def _action(raw):
    operation = raw.get("kind") if isinstance(raw, dict) else None
    if operation == "authorize":
        obj(raw, ("id", "kind", "account", "units"))
        return (identifier(raw["id"], "ID event"), operation, identifier(raw["account"], "ID akun fixture"),
                integer(raw["units"], "Satuan fixture", 1, MAX_UNITS))
    if operation in ("capture", "refund"):
        obj(raw, ("id", "kind", "authorization", "units"))
        return (identifier(raw["id"], "ID event"), operation, identifier(raw["authorization"], "ID hold"),
                integer(raw["units"], "Satuan fixture", 1, MAX_UNITS))
    if operation == "void":
        obj(raw, ("id", "kind", "authorization"))
        return identifier(raw["id"], "ID event"), operation, identifier(raw["authorization"], "ID hold"), 0
    raise ContractError("Jenis event sandbox tidak dikenal.")


class Simulator:
    """State machine internal dengan konservasi saldo pada setiap event."""

    def __init__(self, accounts):
        self.available = dict(accounts)
        self.initial = dict(accounts)
        self.holds = {}
        self.ledger = {}
        self.events = []

    def _transition(self, key, operation, subject, units):
        if operation == "authorize":
            if subject not in self.available:
                return None, "account_missing"
            if self.available[subject] < units:
                return None, "insufficient_test_units"
            self.available[subject] -= units
            self.holds[key] = Authorization(subject, units)
            return key, None
        entry = self.holds.get(subject)
        if entry is None:
            return None, "authorization_missing"
        if operation == "capture":
            if entry.voided or entry.reserved < units:
                return subject, "capture_exceeds_hold"
            entry.reserved -= units
            entry.captured += units
        elif operation == "refund":
            if entry.captured - entry.refunded < units:
                return subject, "refund_exceeds_capture"
            entry.refunded += units
            self.available[entry.account] += units
        elif entry.voided or entry.reserved == 0:
            return subject, "no_hold_to_release"
        else:
            self.available[entry.account] += entry.reserved
            entry.reserved = 0
            entry.voided = True
        return subject, None

    def consume(self, raw):
        key, kind, subject, units = _action(raw)
        if key in self.ledger:
            original, index = self.ledger[key]
            reason = None if original == raw else "conflicting_event_id"
            record = {"id": key, "action": kind, "status": "duplicate" if reason is None else "rejected",
                      "reason": reason, "original_line": index, "authorization": None}
        else:
            self.ledger[key] = (raw, len(self.events) + 1)
            auth, reason = self._transition(key, kind, subject, units)
            record = {"id": key, "action": kind, "status": "accepted" if reason is None else "rejected",
                      "reason": reason, "original_line": None, "authorization": auth}
        self.events.append(record)
        return record

    def reconciliation(self):
        result = {}
        for key, initial in sorted(self.initial.items()):
            entries = [item for item in self.holds.values() if item.account == key]
            reserved = sum(item.reserved for item in entries)
            net = sum(item.captured - item.refunded for item in entries)
            available = self.available[key]
            result[key] = {"initial_units": initial, "available_units": available, "held_units": reserved,
                           "net_captured_units": net, "conserved": initial == available + reserved + net}
        return result


def simulate(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-payment-sandbox.v1", ("source_ref", "fixture_accounts", "events", "expected_receipts"))
    ref = text(plan["source_ref"], "Asal skenario", 220)
    balances = {}
    for row in entries(plan["fixture_accounts"], 100, minimum=1):
        obj(row, ("id", "units"))
        key = identifier(row["id"], "ID akun fixture")
        if key in balances:
            raise ContractError("Akun fixture ganda.")
        balances[key] = integer(row["units"], "Modal fixture", 0, MAX_UNITS)
    source = entries(plan["events"], 1500, minimum=1)
    assertions = entries(plan["expected_receipts"], 1500, minimum=1)
    if len(assertions) != len(source):
        raise ContractError("Setiap event memerlukan receipt yang diharapkan.")
    simulator = Simulator(balances)
    differences = []
    for index, (action, expected_receipt) in enumerate(zip(source, assertions), 1):
        obj(expected_receipt, ("status", "reason"))
        if expected_receipt["status"] not in ("accepted", "rejected", "duplicate"):
            raise ContractError("Status harapan receipt tidak dikenal.")
        observed = simulator.consume(action)
        pair = {key: observed[key] for key in ("status", "reason")}
        if pair != expected_receipt:
            differences.append({"line": index, "expected": expected_receipt, "observed": pair})
    final = simulator.reconciliation()
    status = "verified_fixture" if not differences and all(row["conserved"] for row in final.values()) else "failed_fixture"
    return {"schema": "ace.factory-payment-sandbox-report.v1", "plan_sha256": expected, "source_ref": ref,
            "units": "fixture_units", "receipts": simulator.events, "receipts_sha256": identity(simulator.events),
            "reconciliation": final, "differences": differences, "status": status}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = simulate(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "verified_fixture")


if __name__ == "__main__":
    raise SystemExit(main())
