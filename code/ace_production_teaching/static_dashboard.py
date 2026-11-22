"""Rakit satu HTML statis yang membawa tabel, grafik dan rujukan data lokal."""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import sys

from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         identity, items, obj, read, schema, source_bytes, text)
from .chart_builder import make_chart
from .tabular_engine import _read_csv


CSS = """*{box-sizing:border-box}body{margin:0;background:#f1f5f7;color:#112936;font:16px/1.5 system-ui}
main{max-width:1150px;margin:0 auto;padding:2rem 1.2rem}header{margin-bottom:1.5rem}h1,h2{line-height:1.1}
nav ul{padding:0;list-style:none;display:flex;gap:.9rem;flex-wrap:wrap}a{color:#075860}
section{background:white;border-radius:10px;padding:1.4rem;margin:1rem 0;overflow:auto}figure{margin:0}
figure svg{max-width:100%;height:auto}table{border-collapse:collapse;min-width:min(28rem,100%);width:100%;text-align:left}
td,th{padding:.55rem .7rem;border-bottom:1px solid #d2dce3;vertical-align:top}th{background:#e9f3f4}
caption{text-align:left;font-weight:600;padding:.6rem 0}.source{color:#496572;font-size:.88rem}
@media(max-width:550px){main{padding:1rem}section{padding:1rem}td,th{padding:.45rem .5rem}}
"""


def dashboard(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.dashboard-plan.v1", ("title", "language", "sections"))
    title = text(plan["title"], "Judul dashboard", 100)
    lang = plan["language"]
    if lang not in ("id", "en"):
        raise ProductionError("Bahasa dashboard perlu id atau en.")
    nav = []
    parts = []
    manifest = []
    seen = set()
    for row in items(plan["sections"], 25, 1):
        obj(row, ("id", "heading", "kind", "source"))
        key = identifier(row["id"], "ID bagian")
        heading = text(row["heading"], "Nama bagian", 130)
        if key in seen or row["kind"] not in ("table", "chart"):
            raise ProductionError("Bagian ganda atau bentuk tidak didukung.")
        seen.add(key)
        loc = obj(row["source"], ("path", "sha256"))
        raw = source_bytes(root, loc["path"], loc["sha256"], 350000)
        nav.append(f'<li><a href="#sec_{key}">{escape(heading)}</a></li>')
        if row["kind"] == "table":
            headers, rows = _read_csv(raw, loc["sha256"], 160)
            if len(headers) > 16:
                raise ProductionError("Tabel dashboard dibatasi enam belas kolom.")
            titles = "".join(f'<th scope="col">{escape(name)}</th>' for name in headers)
            members = "".join("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in row) + "</tr>" for row, _ in rows)
            widget = f'<table><caption>{escape(heading)}</caption><thead><tr>{titles}</tr></thead><tbody>{members}</tbody></table>'
            count = len(rows)
        else:
            spec = decode(raw)
            image, proof = make_chart(spec, identity(spec))
            svg = image.decode().replace('id="chart_', f'id="svg_{key}_chart_').replace('aria-labelledby="chart_title chart_desc"',
                                                                                        f'aria-labelledby="svg_{key}_chart_title svg_{key}_chart_desc"')
            widget = f"<figure>{svg}</figure>"
            count = len(proof["points"])
        origin = f'<p class="source"><code>{escape(loc["path"])}</code></p>'
        parts.append(f'<section id="sec_{key}" aria-labelledby="h_{key}"><h2 id="h_{key}">{escape(heading)}</h2>{widget}{origin}</section>')
        manifest.append({"id": key, "source": loc, "kind": row["kind"], "records": count})
    output = ("<!doctype html>\n" + f'<html lang="{lang}"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width, initial-scale=1">'
              f"<title>{escape(title)}</title><style>{CSS}</style></head><body><main>"
              f'<header><h1>{escape(title)}</h1><nav><ul>{"".join(nav)}</ul></nav></header>'
              + "".join(parts) + "</main></body></html>\n").encode()
    return output, {"schema": "ace.production.dashboard.v1", "plan_sha256": expected,
                    "html_sha256": sha256(output).hexdigest(), "sections": manifest, "status": "local_artifact"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = dashboard(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
