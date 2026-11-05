import unittest

from e13.contract import ContractError, canonical_json, input_value

from .e14g_bank import sha
from .e14p_graph import minimum, paths
from .e14r_run import build, frozen, invoke, prior_graphs, stage
from .e14r_worker import solve


class E14RPrescore(unittest.TestCase):
    def test_frozen_bank_has_independent_targets(self):
        bank, _, _ = frozen()
        self.assertEqual(canonical_json(bank), canonical_json(build()))
        known = prior_graphs()
        for block in bank["blocks"]:
            for raw in [block["calibration"], *block["probes"]]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, known)
                known.add(digest)

    def test_worker_requires_positive_receipt(self):
        artifact = {"kind": "edge-relative-word-v1", "word": [1, 2, 2, 1, 2, 2, 1, 1, 2],
                    "source_sha256": "0" * 64}
        with self.assertRaises(ContractError):
            solve({"artifact": artifact, "mode": "packed", "observed": False, "label": None, "truth": []})
        with stage() as root:
            before, _ = invoke(root, artifact, "packed")
            null, _ = invoke(root, artifact, "packed", observed=True)
            hit, _ = invoke(root, artifact, "packed", observed=True, label=10)
        graph = before["graph"]
        input_value("G", graph)
        self.assertLessEqual(graph["nodes"], 16)
        self.assertLessEqual(len(graph["edges"]), 16)
        self.assertEqual(len(paths(graph)), 3)
        self.assertEqual(minimum(paths(graph), tuple(artifact["word"])), 10)
        self.assertEqual((before["selected"], null["selected"], hit["selected"]), ([], [], [artifact["word"]]))
