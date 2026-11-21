"""Bangun puzzle grid orisinal dan buktikan levelnya dapat diselesaikan.

Solver BFS memperhitungkan posisi, token, rintangan dan batas gerakan.
Game browser hasil build menerapkan aturan yang sama, memakai data dari
rancangan lokal. Verifier dapat memutar kembali saksi langkah solver.
"""
import argparse
from collections import deque
from hashlib import sha256
from html import escape
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, read, schema, text
from .repo_scaffolder import materialize


DIRECTIONS = (("up", -1, 0), ("left", 0, -1), ("down", 1, 0), ("right", 0, 1))
TILES = frozenset(".#STG")
MAX_TOKENS = 9
CSS = """
:root{color:#132735;background:#f0f6f5;font:100% system-ui,sans-serif}
main{max-width:33rem;padding:1rem;margin:auto}h1{font-size:clamp(1.85rem,10vw,3.3rem);letter-spacing:-.04em}
.board{display:grid;grid-template-columns:repeat(var(--width),1fr);gap:3px;max-width:26rem;margin:1rem 0}
.cell{background:#d4eae6;aspect-ratio:1;border-radius:.3rem;display:grid;place-items:center;font-weight:750}
.cell.wall{background:#183949}.cell.player{background:#006c5c;color:white}.cell.goal{outline:2px solid #2967a3;outline-offset:-2px}
.controls{display:flex;gap:.45rem;flex-wrap:wrap}button{min-height:42px;padding:.55rem .75rem;font:inherit;border:1px solid #769691;border-radius:.45rem}
button:focus-visible{outline:3px solid #b14f14;outline-offset:3px}
""".strip()
JS = r'''"use strict";

const directions = { up: [-1,0], left: [0,-1], down: [1,0], right: [0,1] };

function initial() {
    return { row: LEVEL.start[0], col: LEVEL.start[1], remaining: LEVEL.moves,
             collected: [], state: "playing" };
}

function move(state, direction) {
    if (!Object.hasOwn(directions,direction)) throw new Error("invalid_direction");
    if (state.state !== "playing") return state;
    const [dr,dc] = directions[direction];
    const row = state.row + dr, col = state.col + dc;
    if (row < 0 || row >= LEVEL.rows.length || col < 0 || col >= LEVEL.rows[0].length) return state;
    const tile = LEVEL.rows[row][col];
    if (tile === "#") return state;
    const position = row * LEVEL.rows[0].length + col;
    const tokens = tile === "T" && !state.collected.includes(position)
        ? [...state.collected, position] : state.collected;
    const remaining = state.remaining - 1;
    const finished = tile === "G" && tokens.length === LEVEL.tokens;
    return { row, col, remaining, collected: tokens,
             state: finished ? "won" : remaining === 0 ? "lost" : "playing" };
}

function mount(doc) {
    let state = initial();
    const display = doc.querySelector("#board");
    const note = doc.querySelector("#progress");
    const cells = [];

    for (const [y, row] of LEVEL.rows.entries()) {
        const line = [];
        for (const [x, tile] of [...row].entries()) {
            const box = doc.createElement("span");
            box.className = "cell";
            display.append(box);
            line.push(box);
        }
        cells.push(line);
    }

    function paint() {
        for (const [y, row] of LEVEL.rows.entries()) {
            for (const [x, tile] of [...row].entries()) {
                const box = cells[y][x];
                const current = y === state.row && x === state.col;
                const hasToken = tile === "T" && !state.collected.includes(y*row.length+x);
                box.classList.toggle("player", current);
                box.classList.toggle("goal", tile === "G");
                box.classList.toggle("wall", tile === "#");
                box.textContent = current ? "●" : tile === "G" ? "G" : hasToken ? "◆" : "";
            }
        }
        const position = `Baris ${state.row+1}, kolom ${state.col+1}.`;
        const progress = `Token ${state.collected.length} dari ${LEVEL.tokens}. Sisa ${state.remaining} langkah.`;
        const label = state.state === "won" ? "Tujuan tercapai. " : state.state === "lost" ? "Langkah habis. " : "";
        note.textContent = label + position + " " + progress;
    }

    function step(direction) {
        state = direction === "restart" ? initial() : move(state,direction);
        paint();
    }

    for (const button of doc.querySelectorAll("button[data-direction]")) {
        button.addEventListener("click", () => step(button.dataset.direction));
    }
    doc.addEventListener("keydown", (event) => {
        const key = { ArrowUp:"up", ArrowLeft:"left", ArrowDown:"down", ArrowRight:"right" }[event.key];
        if (key && !event.altKey && !event.ctrlKey && !event.metaKey) {
            event.preventDefault();
            step(key);
        }
    });
    paint();
}

if (typeof module !== "undefined") module.exports = { initial, move };
if (typeof document !== "undefined") mount(document);
'''


