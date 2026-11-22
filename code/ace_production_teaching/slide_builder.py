"""Render kerangka ke slide PPTX asli dengan bidang teks, catatan sumber dan tabel editable."""
import argparse
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys

from ._artifacts import evidence, package, unpack
from ._contracts import (ProductionError, anchor, canonical, decode, identifier,
                         items, obj, read, schema, text)


def _typed(raw):
    slides = []
    seen = set()
    for row in items(raw, 36, 1):
        obj(row, ("id", "title", "kind", "content", "source_ref"))
        key = identifier(row["id"], "Slide")
        if key in seen:
            raise ProductionError("ID slide ganda.")
        seen.add(key)
        kind = row["kind"]
        title = text(row["title"], "Judul slide", 66)
        pointer = text(row["source_ref"], "Sumber slide", 120)
        if kind == "bullets":
            value = [text(item, "Poin slide", 120) for item in items(row["content"], 6, 1)]
            if sum(len(item) for item in value) > 430:
                raise ProductionError("Bullet melampaui ruang slide.")
        elif kind == "comparison":
            value = {}
            for slot in ("left", "right"):
                pair = obj(row["content"], ("left", "right"))[slot]
                obj(pair, ("heading", "points"))
                points = [text(item, "Poin pembanding", 62) for item in items(pair["points"], 5, 1)]
                value[slot] = {"heading": text(pair["heading"], "Judul kolom", 24), "points": points}
        elif kind == "table":
            grid = obj(row["content"], ("columns", "rows"))
            cols = [text(item, "Label kolom", 24) for item in items(grid["columns"], 5, 1)]
            if len(set(cols)) != len(cols):
                raise ProductionError("Kolom tabel pitch berulang.")
            rows = []
            for line in items(grid["rows"], 6, 1):
                if not isinstance(line, list) or len(line) != len(cols):
                    raise ProductionError("Tabel slide memiliki lebar tidak konsisten.")
                rows.append([text(item, "Sel slide", 30) for item in line])
            value = {"columns": cols, "rows": rows}
        else:
            raise ProductionError("Jenis slide belum didukung.")
        slides.append({"id": key, "title": title, "kind": kind, "payload": value, "source_ref": pointer})
    return slides


def make_slides(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.production.slide-plan.v1", ("title", "slides"))
    title = text(plan["title"], "Judul deck", 120)
    outline = _typed(plan["slides"])
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.util import Inches, Pt
    except ImportError as error:
        raise ProductionError("Backend lokal python-pptx diperlukan untuk menulis slide.") from error
    system = Presentation()
    system.slide_width = Inches(13.333)
    system.slide_height = Inches(7.5)
    core = system.core_properties
    core.title = title
    core.author = "ACE"
    core.last_modified_by = "ACE"
    core.created = core.modified = datetime(2000, 1, 1)
    core.revision = 1

    charcoal = RGBColor(22, 35, 50)
    foreground = RGBColor(24, 37, 50)
    muted = RGBColor(64, 83, 100)
    rule = RGBColor(14, 99, 120)

    def shape(slide, value, x, y, width, height, size, ink, bold=False):
        frame = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height)).text_frame
        frame.word_wrap = True
        frame.margin_left = 0
        frame.margin_right = 0
        frame.margin_top = 0
        frame.margin_bottom = 0
        line = frame.paragraphs[0]
        line.text = value
        line.font.name = "Aptos"
        line.font.size = Pt(size)
        line.font.bold = bold
        line.font.color.rgb = ink
        line.alignment = PP_ALIGN.LEFT
        return frame

    def points(slide, values, x, y, width, max_h, size):
        frame = shape(slide, "", x, y, width, max_h, size, foreground)
        for index, value in enumerate(values):
            line = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            line.text = "• " + value
            line.font.name = "Aptos"
            line.font.size = Pt(size)
            line.font.color.rgb = foreground
            line.space_after = Pt(11)

    for position, item in enumerate(outline, 1):
        slide = system.slides.add_slide(system.slide_layouts[6])
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = RGBColor(247, 249, 251)
        shape(slide, item["title"], 0.65, 0.48, 12.0, 1.0, 34, charcoal, True)
        content = item["payload"]
        if item["kind"] == "bullets":
            points(slide, content, 0.8, 1.65, 11.65, 4.9, 24)
        elif item["kind"] == "comparison":
            for index, key in enumerate(("left", "right")):
                x = 0.75 + index * 6.28
                left = content[key]
                shape(slide, left["heading"], x, 1.58, 5.7, 0.55, 23, rule, True)
                points(slide, left["points"], x, 2.27, 5.45, 4.3, 18)
        else:
            cols = content["columns"]
            rows = [cols, *content["rows"]]
            table = slide.shapes.add_table(len(rows), len(cols), Inches(0.7), Inches(1.6), Inches(11.92), Inches(4.4)).table
            for row_index, values in enumerate(rows):
                for col, value in enumerate(values):
                    cell = table.cell(row_index, col)
                    cell.text = value
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = rule if row_index == 0 else RGBColor(234, 240, 245)
                    paragraph = cell.text_frame.paragraphs[0]
                    paragraph.font.size = Pt(16 if len(cols) > 3 else 19)
                    paragraph.font.color.rgb = RGBColor(255, 255, 255) if row_index == 0 else foreground
                    paragraph.font.bold = row_index == 0
        shape(slide, item["source_ref"], 0.7, 6.98, 11.2, 0.32, 11, muted)
        shape(slide, str(position), 12.15, 6.98, 0.5, 0.32, 11, muted)
    with BytesIO() as stage:
        system.save(stage)
        raw = package(unpack(stage.getvalue()))
    return raw, {"schema": "ace.production.slide-receipt.v1", "plan_sha256": expected,
                 "output": evidence({"slides.pptx": raw}), "title": title, "slides": [
                     {key: item[key] for key in ("id", "title", "kind", "source_ref")} for item in outline]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        blob, result = make_slides(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(blob)
        sys.stdout.buffer.write(canonical(result) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
