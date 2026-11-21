"""Verifier graf peta, rute deterministik dan endpoint yang dihalangi."""
import unittest

from ace_perception import _vision, map_reader as model


def plan(**changes):
    markers = [("departure", 0, 0), ("destination", 2, 2), ("island", 0, 4), ("wall", 1, 1)]
    raw = {"schema": "ace.perception-map-layout.v1", "box": [0, 0, 5, 3], "cell_px": 1,
           "walkable_gray": 128, "minimum_coverage_bp": 10000, "light_is_walkable": True,
           "landmarks": [{"id": label, "row": row, "column": col, "ref": "fixture/"+label}
                         for label, row, col in markers],
           "routes": [["departure", "destination"], ["departure", "island"], ["departure", "wall"]]}
    return model._canonical({**raw, **changes})


def fixture():
    return _vision.encode(5, 3, [255 if item == "." else 0 for item in "...#. .#.## ...#.".replace(" ", "")])


class MapTests(unittest.TestCase):
    def test_builds_four_connected_graph_and_deterministic_shortest_tie(self):
        result = model.read_map(fixture(), plan())
        self.assertEqual(result["grid_size"], [5, 3])
        self.assertEqual(result["edge_count"], 8)
        self.assertEqual([(row["status"], row["steps"]) for row in result["routes"]],
                         [("connected", 4), ("unreachable", None), ("blocked_endpoint", None)])
        self.assertEqual(result["routes"][0]["path"], [[0, 0], [0, 1], [0, 2], [1, 2], [2, 2]])
        node = next(row for row in result["nodes"] if row["cell"] == [0, 0])
        self.assertEqual(node["neighbors"], [[0, 1], [1, 0]])
        self.assertEqual(node["box"], [0, 0, 1, 1])

    def test_partial_tile_keeps_real_pixel_area_and_position(self):
        result = model.read_map(fixture(), plan(cell_px=2, landmarks=[], routes=[], minimum_coverage_bp=5000))
        self.assertEqual(result["grid_size"], [3, 2])
        nodes = {tuple(item["cell"]): item for item in result["nodes"]}
        self.assertEqual(nodes[0, 0]["walkable_pixels"], 3)
        self.assertEqual(nodes[0, 2]["pixels"], 2)
        self.assertEqual(nodes[1, 2]["box"], [4, 2, 5, 3])

    def test_endpoint_unknown_and_out_of_bounds_layout_rejected(self):
        for changes in ({"routes": [["departure", "an-absent"]]}, {"box": [0, 0, 9, 9]}, {"light_is_walkable": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.read_map(fixture(), plan(**changes))
