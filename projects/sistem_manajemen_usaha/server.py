"""REST API & Web Application Server for ACE Smart Enterprise Suite.

Provides RESTful endpoints and serves the modern interactive dashboard UI.
Zero external pip dependencies: built strictly on Python 3 standard library.
"""
from __future__ import annotations

import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
from pathlib import Path
import sys
import urllib.parse

from db import (
    get_db_connection,
    init_database,
    seed_database_if_empty,
    get_kpi_summary,
    add_product,
    add_transaction,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("enterprise_server")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB_PATH = BASE_DIR / "enterprise.sqlite3"


class EnterpriseAPIHandler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_DB_PATH

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/health":
            self._send_json({
                "status": "healthy",
                "service": "ACE Smart Enterprise Suite",
                "version": "1.0.0",
                "database": str(self.db_path.name),
            })
            return

        conn = get_db_connection(self.db_path)
        try:
            if path == "/api/summary":
                summary = get_kpi_summary(conn)
                self._send_json(summary)
                return

            elif path == "/api/products":
                cur = conn.cursor()
                cur.execute("SELECT * FROM products ORDER BY stock ASC, name ASC")
                products = [dict(row) for row in cur.fetchall()]
                self._send_json({"total": len(products), "products": products})
                return

            elif path == "/api/transactions":
                cur = conn.cursor()
                cur.execute("SELECT * FROM transactions ORDER BY timestamp DESC, id DESC LIMIT 100")
                txs = [dict(row) for row in cur.fetchall()]
                self._send_json({"total": len(txs), "transactions": txs})
                return

            elif path == "/api/audit-trail":
                cur = conn.cursor()
                cur.execute("SELECT * FROM audit_trail ORDER BY id DESC LIMIT 50")
                logs = [dict(row) for row in cur.fetchall()]
                self._send_json({"total": len(logs), "audit_logs": logs})
                return

            # Static Assets
            if path in ("/", "/index.html"):
                self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
                return
            elif path == "/style.css":
                self._serve_file(STATIC_DIR / "style.css", "text/css; charset=utf-8")
                return
            elif path == "/app.js":
                self._serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
                return

            self._send_json({"error": "Endpoint tidak ditemukan", "path": path}, status=404)
        finally:
            conn.close()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length)

        try:
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Payload JSON tidak valid"}, status=400)
            return

        conn = get_db_connection(self.db_path)
        try:
            if path == "/api/products":
                req_fields = ["code", "name", "category", "buy_price", "sell_price", "stock"]
                missing = [f for f in req_fields if f not in payload]
                if missing:
                    self._send_json({"error": f"Field wajib belum diisi: {missing}"}, status=400)
                    return
                prod = add_product(
                    conn,
                    code=str(payload["code"]),
                    name=str(payload["name"]),
                    category=str(payload["category"]),
                    buy_price=float(payload["buy_price"]),
                    sell_price=float(payload["sell_price"]),
                    stock=int(payload["stock"]),
                    min_stock=int(payload.get("min_stock", 5)),
                    actor=str(payload.get("actor", "Web Dashboard User")),
                )
                self._send_json({"success": True, "product": prod}, status=201)
                return

            elif path == "/api/transactions":
                req_fields = ["type", "category", "amount", "description"]
                missing = [f for f in req_fields if f not in payload]
                if missing:
                    self._send_json({"error": f"Field wajib belum diisi: {missing}"}, status=400)
                    return
                tx = add_transaction(
                    conn,
                    tx_type=str(payload["type"]),
                    category=str(payload["category"]),
                    amount=float(payload["amount"]),
                    description=str(payload["description"]),
                    payment_method=str(payload.get("payment_method", "QRIS / Transfer")),
                    actor=str(payload.get("actor", "Kasir / Admin")),
                    product_code=payload.get("product_code"),
                    product_qty=int(payload.get("product_qty", 0)),
                )
                self._send_json({"success": True, "transaction": tx}, status=201)
                return

            self._send_json({"error": "Endpoint POST tidak ditemukan"}, status=404)
        except ValueError as val_err:
            self._send_json({"error": str(val_err)}, status=422)
        except Exception as exc:
            logger.exception(f"Error handling POST {path}: {exc}")
            self._send_json({"error": f"Kesalahan internal server: {exc}"}, status=500)
        finally:
            conn.close()

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self._send_json({"error": f"Berkas tidak ditemukan: {file_path.name}"}, status=404)
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP request spam to keep terminal clean."""
        return


def create_server(host: str = "127.0.0.1", port: int = 8085, db_path: Path = DEFAULT_DB_PATH) -> HTTPServer:
    # Ensure database is prepared
    conn = get_db_connection(db_path)
    init_database(conn)
    seed_database_if_empty(conn)
    conn.close()

    EnterpriseAPIHandler.db_path = db_path
    server = HTTPServer((host, port), EnterpriseAPIHandler)
    logger.info(f"ACE Smart Enterprise Server siap di http://{host}:{port}")
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACE Smart Enterprise Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8085, help="Port (default: 8085)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path ke berkas SQLite")
    args = parser.parse_args()

    srv = create_server(host=args.host, port=args.port, db_path=Path(args.db))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server dihentikan oleh pengguna.")
        srv.server_close()
