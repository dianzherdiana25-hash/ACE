"""Putar ulang eksperimen tempa dari kronologi receipt yang direkam.

Riwayat mengikat resep, dataset, kejadian, checkpoint, dan pemakaian
unit internal. State pause dan resume direkonstruksi per eksperimen.
Overspend tercatat sebagai temuan atas receipt yang masuk, sehingga
hasil gagal dan penggunaan berlebih tetap terlihat untuk audit.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_EVENTS = 40_000
MAX_UNITS = 10**12
SIGNALS = {
    "start": ({"planned"}, "running"),
    "checkpoint": ({"running"}, "running"),
    "pause": ({"running"}, "paused"),
    "resume": ({"paused"}, "running"),
    "finish": ({"running"}, "completed"),
    "fail": ({"running", "paused"}, "failed"),
}


@dataclass(slots=True)
class Experiment:
    key: str
    ref: str
    recipe: str
    dataset: str
    budget: int
    updated: datetime
    status: str = "planned"
    charged: int = 0
    attempts: int = 0
    events: list = field(default_factory=list)
    checkpoints: list = field(default_factory=list)
    seen_shas: set = field(default_factory=set)
    terminal_ref: str | None = None

    @classmethod
    def read(cls, key, raw, now, refs):
        object_fields(raw, ("plan_ref", "recipe_sha256", "dataset_sha256", "budget_units"))
        return cls(key, reference(raw["plan_ref"], refs, "rujukan rencana"), digest(raw["recipe_sha256"]),
                   digest(raw["dataset_sha256"]), integer(raw["budget_units"], 0, MAX_UNITS), now)

    def _details(self, action, raw, refs):
        if action == "start":
            object_fields(raw, ("runner_ref",))
            runner = reference(raw["runner_ref"], refs, "rujukan runner")
            self.attempts += 1
            return {"runner_ref": runner}
        if action == "checkpoint":
            object_fields(raw, ("checkpoint_sha256", "checkpoint_ref", "spent_delta_units"))
            checkpoint = digest(raw["checkpoint_sha256"])
            if checkpoint in self.seen_shas:
                raise InputError("Checkpoint ganda pada eksperimen.")
            spent = integer(raw["spent_delta_units"], 0, MAX_UNITS)
            result = {"checkpoint_sha256": checkpoint,
                      "checkpoint_ref": reference(raw["checkpoint_ref"], refs, "rujukan checkpoint"),
                      "spent_delta_units": spent}
            self.charged += spent
            self.seen_shas.add(checkpoint)
            self.checkpoints.append(result)
            return result
        if action == "pause":
            object_fields(raw, ("reason_ref",))
            return {"reason_ref": reference(raw["reason_ref"], refs, "rujukan pause")}
        if action == "resume":
            object_fields(raw, ("runner_ref", "checkpoint_sha256"))
            previous = self.checkpoints[-1]["checkpoint_sha256"] if self.checkpoints else None
            if raw["checkpoint_sha256"] != previous:
                raise InputError("Resume harus menunjuk checkpoint terakhir atau null sebelum checkpoint pertama.")
            runner = reference(raw["runner_ref"], refs, "rujukan runner")
            self.attempts += 1
            return {"runner_ref": runner, "checkpoint_sha256": previous}
        terminal = "result_ref" if action == "finish" else "diagnosis_ref"
        object_fields(raw, (terminal, "spent_delta_units"))
        spent = integer(raw["spent_delta_units"], 0, MAX_UNITS)
        self.terminal_ref = reference(raw[terminal], refs, "rujukan terminal")
        self.charged += spent
        return {terminal: self.terminal_ref, "spent_delta_units": spent}

    def apply(self, action, values, now, refs):
        if now < self.updated:
            raise InputError("Cap waktu mundur dalam eksperimen.")
        if action not in SIGNALS:
            raise InputError("Jenis kejadian eksperimen tidak dikenal.")
        allowed, next_status = SIGNALS[action]
        if self.status not in allowed:
            raise InputError("Peralihan state eksperimen tidak sah.")
        details = self._details(action, values, refs)
        self.status, self.updated = next_status, now
        return details

    def export(self):
        return {"experiment_id": self.key, "plan_ref": self.ref, "recipe_sha256": self.recipe,
                "dataset_sha256": self.dataset, "status": self.status, "attempts": self.attempts,
                "budget_units": self.budget, "spent_units": self.charged, "margin_units": self.budget - self.charged,
                "over_budget": self.charged > self.budget, "terminal_ref": self.terminal_ref,
                "checkpoints": self.checkpoints, "events": self.events, "updated_at": self.updated.isoformat()}


def audit(raw, expected):
    object_fields(raw, ("ledger_ref", "events"))
    if identity(raw) != digest(expected):
        raise InputError("Snapshot receipt berbeda dari anchor.")
    source = string(raw["ledger_ref"], "rujukan receipt")
    refs = {source}
    tracked = {}
    for index, row in enumerate(entries(raw["events"], MAX_EVENTS), 1):
        try:
            object_fields(row, ("id", "type", "at", "event_ref", "values"))
            key = string(row["id"], "ID eksperimen")
            action = string(row["type"], "jenis event")
            now = utc_stamp(row["at"])
            ref = reference(row["event_ref"], refs, "rujukan event")
            if action == "plan":
                if key in tracked:
                    raise InputError("ID eksperimen telah terdaftar.")
                item = Experiment.read(key, row["values"], now, refs)
                tracked[key] = item
                details = {"plan_ref": item.ref}
            else:
                item = tracked.get(key)
                if item is None:
                    raise InputError("Receipt mendahului rencana eksperimen.")
                details = item.apply(action, row["values"], now, refs)
            item.events.append({"index": index, "type": action, "event_ref": ref, "at": now.isoformat(), **details})
        except ValueError as exc:
            raise InputError(f"Event {index}: {exc}") from exc
    runs = [item.export() for _, item in sorted(tracked.items())]
    by_state = Counter(row["status"] for row in runs)
    overspent = [row["experiment_id"] for row in runs if row["over_budget"]]
    return {"schema": "ace.forge-experiment-audit.v1", "ledger_ref": source, "ledger_sha256": expected,
            "events": len(raw["events"]), "tracked": len(runs), "by_state": dict(sorted(by_state.items())),
            "total_budget_units": sum(item["budget_units"] for item in runs),
            "total_spent_units": sum(item["spent_units"] for item in runs),
            "over_budget_experiments": overspent, "experiments": runs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(decode(read_bytes(args.ledger, MAX_BYTES)), args.expect_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
