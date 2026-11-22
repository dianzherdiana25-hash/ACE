"""Bangun ekstensi browser Manifest V3 dengan penyimpanan checklist lokal.

Scope ekstensi berupa popup. Template tidak membutuhkan izin host atau
content script. Mutasi menjaga kuota dan memakai lock per storage key
untuk menghindari hilangnya pembaruan dari popup lain.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


VERSION = re.compile(r"(?:0|[1-9][0-9]{0,4})(?:\.(?:0|[1-9][0-9]{0,4})){1,3}")
RUNTIME = r'''"use strict";

function openPreferences(storage) {
    async function read() {
        const dictionary = await storage.get(SETTINGS.key);
        const saved = dictionary[SETTINGS.key] ?? {};
        if (saved === null || Array.isArray(saved) || typeof saved !== "object") throw new Error("data_invalid");
        const unknown = Object.keys(saved).filter(key => !Object.hasOwn(SETTINGS.items, key));
        if (unknown.length) throw new Error("data_needs_migration");
        const model = Object.create(null);
        for (const [key, fallback] of Object.entries(SETTINGS.items)) {
            if (Object.hasOwn(saved,key) && typeof saved[key] !== "boolean") throw new Error("data_invalid");
            model[key] = Object.hasOwn(saved,key) ? saved[key] : fallback;
        }
        return model;
    }

    async function update(id, state, exclusive) {
        if (!Object.hasOwn(SETTINGS.items, id) || typeof state !== "boolean") throw new Error("change_invalid");
        return exclusive(SETTINGS.key, async () => {
            const previous = await read();
            const next = {...previous, [id]: state};
            await storage.set({ [SETTINGS.key]: next });
            return next;
        });
    }
    return { read, update };
}

function mount(doc, storage, locks) {
    const app = openPreferences(storage);
    const fields = [...doc.querySelectorAll("input[type=checkbox]")];
    const report = doc.querySelector("p[role=status]");

    function assign(record) {
        for (const field of fields) field.checked = record[field.name];
    }

    async function init() {
        try {
            assign(await app.read());
            if (!locks) throw new Error("lock_unavailable");
            for (const field of fields) {
                field.disabled = false;
                field.addEventListener("change", async () => {
                    field.disabled = true;
                    try {
                        const result = await app.update(field.name,field.checked,(key, fn) => locks.request(key,fn));
                        assign(result);
                        report.textContent = "Checklist disimpan.";
                    } catch (_error) {
                        report.textContent = "Gagal menyimpan checklist.";
                        try { assign(await app.read()); } catch (_) {}
                    } finally {
                        field.disabled = false;
                    }
                });
            }
        } catch (_error) {
            report.textContent = "Checklist gagal dibuka.";
        }
    }
    init();
}

if (typeof module !== "undefined") module.exports = { openPreferences };
if (typeof document !== "undefined") mount(document, chrome.storage.local, navigator.locks);
'''


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-extension-plan.v1", ("id", "name", "summary", "version", "source_ref", "checklist"))
    product = identifier(plan["id"], "ID ekstensi")
    title = text(plan["name"], "Judul ekstensi", 70)
    summary = text(plan["summary"], "Deskripsi ekstensi", 130)
    source = text(plan["source_ref"], "Sumber spesifikasi")
    version = plan["version"]
    if not isinstance(version, str) or not VERSION.fullmatch(version) or any(int(part) > 65535 for part in version.split(".")) or (
            all(int(part) == 0 for part in version.split("."))):
        raise ContractError("Versi manifest ekstensi tidak sah.")
    items, labels, sources = {}, [], []
    for row in entries(plan["checklist"], 40, minimum=1):
        obj(row, ("id", "label", "default", "source_ref"))
        key = identifier(row["id"], "ID item")
        if key in items or type(row["default"]) is not bool:
            raise ContractError("Item ganda atau status default tidak sah.")
        items[key] = row["default"]
        label = text(row["label"], "Label checklist", 140)
        labels.append(f'<label><input type="checkbox" name="{key}" disabled> {escape(label)}</label>')
        sources.append({"id": key, "source_ref": text(row["source_ref"], "Rujukan item", 250)})
    manifest = {"manifest_version": 3, "name": title, "version": version, "description": summary,
                "permissions": ["storage"], "action": {"default_popup": "popup.html", "default_title": title}}
    html = f'''<!doctype html>
<html lang="id"><head><meta charset="utf-8"><title>{escape(title)}</title>
<link rel="stylesheet" href="popup.css"><script src="popup.js" defer></script></head>
<body><main><h1>{escape(title)}</h1><p>{escape(summary)}</p>
<fieldset><legend>Checklist</legend>{''.join(labels)}</fieldset><p role="status"></p>
</main></body></html>
'''
    css = ("body{font:14px system-ui;color:#17212b;background:#f5f8fc;min-width:280px;margin:0}"
           "main{padding:16px}h1{font-size:1.25rem;margin:0 0 .55rem}"
           "fieldset{border:1px solid #bacbdd;border-radius:.45rem}label{display:block;padding:.45rem}"
           "input:focus-visible{outline:2px solid #1b5184;outline-offset:3px}\n")
    config = {"key": f"ace/{product}/checklist.v1", "items": items}
    files = {"manifest.json": canonical(manifest) + b"\n", "popup.html": html.encode(), "popup.css": css.encode(),
             "popup.js": b"const SETTINGS = " + canonical(config) + b";\n" + RUNTIME.encode()}
    report = {"schema": "ace.factory-extension-build.v1", "product_id": product, "plan_sha256": expected,
              "source_ref": source, "checklist": sources,
              "files": [{"path": key, "sha256": sha256(value).hexdigest()} for key, value in sorted(files.items())]}
    return {**files, "extension_build.json": canonical(report)+b"\n"}, report


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
