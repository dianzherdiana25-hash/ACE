"""Audit ref pada keputusan yang berubah lewat modul recall dan anchor asli."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from ace_operational.memory_anchor import check_anchors
from tools.recall_ablation import run_ablation


FIXTURE = Path(__file__).parent / "fixtures" / "recall_anchor_audit.json"


def fixture_audit(fixture, store):
    tasks = {task["id"]: task for task in fixture["tasks"]}
    data, _ = run_ablation(fixture["store"], list(tasks.values()), seed=17)
    decisions = {}
    for line in data.splitlines():
        row = json.loads(line)
        decisions.setdefault(row["task_id"], {})[row["arm"]] = row["decision"]
    return {"changed_decisions": [
        {"task_id": task_id, "active": arms["active"], "off": arms["off"],
         "anchor": check_anchors(tasks[task_id]["based_on"], store)}
        for task_id, arms in sorted(decisions.items()) if arms["active"] != arms["off"]
    ]}


class RecallAnchorAuditTests(unittest.TestCase):
    def test_fixture_json_marks_exact_dangling_reference(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        store = Mock()
        store.verify_ref.side_effect = set(fixture["verified_refs"]).__contains__
        report = fixture_audit(fixture, store)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "audit.json"
            output.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), fixture["expected"])
        self.assertEqual([call.args[0] for call in store.verify_ref.call_args_list],
                         ["receipt-clean", "receipt-partial", "receipt-missing"])


if __name__ == "__main__":
    unittest.main()
