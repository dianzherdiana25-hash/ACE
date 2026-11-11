"""Database layer & Core Business Logic for ACE Smart Enterprise Suite.

Features:
- SQLite persistent storage with WAL mode & ACID transactions
- Automatic seeding of initial enterprise records
- Multi-entity tables: products, transactions, budget allocations, audit trail
- Real-time KPI analytics (Revenue, Expenses, Net Profit, Margin %, Inventory Valuation)
- Budget health scoring based on 50-30-20 framework
- Stock alerts for items below minimum threshold
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
from typing import Any


def get_db_connection(db_path: Path | str) -> sqlite3.Connection:
    """Connect to SQLite database with foreign keys and WAL mode enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_database(conn: sqlite3.Connection) -> None:
    """Initialize relational database tables."""
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                min_stock INTEGER NOT NULL DEFAULT 5,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('INCOME', 'EXPENSE')),
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                ref_no TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL
            );
        """)


def seed_database_if_empty(conn: sqlite3.Connection) -> bool:
    """Populate database with realistic enterprise starter dataset if empty."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        return False

    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with conn:
        # 1. Products
        products_data = [
            ("PRD-001", "Kopi Robusta Temanggung 250g", "Bahan Baku", 35000, 65000, 42, 10, now_str),
            ("PRD-002", "Kopi Arabika Gayo 250g", "Bahan Baku", 55000, 95000, 18, 8, now_str),
            ("PRD-003", "Susu Segar Pasteurisasi 1L", "Bahan Baku", 18000, 28000, 6, 12, now_str),  # Warning: Low stock
            ("PRD-004", "Sirup Karamel Artisan 750ml", "Bahan Pelengkap", 65000, 110000, 14, 5, now_str),
            ("PRD-005", "Cup Takeaway Ramah Lingkungan 12oz (Pack 50)", "Kemasan", 30000, 48000, 3, 10, now_str),  # Critical
            ("PRD-006", "Pastry Croissant Butter (Satuan)", "Makanan Jadi", 12000, 24000, 25, 10, now_str),
        ]
        conn.executemany(
            "INSERT INTO products (code, name, category, buy_price, sell_price, stock, min_stock, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            products_data,
        )

        # 2. Transactions
        tx_data = [
            ("2026-11-01 09:15:00", "INCOME", "Penjualan F&B", 1850000, "Penjualan kasir offline batch 1", "QRIS", "TX-261101-01"),
            ("2026-11-02 11:30:00", "EXPENSE", "Bahan Baku", 750000, "Restock biji kopi Gayo", "Transfer Bank", "TX-261102-01"),
            ("2026-11-03 14:00:00", "INCOME", "Penjualan F&B", 2400000, "Penjualan paket catering meeting", "Transfer Bank", "TX-261103-01"),
            ("2026-11-04 10:00:00", "EXPENSE", "Operasional & Utilitas", 600000, "Tagihan listrik dan air mingguan", "Virtual Account", "TX-261104-01"),
            ("2026-11-05 16:45:00", "INCOME", "Penjualan F&B", 3100000, "Weekend rush penjualan kopi & pastry", "QRIS / Tunai", "TX-261105-01"),
            ("2026-11-06 13:20:00", "EXPENSE", "Gaji & Upah Barista", 1500000, "Uang saku & upah part-time shift", "Transfer Bank", "TX-261106-01"),
            ("2026-11-07 15:10:00", "EXPENSE", "Pemasaran & Ads", 350000, "Promosi media sosial Instagram lokal", "Kartu Debit", "TX-261107-01"),
            ("2026-11-08 17:30:00", "INCOME", "Penjualan F&B", 2800000, "Penjualan harian kafe", "QRIS", "TX-261108-01"),
        ]
        conn.executemany(
            "INSERT INTO transactions (timestamp, type, category, amount, description, payment_method, ref_no) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            tx_data,
        )

        # 3. Initial Audit Log
        conn.execute(
            "INSERT INTO audit_trail (timestamp, actor, action, details) VALUES (?, ?, ?, ?)",
            (now_str, "Sistem ACE", "SEED_DATABASE", json.dumps({"status": "SUCCESS", "records_inserted": len(products_data) + len(tx_data)})),
        )
    return True


def record_audit(conn: sqlite3.Connection, actor: str, action: str, details: dict[str, Any]) -> None:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with conn:
        conn.execute(
            "INSERT INTO audit_trail (timestamp, actor, action, details) VALUES (?, ?, ?, ?)",
            (now_str, actor, action, json.dumps(details, ensure_ascii=False)),
        )


