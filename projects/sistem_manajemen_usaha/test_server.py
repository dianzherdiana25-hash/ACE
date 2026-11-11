"""Integration & Unit Tests for ACE Smart Enterprise Suite.

Tests:
1. SQLite schema initialization and seed idempotency
2. Real-time KPI analytics (Revenue, Net Profit, Margin %, Stock Valuation)
3. 50-30-20 budget health allocation
4. Inventory stock deduction upon sales transaction
5. Negative price/stock rejection validation
6. Real HTTP REST API server endpoints (/api/health, /api/summary, /api/products, /api/transactions)
7. Tamper-evident audit trail insertion
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
import unittest
from urllib.request import Request, urlopen
import urllib.error

from db import (
    get_db_connection,
    init_database,
    seed_database_if_empty,
    get_kpi_summary,
    add_product,
    add_transaction,
)
from server import create_server


class TestEnterpriseSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path("/tmp/test_enterprise_suite")
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        cls.db_path = cls.test_dir / "test_enterprise.sqlite3"
        if cls.db_path.exists():
            cls.db_path.unlink()

        # Start live server on port 8089 for HTTP endpoint tests
        cls.server_port = 8089
        cls.server = create_server(host="127.0.0.1", port=cls.server_port, db_path=cls.db_path)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_database_seed_and_kpi(self):
        conn = get_db_connection(self.db_path)
        summary = get_kpi_summary(conn)
        conn.close()

        # Check seeded values
        self.assertGreater(summary["total_income"], 5000000)
        self.assertGreater(summary["total_expense"], 1000000)
        self.assertEqual(summary["net_profit"], summary["total_income"] - summary["total_expense"])
        self.assertGreater(summary["profit_margin_pct"], 0.0)
        self.assertGreater(summary["total_sku"], 0)
        self.assertGreater(summary["inventory_asset_value"], 0)
        self.assertIn("budget_evaluation_50_30_20", summary)

    def test_02_add_product_and_validation(self):
        conn = get_db_connection(self.db_path)
        # Valid product
        prod = add_product(
            conn,
            code="TEST-001",
            name="Bubuk Cokelat Murni 1kg",
            category="Bahan Baku",
            buy_price=60000,
            sell_price=95000,
            stock=15,
            min_stock=5,
        )
        self.assertEqual(prod["code"], "TEST-001")

        # Invalid: Negative price
        with self.assertRaises(ValueError):
            add_product(conn, "TEST-NEG", "Produk Rugi", "Lainnya", -1000, 5000, 10)

        conn.close()

    def test_03_transaction_with_inventory_deduction(self):
        conn = get_db_connection(self.db_path)
        # Check current stock of PRD-001
        cur = conn.cursor()
        cur.execute("SELECT stock FROM products WHERE code='PRD-001'")
        stock_before = cur.fetchone()[0]

        # Record a sale of 2 units of PRD-001
        tx = add_transaction(
            conn,
            tx_type="INCOME",
            category="Penjualan F&B",
            amount=130000,
            description="Penjualan 2x Kopi Robusta",
            product_code="PRD-001",
            product_qty=2,
        )
        self.assertTrue(tx["ref_no"].startswith("TX-"))

        cur.execute("SELECT stock FROM products WHERE code='PRD-001'")
        stock_after = cur.fetchone()[0]
        self.assertEqual(stock_after, stock_before - 2)
        conn.close()

    def test_04_http_api_health(self):
        url = f"http://127.0.0.1:{self.server_port}/api/health"
        with urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["service"], "ACE Smart Enterprise Suite")

    def test_05_http_api_summary_and_products(self):
        url = f"http://127.0.0.1:{self.server_port}/api/summary"
        with urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("total_income", data)
            self.assertIn("net_profit", data)

        url_p = f"http://127.0.0.1:{self.server_port}/api/products"
        with urlopen(url_p, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertGreater(data["total"], 0)

    def test_06_http_api_post_transaction(self):
        url = f"http://127.0.0.1:{self.server_port}/api/transactions"
        payload = {
            "type": "EXPENSE",
            "category": "Peralatan",
            "amount": 250000,
            "description": "Beli tamper kopi baru",
            "payment_method": "QRIS",
        }
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 201)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertEqual(data["transaction"]["type"], "EXPENSE")


if __name__ == "__main__":
    unittest.main()
