"""Pilih portofolio pertanyaan ramalan di bawah batas sumber daya.

Pemanggil mendaftarkan nilai, biaya, serta kategori risiko yang boleh
bertumpang tindih. Pencarian eksak mengembalikan pilihan terbaik per
ukuran portofolio. Nilai lebih tinggi menang, lalu biaya lebih rendah,
lalu urutan ID unik. Batas ukuran input menjaga pencarian dapat diaudit.
"""
from collections import Counter
from dataclasses import dataclass

from ._advanced import InputError, integer, json_main, labels, rows, shape, text, unique


MAX_QUESTIONS = 20
MAX_UNITS = 1_000_000


@dataclass(frozen=True, slots=True)
class Question:
    key: str
    value: int
    cost: int
    groups: tuple
    ref: str

    @classmethod
    def read(cls, raw, caps):
        shape(raw, ("id", "value_units", "cost_units", "groups", "source_ref"))
        groups = tuple(sorted(labels(raw["groups"], 1, len(caps), "kategori")))
        if set(groups) - caps.keys():
            raise InputError("Kategori harus memiliki batas eksplisit.")
        return cls(text(raw["id"], "ID pertanyaan"), integer(raw["value_units"], 0, MAX_UNITS),
                   integer(raw["cost_units"], 0, MAX_UNITS), groups, text(raw["source_ref"], "rujukan pertanyaan"))


@dataclass(frozen=True, slots=True)
class Plan:
    value: int
    cost: int
    selected: tuple

    @property
    def rank(self):
        return (-self.value, self.cost, tuple(item.key for item in self.selected))

    def export(self):
        categories = Counter(group for item in self.selected for group in item.groups)
        return {"ids": [item.key for item in self.selected], "value_units": self.value,
                "cost_units": self.cost, "category_counts": dict(sorted(categories.items()))}


def _frontier(questions, budget, slots, caps):
    incumbent = {}
    used = Counter()
    selection = []

    def visit(start, value, cost):
        size = len(selection)
        record = Plan(value, cost, tuple(selection))
        prior = incumbent.get(size)
        if prior is None or record.rank < prior.rank:
            incumbent[size] = record
        if size == slots:
            return
        for index in range(start, len(questions)):
            item = questions[index]
            total_cost = cost + item.cost
            if total_cost > budget or any(used[group] >= caps[group] for group in item.groups):
                continue
            selection.append(item)
            used.update(item.groups)
            visit(index + 1, value + item.value, total_cost)
            used.subtract(item.groups)
            selection.pop()

    visit(0, 0, 0)
    return incumbent


def optimize(raw):
    shape(raw, ("protocol_ref", "budget", "max_questions", "category_limits", "questions"))
    protocol = text(raw["protocol_ref"], "rujukan protokol")
    budget = integer(raw["budget"], 0, MAX_UNITS * MAX_QUESTIONS)
    slots = integer(raw["max_questions"], 0, MAX_QUESTIONS)
    caps = {}
    for row in rows(raw["category_limits"], 1, 50):
        shape(row, ("id", "max"))
        group = text(row["id"], "kategori")
        if group in caps:
            raise InputError("Kategori ganda.")
        caps[group] = integer(row["max"], 0, MAX_QUESTIONS)
    identifiers, refs = set(), {protocol}
    questions = []
    for row in rows(raw["questions"], 0, MAX_QUESTIONS):
        item = Question.read(row, caps)
        unique(item.key, identifiers, "ID pertanyaan")
        unique(item.ref, refs)
        questions.append(item)
    questions.sort(key=lambda item: item.key)
    frontier = _frontier(questions, budget, slots, caps)
    best = min(frontier.values(), key=lambda record: record.rank)
    exported = best.export()
    remaining = budget - best.cost
    selected = set(exported["ids"])
    omitted = []
    for item in questions:
        if item.key in selected:
            continue
        blockers = []
        if len(selected) == slots:
            blockers.append("slots")
        if item.cost > remaining:
            blockers.append("budget")
        blockers.extend(f"category:{key}" for key in item.groups if exported["category_counts"].get(key, 0) == caps[key])
        omitted.append({"id": item.key, "source_ref": item.ref, "addition_blockers": blockers})
    return {
        "schema": "ace.question-portfolio.v1", "protocol_ref": protocol,
        "budget": budget, "max_questions": slots, "category_limits": dict(sorted(caps.items())),
        "chosen": {**exported, "unspent_budget": remaining}, "not_selected": omitted,
        "selected_questions": [{"id": item.key, "source_ref": item.ref, "groups": list(item.groups),
                                "value_units": item.value, "cost_units": item.cost} for item in best.selected],
        "frontier": [{"size": count, **record.export()} for count, record in sorted(frontier.items())],
    }


def main(argv=None):
    return json_main(argv, __doc__, optimize)


if __name__ == "__main__":
    raise SystemExit(main())