def get_kpi_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compute enterprise financial health, inventory valuation, and budget ratios."""
    cur = conn.cursor()

    # Total Income and Expense
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='INCOME'")
    total_income = float(cur.fetchone()[0])

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='EXPENSE'")
    total_expense = float(cur.fetchone()[0])

    net_profit = total_income - total_expense
    profit_margin = round((net_profit / total_income * 100), 2) if total_income > 0 else 0.0

    # Inventory Valuation & Stock Alerts
    cur.execute("SELECT COUNT(*), COALESCE(SUM(buy_price * stock), 0), COALESCE(SUM(sell_price * stock), 0) FROM products")
    row_inv = cur.fetchone()
    total_sku = int(row_inv[0])
    inventory_asset_value = float(row_inv[1])
    inventory_potential_sales = float(row_inv[2])

    # Low stock items
    cur.execute("SELECT code, name, stock, min_stock FROM products WHERE stock <= min_stock")
    low_stock_items = [
        {"code": r[0], "name": r[1], "stock": r[2], "min_stock": r[3], "status": "HABIS" if r[2] == 0 else "KRITIS"}
        for r in cur.fetchall()
    ]

    # Category Breakdown for Expenses
    cur.execute("""
        SELECT category, SUM(amount) as cat_total 
        FROM transactions 
        WHERE type='EXPENSE' 
        GROUP BY category 
        ORDER BY cat_total DESC
    """)
    expenses_by_category = [{"category": r[0], "total": float(r[1])} for r in cur.fetchall()]

    # 50-30-20 Business Allocation Simulation
    # 50%: Operational Needs (Bahan Baku, Utilitas, Gaji)
    # 30%: Growth & Expansion (Pemasaran, Inovasi Menu)
    # 20%: Emergency Reserve / Retained Profit
    kebutuhan_total = sum(e["total"] for e in expenses_by_category if e["category"] in ("Bahan Baku", "Operasional & Utilitas", "Gaji & Upah Barista"))
    keinginan_total = sum(e["total"] for e in expenses_by_category if e["category"] in ("Pemasaran & Ads", "Renovasi & Dekorasi", "Lain-lain"))
    tabungan_laba = max(0.0, net_profit)

    ratio_income = max(1.0, total_income)
    eval_50_30_20 = {
        "kebutuhan_operasional": {
            "amount": kebutuhan_total,
            "pct": round(kebutuhan_total / ratio_income * 100, 1),
            "target_pct": 50.0,
            "status": "IDEAL" if (kebutuhan_total / ratio_income) <= 0.52 else "OVERBUDGET",
        },
        "pertumbuhan_dan_pemasaran": {
            "amount": keinginan_total,
            "pct": round(keinginan_total / ratio_income * 100, 1),
            "target_pct": 30.0,
            "status": "IDEAL" if (keinginan_total / ratio_income) <= 0.32 else "OVERBUDGET",
        },
        "cadangan_kas_dan_laba": {
            "amount": tabungan_laba,
            "pct": round(tabungan_laba / ratio_income * 100, 1),
            "target_pct": 20.0,
            "status": "SEHAT" if (tabungan_laba / ratio_income) >= 0.18 else "PERLU_DITINGKATKAN",
        },
    }

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": net_profit,
        "profit_margin_pct": profit_margin,
        "total_sku": total_sku,
        "inventory_asset_value": inventory_asset_value,
        "inventory_potential_sales": inventory_potential_sales,
        "low_stock_count": len(low_stock_items),
        "low_stock_items": low_stock_items,
        "expenses_by_category": expenses_by_category,
        "budget_evaluation_50_30_20": eval_50_30_20,
    }


def add_product(
    conn: sqlite3.Connection,
    code: str,
    name: str,
    category: str,
    buy_price: float,
    sell_price: float,
    stock: int,
    min_stock: int = 5,
    actor: str = "Admin",
) -> dict[str, Any]:
    """Add a new product with validation."""
    if buy_price < 0 or sell_price < 0:
        raise ValueError("Harga tidak boleh bernilai negatif")
    if stock < 0:
        raise ValueError("Stok tidak boleh bernilai negatif")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with conn:
        conn.execute(
            "INSERT INTO products (code, name, category, buy_price, sell_price, stock, min_stock, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (code, name, category, buy_price, sell_price, stock, min_stock, now_str),
        )
    record_audit(conn, actor, "ADD_PRODUCT", {"code": code, "name": name, "stock": stock})
    return {"code": code, "name": name, "stock": stock}


def add_transaction(
    conn: sqlite3.Connection,
    tx_type: str,
    category: str,
    amount: float,
    description: str,
    payment_method: str = "Transfer Bank",
    actor: str = "Kasir / Admin",
    product_code: str | None = None,
    product_qty: int = 0,
) -> dict[str, Any]:
    """Record transaction and update inventory atomically."""
    if amount <= 0:
        raise ValueError("Jumlah transaksi harus lebih besar dari 0")
    if tx_type not in ("INCOME", "EXPENSE"):
        raise ValueError("Tipe transaksi harus 'INCOME' atau 'EXPENSE'")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ref_no = f"TX-{time.strftime('%y%m%d')}-{int(time.time() * 1000) % 100000:05d}"

    with conn:
        conn.execute(
            "INSERT INTO transactions (timestamp, type, category, amount, description, payment_method, ref_no) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now_str, tx_type, category, amount, description, payment_method, ref_no),
        )

        # If linked to a product sale or restock, adjust stock
        if product_code and product_qty > 0:
            if tx_type == "INCOME":
                conn.execute(
                    "UPDATE products SET stock = MAX(0, stock - ?), updated_at = ? WHERE code = ?",
                    (product_qty, now_str, product_code),
                )
            elif tx_type == "EXPENSE":
                conn.execute(
                    "UPDATE products SET stock = stock + ?, updated_at = ? WHERE code = ?",
                    (product_qty, now_str, product_code),
                )

    record_audit(conn, actor, f"TRANSACTION_{tx_type}", {"ref_no": ref_no, "amount": amount, "category": category})
    return {"ref_no": ref_no, "type": tx_type, "amount": amount, "timestamp": now_str}
