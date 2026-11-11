import sys
from pathlib import Path

_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest

from ace_operational.terminal_chart_visualizer import (
    render_bar_chart,
    render_distribution_bar,
    render_progress_bar,
    render_sparkline,
)


class TestTerminalChartVisualizer(unittest.TestCase):

    def test_render_sparkline(self):
        self.assertEqual(render_sparkline([]), "")
        # Nilai datar (konstan) menghasilkan karakter tengah konsisten
        flat = render_sparkline([10, 10, 10])
        self.assertEqual(len(flat), 3)

        # Nilai naik menghasilkan blok dari terendah ke tertinggi
        rising = render_sparkline([0, 50, 100])
        self.assertEqual(len(rising), 3)
        self.assertEqual(rising[0], " ")
        self.assertEqual(rising[-1], "█")

    def test_render_progress_bar(self):
        p0 = render_progress_bar(0, 100, length=10)
        self.assertIn("0.0%", p0)
        self.assertIn("░" * 10, p0)

        p100 = render_progress_bar(100, 100, length=10)
        self.assertIn("100.0%", p100)
        self.assertIn("█" * 10, p100)

        p50 = render_progress_bar(50, 100, length=20, label="Unduh Model")
        self.assertIn("Unduh Model:", p50)
        self.assertIn("50.0%", p50)

    def test_render_bar_chart(self):
        chart = render_bar_chart({})
        self.assertIn("Tidak ada data", chart)

        data = {
            "Kebutuhan": 5000000,
            "Keinginan": 3000000,
            "Tabungan": 2000000,
        }
        res = render_bar_chart(data, max_width=20, unit="Rp")
        self.assertIn("Kebutuhan", res)
        self.assertIn("Keinginan", res)
        self.assertIn("Tabungan", res)
        self.assertIn("50.0%", res)
        self.assertIn("30.0%", res)
        self.assertIn("20.0%", res)

    def test_render_distribution_bar(self):
        empty = render_distribution_bar({})
        self.assertIn("Data kosong", empty)

        data = {"Pokok": 50, "Sekunder": 30, "Tersier": 20}
        dist = render_distribution_bar(data, width=20)
        self.assertIn("[", dist)
        self.assertIn("Pokok: 50.0%", dist)
        self.assertIn("Sekunder: 30.0%", dist)
        self.assertIn("Tersier: 20.0%", dist)


if __name__ == "__main__":
    unittest.main()