def _level(rows):
    raw = entries(rows, 12, minimum=2)
    cells = [text(value, "Peta grid", 12) for value in raw]
    width = len(cells[0])
    if width < 2 or any(len(row) != width or set(row) - TILES for row in cells):
        raise ContractError("Grid tidak persegi panjang atau tile tidak dikenal.")
    marks = {key: [(y, x) for y, row in enumerate(cells)
                   for x, marker in enumerate(row) if marker == key] for key in ("S", "G", "T")}
    if len(marks["S"]) != 1 or len(marks["G"]) != 1 or len(marks["T"]) > MAX_TOKENS:
        raise ContractError("Grid perlu titik mulai, tujuan dan token dalam batas.")
    tokens = {point: 1<<index for index, point in enumerate(marks["T"])}
    return cells, marks["S"][0], marks["G"][0], tokens


def solve(rows, start, target, tokens, limit):
    origin = (*start, 0)
    queue = deque([(origin, 0)])
    visited = {origin: None}
    complete = (1 << len(tokens)) - 1
    while queue:
        state, length = queue.popleft()
        y, x, collected = state
        if (y, x) == target and collected == complete:
            route = []
            while visited[state] is not None:
                state, edge = visited[state]
                route.append(edge)
            return list(reversed(route))
        if length == limit:
            continue
        for name, dr, dc in DIRECTIONS:
            point = y+dr, x+dc
            dy, dx = point
            if not (0 <= dy < len(rows) and 0 <= dx < len(rows[0])) or rows[dy][dx] == "#":
                continue
            candidate = (*point, collected | tokens.get(point, 0))
            if candidate not in visited:
                visited[candidate] = state, name
                queue.append((candidate, length+1))
    return None


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-grid-game.v1", ("id", "title", "goal", "source_ref", "map", "max_moves"))
    product = identifier(plan["id"], "ID game")
    title = text(plan["title"], "Judul game", 100)
    goal = text(plan["goal"], "Tujuan game", 300)
    source = text(plan["source_ref"], "Sumber desain")
    rows, start, target, tokens = _level(plan["map"])
    limit = integer(plan["max_moves"], "Batas gerakan", 1, 150)
    solution = solve(rows, start, target, tokens, limit)
    if solution is None:
        raise ContractError("Level tidak memiliki solusi di dalam batas langkah.")
    config = {"rows": rows, "start": start, "moves": limit, "tokens": len(tokens)}
    controls = "".join(f'<button type="button" data-direction="{key}">{label}</button>'
                       for key,label in (("up","Atas"),("left","Kiri"),("down","Bawah"),("right","Kanan"),("restart","Ulangi")))
    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<link rel="stylesheet" href="game.css"><script src="game.js" defer></script></head>
<body><main><h1>{escape(title)}</h1><p>{escape(goal)}</p>
<div class="board" id="board" aria-hidden="true"></div><p id="progress" role="status"></p>
<div class="controls">{controls}</div></main></body></html>
"""
    files = {"index.html": html.encode(), "game.css": f":root{{--width:{len(rows[0])}}}\n{CSS}\n".encode(),
             "game.js": b"const LEVEL = "+canonical(config)+b";\n"+JS.encode()}
    report = {"schema": "ace.factory-grid-game-build.v1", "product_id": product, "plan_sha256": expected,
              "source_ref": source, "tokens": len(tokens), "budget_moves": limit, "shortest_moves": len(solution),
              "solution": solution, "files": [{"path": key, "sha256": sha256(value).hexdigest()}
                                             for key, value in sorted(files.items())]}
    return {**files, "game_build.json": canonical(report)+b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
