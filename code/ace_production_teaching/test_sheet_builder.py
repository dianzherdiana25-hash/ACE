from importlib.util import find_spec
from io import BytesIO
from xml.etree import ElementTree as ET
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from .sheet_builder import NS, make_workbook


def workbook():
    rows = [(at, kind, value) for at, kind, value in (
        ("A1", "number", "5.25"), ("A2", "number", "6.75"), ("B1", "text", "=text"),
        ("B2", "formula", "=SUM(A1:A2)"), ("B3", "formula", "=ROUND(B2/7,2)"), ("B4", "formula", "=-2^2"),
        ("B5", "formula", "=2^3^2"))]
    return {"schema": "ace.production.workbook-plan.v1", "sheets": [
                {"name": "Fixture", "cells": [{"at": at, "kind": kind, "value": value,
                                                "source_ref": "fixture:workbook"} for at, kind, value in rows]}]}


class WorkbookTests(unittest.TestCase):
    def test_xml_contains_live_formula_and_cached_independently_computed_amounts(self):
        plan = workbook()
        raw, report = make_workbook(plan, identity(plan))
        sheet = ET.fromstring(unpack(raw)["xl/worksheets/sheet1.xml"])
        formulas = {row["at"]: row["cached"] for row in report["sheets"][0]["formulas"]}
        self.assertEqual(formulas, {"B2": "12", "B3": "1.71", "B4": "4", "B5": "64"})
        self.assertEqual(sheet.find(f".//{{{NS}}}c[@r='B2']/{{{NS}}}f").text, "SUM(A1:A2)")
        self.assertEqual(sheet.find(f".//{{{NS}}}c[@r='B1']").attrib["t"], "inlineStr")
        plan["sheets"][0]["cells"][0].update(kind="formula", value="=B2")
        with self.assertRaisesRegex(ProductionError, "siklus"):
            make_workbook(plan, identity(plan))

    @unittest.skipUnless(find_spec("openpyxl"), "Pembaca workbook lokal diperlukan")
    def test_openpyxl_reads_formula_and_evaluated_data_cache(self):
        from openpyxl import load_workbook

        plan = workbook()
        raw, _ = make_workbook(plan, identity(plan))
        formulas = load_workbook(BytesIO(raw))
        values = load_workbook(BytesIO(raw), data_only=True)
        self.assertEqual(formulas.active["B2"].value, "=SUM(A1:A2)")
        self.assertEqual(values.active["B2"].value, 12)
        self.assertEqual(formulas.active["B1"].data_type, "s")
        self.assertEqual(formulas.active["B1"].value, "=text")
        plan["sheets"][0]["cells"][3]["value"] = "=WEBSERVICE(\"https://example.test\")"
        with self.assertRaises(ProductionError):
            make_workbook(plan, identity(plan))
