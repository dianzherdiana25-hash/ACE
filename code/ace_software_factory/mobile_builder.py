"""Hasilkan aplikasi web mobile yang dapat ditambahkan ke layar utama.

State disimpan di penyimpanan browser dengan quota eksplisit. Kontrak
membentuk tab, jenis data, dan tampilan sentuh. Paket ini menghasilkan
HTML, JS, CSS dan web manifest yang dapat disajikan dari origin lokal.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


COLOR = re.compile(r"#[0-9a-fA-F]{6}")
PRESENTATION = """
:root{color-scheme:light;font:100% system-ui,sans-serif;color:#17212c;background:#f0f4f8}
*{box-sizing:border-box}body{margin:0}.frame{max-width:32rem;margin:auto;min-height:100vh;background:white}
header,main{padding:1rem 1.2rem}header{background:var(--brand);color:white}h1,header p{margin:.25rem 0}
nav{display:flex;overflow:auto;gap:.5rem;padding:.6rem 1.2rem;border-bottom:1px solid #ced8e3}
button,input{font:inherit;min-height:2.75rem}button{cursor:pointer;padding:.55rem .8rem;border-radius:.4rem;border:1px solid #a6b4c4}
nav button[aria-current='page']{background:#17364d;color:white}label{display:block;margin-top:.6rem;font-weight:600}
input{width:100%;padding:.5rem;border:1px solid #a6b4c4;border-radius:.4rem;margin:.35rem 0}
form button{background:#17364d;color:white}ul{padding:0;list-style:none}
li{display:flex;justify-content:space-between;align-items:center;gap:.75rem;border-bottom:1px solid #ced8e3;padding:.55rem 0}
.state{min-height:1.5em;color:#364f66}button:focus-visible,input:focus-visible{outline:3px solid #be6212;outline-offset:2px}
""".strip()
RUNTIME = r'''"use strict";

function load(storage, view) {
    const raw = storage.getItem(APP.id + "/" + view);
    if (raw === null) return [];
    const records = JSON.parse(raw);
    if (!Array.isArray(records) || records.length > APP.maxRecords) throw new Error("storage_invalid");
    const seen = new Set();
    for (const row of records) {
        if (row === null || typeof row !== "object" || !Number.isSafeInteger(row.key) ||
            row.key <= 0 || seen.has(row.key) || typeof row.title !== "string" ||
            !row.title.trim() || row.title.length > 160) throw new Error("storage_invalid");
        seen.add(row.key);
    }
    return records;
}

function mutate(storage, view, action, input) {
    if (!Object.hasOwn(APP.tabs, view)) throw new Error("unknown_view");
    const records = load(storage, view);
    let next;
    if (action === "add") {
        if (typeof input !== "string" || !input.trim() || input.length > 160) throw new Error("invalid_input");
        if (records.length >= APP.maxRecords) throw new Error("storage_limit");
        const key = Math.max(0, ...records.map(row => row.key)) + 1;
        if (!Number.isSafeInteger(key)) throw new Error("storage_limit");
        next = [...records, { key, title: input.trim() }];
    } else if (action === "remove") {
        if (!Number.isSafeInteger(input) || !records.some(row => row.key === input)) throw new Error("item_missing");
        next = records.filter(row => row.key !== input);
    } else {
        throw new Error("unknown_action");
    }
    storage.setItem(APP.id + "/" + view, JSON.stringify(next));
    return next;
}

function mount(doc, storage) {
    const buttons = [...doc.querySelectorAll("[data-tab]")];
    const list = doc.querySelector("#records");
    const status = doc.querySelector("#status");
    const form = doc.querySelector("#capture");
    let selected = buttons[0].dataset.tab;

    function show() {
        const view = APP.tabs[selected];
        doc.querySelector("#section-title").textContent = view.title;
        const fieldLabel = doc.querySelector("#capture-label");
        fieldLabel.textContent = view.input;
        for (const button of buttons) {
            if (button.dataset.tab === selected) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        }
        list.replaceChildren();
        for (const row of load(storage, selected)) {
            const li = doc.createElement("li");
            const title = doc.createElement("span");
            title.textContent = row.title;
            const done = doc.createElement("button");
            done.type = "button";
            done.textContent = "Hapus";
            done.setAttribute("aria-label", "Hapus " + row.title);
            done.addEventListener("click", () => apply("remove", row.key));
            li.append(title, done);
            list.append(li);
        }
    }

    function apply(kind, input) {
        try {
            mutate(storage, selected, kind, input);
            status.textContent = "Tersimpan di perangkat ini.";
            show();
            return true;
        } catch (_error) {
            status.textContent = "Perubahan gagal disimpan.";
            return false;
        }
    }

    for (const button of buttons) button.addEventListener("click", () => {
        selected = button.dataset.tab;
        status.textContent = "";
        try { show(); }
        catch (_error) { list.replaceChildren(); status.textContent = "Data perangkat gagal dibaca."; }
    });
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (apply("add", doc.querySelector("#record-title").value)) form.reset();
    });
    try { show(); }
    catch (_error) { status.textContent = "Data perangkat gagal dibaca."; }
}

if (typeof module !== "undefined") module.exports = { load, mutate };
if (typeof document !== "undefined") mount(document, window.localStorage);
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-mobile-plan.v1", ("id", "name", "summary", "theme", "source_ref", "max_records", "tabs"))
    product = identifier(plan["id"], "ID aplikasi mobile")
    title = text(plan["name"], "Nama aplikasi", 80)
    summary = text(plan["summary"], "Ringkasan", 180)
    source = text(plan["source_ref"], "Sumber desain")
    theme = plan["theme"]
    if not isinstance(theme, str) or not COLOR.fullmatch(theme):
        raise ContractError("Warna tema perlu format #RRGGBB.")
    base = { "id": product, "maxRecords": integer(plan["max_records"], "Batas data per tab", 1, 500), "tabs": {}}
    labels = []
    refs = []
    for row in entries(plan["tabs"], 8, minimum=1):
        obj(row, ("id", "title", "input", "source_ref"))
        key = identifier(row["id"], "ID tab")
        name = text(row["title"], "Judul tab", 60)
        if key in base["tabs"]:
            raise ContractError("ID tab ganda.")
        base["tabs"][key] = {"title": name, "input": text(row["input"], "Label masukan", 70)}
        refs.append({"id": key, "source_ref": text(row["source_ref"], "Sumber tab")})
        labels.append(f'<button type="button" data-tab="{key}">{escape(name)}</button>')
    page = f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="{theme}"><title>{escape(title)}</title>
<link rel="manifest" href="manifest.webmanifest"><link rel="stylesheet" href="mobile.css">
<script defer src="mobile.js"></script></head>
<body><div class="frame"><header><h1>{escape(title)}</h1><p>{escape(summary)}</p></header>
<nav aria-label="Bagian aplikasi">{''.join(labels)}</nav>
<main><h2 id="section-title"></h2><form id="capture"><label id="capture-label" for="record-title"></label>
<input id="record-title" name="title" maxlength="160" required><button type="submit">Tambah</button></form>
<p class="state" id="status" role="status"></p><ul id="records"></ul></main></div></body></html>
"""
    manifest = {"id": "./", "name": title, "short_name": title[:32], "display": "standalone", "start_url": "./",
                "scope": "./", "theme_color": theme, "background_color": "#f0f4f8", "lang": "id"}
    files = {"index.html": page.encode(), "manifest.webmanifest": canonical(manifest)+b"\n",
             "mobile.css": f":root{{--brand:{theme}}}\n{PRESENTATION}\n".encode(),
             "mobile.js": b"const APP = "+canonical(base)+b";\n"+RUNTIME.encode()}
    report = {"schema": "ace.factory-mobile-build.v1", "plan_sha256": expected, "product_id": product,
              "source_ref": source, "tabs": refs, "runtime": "mobile_web",
              "files": [{"path": key, "sha256": sha256(value).hexdigest()} for key, value in sorted(files.items())]}
    return {**files, "mobile_build.json": canonical(report)+b"\n"}, report


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
