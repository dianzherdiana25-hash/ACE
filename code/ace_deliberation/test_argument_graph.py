"""Uji bahwa jalur, siklus dan sumber argumen dapat diperiksa ulang."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import argument_graph as graph


def node(identifier, kind="claim"):
    return {"id": identifier, "kind": kind, "text": identifier, "source_ref": f"fixture/{identifier}"}


def edge(source, target, relation="supports"):
    return {"source": source, "target": target, "relation": relation, "source_ref": "fixture/review"}


class GraphTests(unittest.TestCase):
    def fixture(self):
        return {"nodes": [node("c"), node("b"), node("a"), node("e", "evidence"), node("d")],
                "edges": [edge("e", "b"), edge("e", "a"), edge("b", "c"),
                          edge("a", "c"), edge("c", "a", "attacks")]}

    def test_reports_cycles_and_missing_direct_evidence_independent_of_input_order(self):
        raw = self.fixture()
        report = graph.ArgumentGraph(raw).report()
        self.assertEqual(report["cycles"], [["a", "c"]])
        self.assertEqual(report["claims_without_evidence"], ["c", "d"])
        self.assertEqual(graph.ArgumentGraph({k: v[::-1] for k, v in raw.items()}).report(), report)

    def test_path_preserves_side_and_provenance_and_breaks_ties_by_id(self):
        subject = graph.ArgumentGraph(self.fixture())
        self.assertEqual(subject.shortest_path("e", "c"), [edge("e", "a"), edge("a", "c")])
        self.assertEqual(subject.shortest_path("c", "a"), [edge("c", "a", "attacks")])
        self.assertIsNone(subject.shortest_path("c", "a", relations=["supports"]))
        self.assertIsNone(subject.shortest_path("a", "e"))
        self.assertEqual(subject.shortest_path("b", "b"), [])
        self.assertEqual(subject.incoming("a"), [edge("c", "a", "attacks"), edge("e", "a")])
        self.assertEqual(subject.strongly_connected(relations=["supports"]),
                         [["a"], ["b"], ["c"], ["d"], ["e"]])

    def test_long_cycle_does_not_need_python_recursion(self):
        count = 1_100
        identifiers = [f"p{i:04d}" for i in range(count)]
        raw = {"nodes": [node(i) for i in identifiers],
               "edges": [edge(a, b) for a, b in zip(identifiers, identifiers[1:] + identifiers[:1])]}
        subject = graph.ArgumentGraph(raw)
        self.assertEqual(subject.strongly_connected(), [identifiers])
        self.assertEqual(len(subject.shortest_path(identifiers[0], identifiers[-1])), count - 1)

    def test_rejects_dangling_duplicate_or_unattributed_edges(self):
        for bad in (edge("absent", "a"), edge("a", "a"), edge("a", "e"), edge("e", "b"),
                    {**edge("e", "c"), "source_ref": ""}, edge("a", "b", "guess")):
            with self.subTest(bad=bad), self.assertRaises(graph.GraphError):
                raw = self.fixture()
                raw["edges"].append(bad)
                graph.ArgumentGraph(raw)

    def test_path_cli_reads_false_relation_as_missing_path(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "graph.json"
        path.write_text(json.dumps(self.fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(graph.main([str(path), "--path", "c", "a", "--supports-only"]), 0)
        self.assertIsNone(json.loads(output.getvalue())["path"])

    def test_exported_report_cannot_mutate_graph(self):
        subject = graph.ArgumentGraph(self.fixture())
        snapshot = subject.report()
        copy = subject.report()
        copy["nodes"][0]["source_ref"] = "replaced"
        copy["edges"].clear()
        self.assertEqual(subject.report(), snapshot)
