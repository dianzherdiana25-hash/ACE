"""Verifier BFS dan replay pada JavaScript yang benar-benar dihasilkan."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import game_builder
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


SCRIPT = '''
const assert = require("node:assert/strict");
const {initial,move} = require("./game.js");
const sheet = require("./game_build.json");
const start = initial();
assert.deepEqual(move(start,"down"),start);
assert.equal(move(move(start,"right"),"right").state,"playing");
let state = start;
for (const item of sheet.solution) state = move(state,item);
assert.equal(state.state,"won");
assert.equal(state.collected.length,1);
assert.equal(state.remaining,0);
'''


class GameTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"schema": "ace.factory-grid-game.v1", "id": "path_of_lantern", "title": "Satu lentera",
                     "goal": "Ambil token sebelum menuju G.", "source_ref": "fixture/design/grid",
                     "map": ["S.G", "#T#", "..."], "max_moves": 4}

    def build(self):
        return game_builder.build(self.plan, identity(self.plan))

    def test_game_build_contains_shortest_witness(self):
        files, report = self.build()
        self.assertEqual(report["shortest_moves"], 4)
        self.assertEqual(report["solution"], ["right", "down", "up", "right"])
        self.assertIn(b'data-direction="restart"', files["index.html"])

    def test_rejects_unsolvable_or_too_short_level(self):
        self.plan["max_moves"] = 3
        with self.assertRaisesRegex(ContractError, "solusi"):
            self.build()
        self.plan["map"] = ["S#", "#G"]
        self.plan["max_moves"] = 5
        with self.assertRaisesRegex(ContractError, "solusi"):
            self.build()

    def test_real_javascript_runtime_agrees_with_python_solver(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node lokal tidak tersedia")
        target = Path(self.enterContext(TemporaryDirectory())) / "game"
        files, _ = self.build()
        materialize(target, {**files, "fixture.cjs": SCRIPT.encode()})
        result = subprocess.run([node, "fixture.cjs"], cwd=target, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
