"""Bangun graf lintasan dari peta raster dengan arti warna eksplisit.

Setiap sel menilai coverage piksel yang ditetapkan sebagai jalan.
Graf memakai sisi empat arah dan menyimpan posisi yang dapat
ditelusuri ke peta. Rute shortest-hop mengikuti urutan koordinat
deterministik. Landmark di dinding atau terputus diberi status.
"""
import argparse
from collections import deque
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token


MAX_CELLS = 4096
MAX_ROUTES = 64
MAX_LANDMARKS = 128


def _grid(image, box, cell, level, ratio, light):
    x0, y0, x1, y1 = box
    width, height = (x1-x0+cell-1)//cell, (y1-y0+cell-1)//cell
    if width*height > MAX_CELLS:
        raise ValueError("Jumlah sel peta melampaui batas.")
    floors = {}
    for row in range(height):
        top = y0+row*cell
        bottom = min(y1, top+cell)
        for col in range(width):
            left = x0+col*cell
            right = min(x1, left+cell)
            data = image.rectangle((left, top, right, bottom))
            passable = sum(value >= level if light else value <= level for value in data)
            if passable*10_000 >= ratio*len(data):
                floors[row, col] = {"box": [left, top, right, bottom], "walkable_pixels": passable,
                                    "pixels": len(data)}
    return floors, width, height


def _neighbors(cell, floors):
    y, x = cell
    return [item for item in ((y-1, x), (y, x-1), (y, x+1), (y+1, x)) if item in floors]


def _search(graph, start):
    visited = {start: None}
    queue = deque([start])
    while queue:
        point = queue.popleft()
        for neighbor in graph[point]:
            if neighbor not in visited:
                visited[neighbor] = point
                queue.append(neighbor)
    return visited


def _landmarks(raw, width, height):
    if not isinstance(raw, list) or len(raw) > MAX_LANDMARKS:
        raise ValueError("Jumlah landmark di luar batas.")
    result, ids, refs = [], set(), set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "row", "column", "ref"}:
            raise ValueError("Bentuk landmark tidak sah.")
        key = _token(row["id"], "ID landmark")
        pointer = _token(row["ref"], "Rujukan landmark")
        if key in ids or pointer in refs:
            raise ValueError("Landmark atau rujukan ganda.")
        point = (_integer(row["row"], 0, height-1, "Baris landmark"),
                 _integer(row["column"], 0, width-1, "Kolom landmark"))
        ids.add(key)
        refs.add(pointer)
        result.append((key, pointer, point))
    return sorted(result)


def _routes(requests, markers, graph):
    if not isinstance(requests, list) or len(requests) > MAX_ROUTES:
        raise ValueError("Jumlah rute di luar batas.")
    registry = {key: cell for key, _, cell in markers}
    results = []
    searches = {}
    seen = set()
    for pair in requests:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Rute memerlukan dua ID landmark.")
        one, two = (_token(item, "ID ujung rute") for item in pair)
        if (one, two) in seen or one not in registry or two not in registry:
            raise ValueError("Rute ganda atau landmark belum dikenal.")
        seen.add((one, two))
        start, end = registry[one], registry[two]
        path = []
        if start not in graph or end not in graph:
            status = "blocked_endpoint"
        else:
            if start not in searches:
                searches[start] = _search(graph, start)
            parent = searches[start]
            if end not in parent:
                status = "unreachable"
            else:
                status = "connected"
                here = end
                while here is not None:
                    path.append(list(here))
                    here = parent[here]
                path.reverse()
        results.append({"start": one, "end": two, "status": status, "path": path,
                        "steps": len(path)-1 if path else None})
    return results


def read_map(image_data, layout):
    image = _raster.decode(image_data)
    fields = ("box", "cell_px", "walkable_gray", "minimum_coverage_bp", "light_is_walkable", "landmarks", "routes")
    spec = _vision.spec(layout, "ace.perception-map-layout.v1", fields)
    box = _vision.bounded_box(spec["box"], image)
    cell = _integer(spec["cell_px"], 1, 512, "Sisi sel peta")
    level = _integer(spec["walkable_gray"], 0, image.maximum, "Ambang peta")
    ratio = _integer(spec["minimum_coverage_bp"], 1, 10_000, "Coverage jalan minimum")
    mode = spec["light_is_walkable"]
    if type(mode) is not bool:
        raise ValueError("Sisi walkable perlu boolean.")
    floors, width, height = _grid(image, box, cell, level, ratio, mode)
    graph = {key: _neighbors(key, floors) for key in floors}
    markers = _landmarks(spec["landmarks"], width, height)
    routes = _routes(spec["routes"], markers, graph)
    return {"schema": "ace.perception-map-graph.v1", "image_sha256": sha256(image_data).hexdigest(),
            "layout_sha256": sha256(layout).hexdigest(), "box": box, "grid_size": [width, height],
            "edge_count": sum(map(len, graph.values()))//2, "cell_px": cell,
            "nodes": [{"cell": list(key), **floors[key], "neighbors": [list(item) for item in graph[key]]} for key in floors],
            "landmarks": [{"id": key, "ref": ref, "cell": list(point), "walkable": point in floors}
                          for key, ref, point in markers], "routes": routes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_map(_raster.read(args.image), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(item["status"] != "connected" for item in report["routes"]))


if __name__ == "__main__":
    raise SystemExit(main())
