"""Bangun halaman arahan produk dari klaim dan tindakan yang disetujui.

Isi datang dari kontrak. Setiap benefit menunjuk sumber, dan tautan CTA
hanya dapat merujuk bagian halaman atau rute relatif yang terdaftar.
Artefak statis dapat dibuka lokal tanpa JavaScript, font atau pelacak CDN.
"""
import argparse
from hashlib import sha256
from html import escape
from pathlib import Path
import re
import sys

from ._artifact_io import read_relative
from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, obj, read, schema, text
from .repo_scaffolder import materialize


COLOR = re.compile(r"#[0-9a-fA-F]{6}")
ROUTE = re.compile(r"/[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*/?")
CSS = """
*{box-sizing:border-box}
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#17212c;background:#f8fafc;line-height:1.6}
body{margin:0}
.shell{max-width:68rem;margin:auto;padding:1rem clamp(1rem, 4vw, 3rem)}
nav{display:flex;gap:1.5rem;align-items:center;justify-content:space-between;padding:.9rem 0}
.brand{font-weight:750;color:#17212c}
nav a,.hero a{color:var(--accent);text-underline-offset:.22em;font-weight:700}
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,21rem),1fr));gap:2rem;align-items:center;padding:4rem 0}
.hero h1{font-size:clamp(2.65rem,6.6vw,5.2rem);font-weight:790;letter-spacing:-.05em;line-height:1.04;margin:0 0 1.2rem}
.hero p{max-width:44ch;font-size:1.13rem}
.hero img{width:100%;height:auto;display:block;border-radius:.75rem}
.primary{display:inline-block;padding:.7rem 1.25rem;border:2px solid var(--accent);border-radius:.52rem}
.blocks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr));gap:1rem}
article{padding:1.35rem 1.45rem;background:white;border-radius:.65rem;border:1px solid #dbe4ed}
article h3{font-size:1.16rem;margin:0}
section{margin-bottom:3rem}
footer{border-top:1px solid #dbe4ed;padding:1.2rem 0}
a:focus-visible{outline:3px solid #17212c;outline-offset:4px}
""".strip()


def _accent(value):
    if not isinstance(value, str) or not COLOR.fullmatch(value):
        raise ContractError("Warna aksen perlu hex enam digit.")
    channels = [int(value[index:index+2], 16) / 255.0 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055)/1.055)**2.4 for channel in channels]
    lightness = sum(weight * v for weight, v in zip((0.2126, 0.7152, 0.0722), linear))
    if (0.954 + 0.05) / (lightness + 0.05) < 4.5:
        raise ContractError("Aksen tidak memenuhi kontras teks 4.5:1.")
    return value.casefold()


def _picture(root, raw):
    if raw is None:
        return None, None
    obj(raw, ("path", "sha256", "alt", "source_ref"))
    path = text(raw["path"], "Path gambar", 200)
    if not path.endswith((".png", ".jpg", ".jpeg")):
        raise ContractError("Gambar perlu PNG atau JPEG lokal.")
    anchor = digest(raw["sha256"])
    content = read_relative(root, path, 1_000_000, anchor)
    png = path.endswith(".png")
    if not content.startswith(b"\x89PNG\r\n\x1a\n" if png else b"\xff\xd8\xff"):
        raise ContractError("Jenis byte gambar tidak cocok dengan ekstensi.")
    name = "assets/hero.png" if png else "assets/hero.jpg"
    return {"path": name, "sha256": anchor, "alt": text(raw["alt"], "Deskripsi gambar", 240),
            "source_ref": text(raw["source_ref"], "Sumber gambar")}, content


def build(root, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-landing-plan.v1", ("id", "lang", "name", "headline", "summary",
                                                "source_ref", "accent", "benefits", "cta", "routes", "hero"))
    product = identifier(plan["id"], "ID produk")
    lang = plan["lang"]
    if lang not in ("id", "en"):
        raise ContractError("Bahasa halaman belum didukung.")
    name = text(plan["name"], "Nama produk", 120)
    headline = text(plan["headline"], "Judul", 110)
    summary = text(plan["summary"], "Ringkasan", 230)
    source = text(plan["source_ref"], "Rujukan penawaran", 200)
    accent = _accent(plan["accent"])
    routes = []
    for raw in entries(plan["routes"], 30):
        route = text(raw, "Rute CTA", 180)
        if not ROUTE.fullmatch(route) or route in routes:
            raise ContractError("Rute CTA ganda atau tidak relatif.")
        routes.append(route)
    cta = obj(plan["cta"], ("label", "target", "source_ref"))
    label = text(cta["label"], "Tindakan utama", 80)
    target = text(cta["target"], "Target utama", 180)
    if target not in {"#benefits", *routes}:
        raise ContractError("Tujuan CTA belum terdaftar.")
    cta_ref = text(cta["source_ref"], "Rujukan tindakan", 200)
    picture, image = _picture(root, plan["hero"])

    benefits = {}
    for raw in entries(plan["benefits"], 12, minimum=1):
        obj(raw, ("id", "title", "description", "source_ref"))
        key = identifier(raw["id"], "Manfaat")
        if key in benefits:
            raise ContractError("ID manfaat ganda.")
        benefits[key] = (text(raw["title"], "Judul manfaat", 100), text(raw["description"], "Manfaat", 280),
                         text(raw["source_ref"], "Rujukan manfaat", 200))
    benefit_label = "Manfaat" if lang == "id" else "Benefits"
    product_logo = escape(name)
    hero = f'<img src="{picture["path"]}" alt="{escape(picture["alt"])}">' if picture else ""
    cards = "\n".join(f'<article id="benefit-{key}"><h3>{escape(title)}</h3><p>{escape(body)}</p></article>'
                      for key, (title, body, _) in benefits.items())
    page = f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{escape(summary)}">
<title>{product_logo}</title>
<link rel="stylesheet" href="landing.css">
</head>
<body>
<div class="shell">
<nav aria-label="{benefit_label}"><span class="brand">{product_logo}</span><a href="#benefits">{benefit_label}</a></nav>
<main>
<header class="hero"><div><h1>{escape(headline)}</h1><p>{escape(summary)}</p>
<a class="primary" href="{escape(target)}">{escape(label)}</a></div>{hero}</header>
<section id="benefits" aria-labelledby="benefit-heading">
<h2 id="benefit-heading">{benefit_label}</h2>
<div class="blocks">{cards}</div>
</section>
</main>
<footer>{product_logo}</footer>
</div>
</body>
</html>
'''.encode()
    files = {"index.html": page, "landing.css": f":root{{--accent:{accent}}}\n{CSS}\n".encode()}
    if picture:
        files[picture["path"]] = image
    report = {"schema": "ace.factory-landing-build.v1", "plan_sha256": expected, "product_id": product,
              "source_ref": source, "benefits": [{"id": key, "source_ref": row[2]} for key, row in benefits.items()],
              "cta": {"target": target, "source_ref": cta_ref}, "hero": picture,
              "files": [{"path": path, "sha256": sha256(data).hexdigest()} for path, data in sorted(files.items())]}
    return {**files, "landing_manifest.json": canonical(report) + b"\n"}, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = build(args.root, decode(read(args.plan)), args.expect_sha256)
        materialize(args.output, files)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
