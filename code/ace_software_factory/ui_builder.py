"""Bangun antarmuka web statis dari hierarki layar yang dideklarasikan.

Label, navigasi, tabel, dan form dibentuk dari kontrak. Nilai user
di-escape sebelum dirender. Aksi form JSON hanya menuju endpoint
relatif yang terdaftar. Halaman hasil dapat dibaca tanpa layanan
dan menyimpan feedback saat endpoint dipakai.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, integer, obj, read, schema, text
from .repo_scaffolder import materialize


RESOURCE = re.compile(r"/[a-z][a-z0-9_]{0,63}")
LANG = re.compile(r"[a-z]{2,3}(?:-[A-Z]{2})?")
INPUTS = {"text", "number", "email", "checkbox"}
STYLE = '''*{box-sizing:border-box}body{margin:0;background:#f5f6fa;color:#182035;font:16px/1.55 system-ui,sans-serif}
main{width:min(940px,100% - 32px);margin:0 auto;padding:20px 0 48px}
header,section{margin:0 0 20px}header{padding:20px 0;border-bottom:1px solid #c9d2e4}
h1,h2,p{margin:0 0 .65rem}h1,h2{line-height:1.18}a{color:#154fa8}nav{display:flex;gap:16px;flex-wrap:wrap}
section{padding:20px;border:1px solid #d4dbe7;border-radius:12px;background:white}
form{display:grid;gap:10px;max-width:560px}label{font-weight:600}
input:not([type=checkbox]){width:100%;border:1px solid #9ba9bd;border-radius:6px;padding:9px;background:#fff;font:inherit}
button{justify-self:start;padding:9px 16px;border:0;border-radius:6px;background:#174b9a;color:#fff;font:inherit}
:focus-visible{outline:3px solid #bf6a0a;outline-offset:3px}table{border-collapse:collapse;width:100%}
td,th{text-align:start;padding:8px;border-bottom:1px solid #e0e5ee}.table-wrap{overflow:auto}
.status[hidden]{display:none}@media(max-width:520px){main{width:min(100% - 20px,940px)}section{padding:14px}}'''
JS = r'''document.querySelectorAll("form[data-endpoint]").forEach(function (form) {
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const status = form.querySelector("[role=status]");
        const button = form.querySelector("button[type=submit]");
        const data = {};
        for (const input of form.querySelectorAll("input")) {
            if (input.type === "checkbox") {
                data[input.name] = input.checked;
            } else if (input.value !== "") {
                data[input.name] = input.type === "number" ? input.valueAsNumber : input.value;
            }
        }
        button.disabled = true;
        status.hidden = false;
        status.textContent = form.dataset.wait;
        try {
            const response = await fetch(form.dataset.endpoint, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(data),
                credentials: "same-origin",
                redirect: "error"
            });
            status.textContent = response.ok ? form.dataset.success : form.dataset.error;
        } catch (_error) {
            status.textContent = form.dataset.error;
        } finally {
            button.disabled = false;
        }
    });
});
'''


def _escape(raw, name, cap=500):
    return escape(text(raw, name, cap), quote=True)


def _paragraph(data, _resources):
    obj(data, ("text",))
    return "<p>"+_escape(data["text"], "Isi paragraf", 4000)+"</p>"


def _table(data, _resources):
    obj(data, ("columns", "rows", "caption"))
    columns = entries(data["columns"], 20, minimum=1)
    head = []
    known = set()
    for column in columns:
        obj(column, ("id", "label"))
        key = identifier(column["id"], "Kolom")
        if key in known:
            raise ContractError("Kolom tabel ganda.")
        known.add(key)
        head.append("<th scope=\"col\">"+_escape(column["label"], "Label kolom", 100)+"</th>")
    body = []
    for row in entries(data["rows"], 1000):
        obj(row, known)
        cells = []
        for column in columns:
            value = row[column["id"]]
            if type(value) not in (int, str, bool) or isinstance(value, str) and len(value) > 1000:
                raise ContractError("Nilai tabel tidak sah.")
            cells.append("<td>"+escape(str(value), quote=True)+"</td>")
        body.append("<tr>"+"".join(cells)+"</tr>")
    caption = _escape(data["caption"], "Caption tabel", 140)
    return ("<div class=\"table-wrap\"><table><caption>"+caption+"</caption><thead><tr>"+"".join(head)+
            "</tr></thead><tbody>"+"".join(body)+"</tbody></table></div>")


def _form(data, resources):
    obj(data, ("id", "endpoint", "fields", "submit", "wait", "success", "error"))
    key = identifier(data["id"], "ID form")
    endpoint = data["endpoint"]
    if endpoint not in resources:
        raise ContractError("Endpoint form belum terdaftar.")
    widgets = []
    seen = set()
    for row in entries(data["fields"], 30, minimum=1):
        obj(row, ("name", "label", "input_type", "required", "max_length"))
        name = identifier(row["name"], "ID bidang form")
        kind = row["input_type"]
        required = row["required"]
        if name in seen or not isinstance(kind, str) or kind not in INPUTS or type(required) is not bool:
            raise ContractError("Bidang form ganda atau tidak sah.")
        seen.add(name)
        value = f"{key}-{name}"
        label = _escape(row["label"], "Label bidang form", 120)
        length = row["max_length"]
        if length is not None and kind not in {"text","email"}:
            raise ContractError("Batas karakter hanya untuk masukan teks.")
        limit = f' maxlength="{integer(length,"Panjang bidang",1,16384)}"' if length is not None else ""
        state = " required" if required else ""
        widgets.append(f'<label for="{value}">{label}</label><input id="{value}" name="{name}" type="{kind}"{limit}{state}>')
    submit = _escape(data["submit"], "Label kirim", 80)
    strings = {name:_escape(data[name], "Feedback form", 180) for name in ("wait","success","error")}
    return (f'<form data-endpoint="{endpoint}" data-wait="{strings["wait"]}" data-success="{strings["success"]}" '
            f'data-error="{strings["error"]}">'+"".join(widgets)+
            f'<button type="submit">{submit}</button><p role="status" class="status" hidden></p></form>')


BLOCKS = {"text": _paragraph, "table": _table, "form": _form}


def build(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-ui-plan.v1", ("screen_ref", "locale", "title", "sections", "api_endpoints", "navigation"))
    title = _escape(plan["title"], "Judul halaman", 180)
    locale = plan["locale"]
    if not isinstance(locale,str) or not LANG.fullmatch(locale):
        raise ContractError("Locale halaman tidak sah.")
    resources = entries(plan["api_endpoints"], 32)
    if any(not isinstance(value,str) or not RESOURCE.fullmatch(value) for value in resources) or len(set(resources)) != len(resources):
        raise ContractError("Endpoint halaman ganda atau tidak relatif.")
    blocks = []
    seen, ids = set(), set()
    used_form = False
    for section in entries(plan["sections"], 36, minimum=1):
        obj(section, ("id", "heading", "source_ref", "blocks"))
        key = identifier(section["id"], "ID bagian")
        if key in seen:
            raise ContractError("Bagian halaman ganda.")
        seen.add(key)
        label = _escape(section["heading"], "Judul bagian", 160)
        ref = text(section["source_ref"], "Rujukan bagian", 256)
        rendered = []
        for row in entries(section["blocks"], 40, minimum=1):
            obj(row, ("type", "data"))
            kind = row["type"]
            if not isinstance(kind,str) or kind not in BLOCKS:
                raise ContractError("Blok layar tidak didukung.")
            parsed = BLOCKS[kind](row["data"], resources)
            if kind == "form":
                form_id = row["data"]["id"]
                if form_id in ids:
                    raise ContractError("ID form ganda dalam halaman.")
                ids.add(form_id)
                used_form = True
            rendered.append(parsed)
        blocks.append((key, ref, f'<section id="{key}"><h2>{label}</h2>'+"".join(rendered)+"</section>"))
    navigation = []
    anchors = set()
    for raw in entries(plan["navigation"], 36):
        obj(raw, ("target", "label"))
        target = identifier(raw["target"], "Target navigasi")
        if target not in seen or target in anchors:
            raise ContractError("Target navigasi ganda atau tidak dikenal.")
        anchors.add(target)
        navigation.append(f'<a href="#{target}">'+_escape(raw["label"], "Label navigasi", 100)+"</a>")
    menu = '<nav aria-label="Navigasi halaman">'+"".join(navigation)+"</nav>" if navigation else ""
    artifact = ("<!doctype html>\n"
                f'<html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" '
                f'content="width=device-width,initial-scale=1"><title>{title}</title><style>{STYLE}</style></head>'
                f'<body><main><header><h1>{title}</h1>{menu}</header>'
                + "".join(row[2] for row in blocks)
                + ("<script>"+JS+"</script>" if used_form else "")+"</main></body></html>\n").encode()
    receipt = {"schema":"ace.factory-ui.v1", "screen_ref":text(plan["screen_ref"],"Rujukan layar",200),
               "plan_sha256":expected,"html_sha256":sha256(artifact).hexdigest(),"locale":locale,
               "sections":[{"id":key,"source_ref":ref} for key,ref,_ in blocks],"forms":len(ids)}
    return {"index.html":artifact},receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--expect-sha256",required=True)
    args=parser.parse_args(argv)
    try:
        files,report=build(decode(read(args.plan)),args.expect_sha256)
        materialize(args.output,files)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
