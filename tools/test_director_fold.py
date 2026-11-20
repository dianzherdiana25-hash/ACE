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


class DirectorFoldTests(unittest.TestCase):
    def test_38_fixture_proposals_determine_11_groups(self):
        rows = [row(f"largest-{i}", ["g0"], i + 1) for i in range(11)]
        for group in range(1, 10):
            for i in range(3 if group < 9 else 2):
                rows.append(row(f"g{group}-{i}", [f"g{group}"], i + 1))
        rows.append({**row("multi", ["g0", "g1"], 1), "evidence_refs": ["r"],
                     "touches_money": False, "touches_publication": False, "touches_external": False,
                     "reversible": True})
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
