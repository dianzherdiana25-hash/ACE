"""Kompilasi katalog dwibahasa produk tanpa mengarang string yang hilang.

Kunci, placeholder, dan kategori plural diperiksa pada Inggris dan
Indonesia sebelum runtime JS dirilis. Hasil format berupa teks biasa
agar antarmuka dapat memasangnya dengan textContent.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


HOLE = re.compile(r"\{([a-z][a-z0-9_]{0,63})\}")
LANGS = {"id": {"other"}, "en": {"one", "other"}}
KINDS = {"text", "integer"}
RUNTIME = r'''"use strict";

function translate(locale, key, values) {
    const message = Object.hasOwn(MESSAGES.messages,key) ? MESSAGES.messages[key] : null;
    if (!message) throw new Error("key_unknown");
    if (!Object.hasOwn(MESSAGES.locales,locale)) locale=MESSAGES.default;
    if (values===null || typeof values!=="object" || Array.isArray(values)) throw new Error("values_invalid");
    if (Object.keys(values).length!==Object.keys(message.fields).length) throw new Error("values_mismatch");
    const numberFormat=new Intl.NumberFormat(locale);
    const provided=Object.create(null);
    for (const [field,kind] of Object.entries(message.fields)) {
        if (!Object.hasOwn(values,field)) throw new Error("field_missing");
        const value=values[field];
        if (kind==="integer") {
            if (!Number.isSafeInteger(value)) throw new Error("field_type_invalid");
            provided[field]=numberFormat.format(value);
        } else {
            if (typeof value!=="string" || value.length>300) throw new Error("field_type_invalid");
            provided[field]=value;
        }
    }
    const localized=MESSAGES.locales[locale][key];
    const plural=message.plural === null ? "other" : new Intl.PluralRules(locale).select(values[message.plural]);
    const code=localized[plural] ?? localized.other;
    return code.map(([literal, field]) => literal + (field===null ? "" : provided[field])).join("");
}
if (typeof module!=="undefined") module.exports={translate};
if (typeof window!=="undefined") window.ProductLocale=Object.freeze({translate});
'''


def _compile(value, fields):
    template=text(value,"String katalog",800)
    result=[]
    used=set()
    last=0
    for match in HOLE.finditer(template):
        name=match.group(1)
        fragment=template[last:match.start()]
        if name not in fields or "{" in fragment or "}" in fragment:
            raise ContractError("Placeholder katalog tidak sesuai deklarasi.")
        result.append([fragment,name])
        used.add(name)
        last=match.end()
    suffix=template[last:]
    if "{" in suffix or "}" in suffix or used != fields.keys():
        raise ContractError("Terjemahan menghilangkan field atau meninggalkan brace.")
    return [*result,[suffix,None]]


def build(plan, expected):
    checked(plan,expected)
    schema(plan,"ace.factory-i18n-plan.v1",("id","source_ref","default_locale","messages"))
    product=identifier(plan["id"],"ID produk")
    source=text(plan["source_ref"],"Sumber katalog")
    fallback=plan["default_locale"]
    if not isinstance(fallback,str) or fallback not in LANGS:
        raise ContractError("Locale fallback perlu id atau en.")
    settings={"default":fallback,"messages":{},"locales":{locale:{} for locale in sorted(LANGS)}}
    links={}
    for raw in entries(plan["messages"],300,minimum=1):
        obj(raw,("id","fields","plural","translations","source_ref"))
        key=identifier(raw["id"],"Kunci pesan")
        if key in settings["messages"]:
            raise ContractError("Pesan ganda.")
        field_types={}
        for field in entries(raw["fields"],12):
            obj(field,("id","type"))
            name=identifier(field["id"],"ID field")
            if name in field_types or not isinstance(field["type"],str) or field["type"] not in KINDS:
                raise ContractError("Field ganda atau tipe tidak didukung.")
            field_types[name]=field["type"]
        plural=raw["plural"]
        if plural is not None and field_types.get(identifier(plural,"Field plural"))!="integer":
            raise ContractError("Field plural perlu integer yang dideklarasikan.")
        translated=obj(raw["translations"],LANGS)
        localized={}
        for locale, categories in LANGS.items():
            values=obj(translated[locale],categories if plural else {"other"})
            localized[locale]={category:_compile(value,field_types) for category,value in sorted(values.items())}
            settings["locales"][locale][key]=localized[locale]
        settings["messages"][key]={"fields":field_types,"plural":plural}
        links[key]=text(raw["source_ref"],"Sumber pesan")
    runtime=b"const MESSAGES = "+canonical(settings)+b";\n"+RUNTIME.encode()
    report={"schema":"ace.factory-i18n-build.v1","plan_sha256":expected,"product_id":product,"source_ref":source,
            "default_locale":fallback,"available_locales":sorted(LANGS),
            "messages":[{"id":key,"source_ref":links[key]} for key in sorted(links)],
            "runtime":{"path":"product_locale.js","sha256":sha256(runtime).hexdigest()}}
    return {"product_locale.js":runtime,"i18n_manifest.json":canonical(report)+b"\n"},report


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
    except (OSError,ValueError,RecursionError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
