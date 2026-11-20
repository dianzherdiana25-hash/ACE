"""Uji lipatan 38 proposal dan kelas konservatif untuk multi-gap."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.director_fold import fold_proposals


def row(task_id, refs, day):
    return {"task_id": task_id, "based_on": refs, "status": "WAITING_FOR_DEPENDENCY",
            "created_at": f"2026-11-{day:02d}T00:00:00Z"}


def triage_fixture():
    rows = [row(f"largest-{i}", ["g0"], i + 1) for i in range(11)]
    for group in range(1, 10):
        for i in range(3 if group < 9 else 2):
            rows.append(row(f"g{group}-{i}", [f"g{group}"], i + 1))
    rows.append({**row("multi", ["g0", "g1"], 1), "evidence_refs": ["r"],
                 "touches_money": False, "touches_publication": False, "touches_external": False,
                 "reversible": True})
    return rows


class DirectorFoldTests(unittest.TestCase):
    def test_38_fixture_proposals_determine_11_groups(self):
        rows = triage_fixture()
        plan = fold_proposals(rows[::-1])
        self.assertEqual(plan, fold_proposals(rows))
        self.assertEqual((plan["proposal_count"], len(plan["groups"])), (38, 11))
        large = plan["groups"][0]
        self.assertEqual((large["representative"], len(large["duplicates"])), ("largest-0", 10))
        multi, = [group for group in plan["groups"] if group["kind"] == "multi_gap"]
        self.assertEqual((multi["representative"], multi["initial_class"]), ("multi", "B"))

    def test_restrictive_class_survives_folding_and_cli_keeps_bytes(self):
        rows = [row("old", ["g"], 1), {**row("new", ["g"], 2), "touches_external": True}]
        with TemporaryDirectory() as directory:
            source = Path(directory) / "proposals.jsonl"
            data = b"".join((json.dumps(item) + "\n").encode() for item in rows)
            source.write_bytes(data)
            run = subprocess.run([sys.executable, str(Path(__file__).with_name("director_fold.py")),
                                  str(source)], check=True, capture_output=True, text=True)
            group, = json.loads(run.stdout)["groups"]
            self.assertEqual((group["representative"], group["initial_class"]), ("old", "C"))
            self.assertEqual(source.read_bytes(), data)

    def test_plan_mode_on_38_triage_proposals_yields_11_representatives_and_exact_duplicate_counts(self):
        rows = triage_fixture()
        with TemporaryDirectory() as directory:
            source = Path(directory) / "triage_38.jsonl"
            raw = "".join(json.dumps(item) + "\n" for item in rows).encode("utf-8")
            source.write_bytes(raw)
            run = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("director_fold.py")), str(source), "--plan"],
                check=True,
                capture_output=True,
                text=True,
            )
            plan = json.loads(run.stdout)
            self.assertEqual(plan["mode"], "plan_only")
            self.assertTrue(plan["read_only"])
            self.assertEqual(plan["proposal_count"], 38)
            self.assertEqual(plan["representative_count"], 11)
            self.assertEqual(plan["duplicate_count"], 27)
            self.assertEqual(plan["umbrella_count"], 1)
            self.assertEqual(len(plan["representatives"]), 11)
            self.assertEqual(plan["umbrella_groups"][0]["representative"], "multi")
            self.assertEqual(plan["umbrella_groups"][0]["based_on"], ["g0", "g1"])

            by_rep = plan["duplicates_by_group"]
            self.assertEqual(by_rep["largest-0"]["duplicate_count"], 10)
            for g in range(1, 9):
                self.assertEqual(by_rep[f"g{g}-0"]["duplicate_count"], 2)
            self.assertEqual(by_rep["g9-0"]["duplicate_count"], 1)
            self.assertEqual(by_rep["multi"]["duplicate_count"], 0)
            self.assertEqual(source.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
