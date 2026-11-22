from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .static_dashboard import dashboard
from .test_tabular_engine import save


class IDs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if "aria-labelledby" in values:
            self.references.extend(values["aria-labelledby"].split())
        if "href" in values and values["href"].startswith("#"):
            self.references.append(values["href"][1:])


class DashboardTests(unittest.TestCase):
    def test_one_html_with_escaped_data_unique_ids_and_local_navigation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = {"schema": "ace.production.chart-plan.v1", "title": "Ukuran", "kind": "line",
                    "width": 420, "height": 240, "y_label": "Lux", "y_axis": None, "points": [
                       {"label": "A", "value": 4, "source_ref": "fixture:a"},
                       {"label": "B", "value": 5, "source_ref": "fixture:b"}]}
            plan = {"schema": "ace.production.dashboard-plan.v1", "title": "Data", "language": "id", "sections": [
                {"id": "rows", "heading": "Tabel", "kind": "table",
                 "source": save(root, "data.csv", b"nominal\n<script>\n")},
                {"id": "chart", "heading": "Grafik", "kind": "chart",
                 "source": save(root, "chart.json", canonical(spec))}]}
            data, receipt = dashboard(plan, identity(plan), root)
            scanner = IDs()
            scanner.feed(data.decode())
            self.assertEqual(len(set(scanner.ids)), len(scanner.ids))
            self.assertLessEqual(set(scanner.references), set(scanner.ids))
            self.assertNotIn("script", scanner.tags)
            self.assertIn(b"&lt;script&gt;", data)
            self.assertEqual([row["records"] for row in receipt["sections"]], [1, 2])
