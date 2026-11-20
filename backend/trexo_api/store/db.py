"""SQLite persistence for the store-operations domain.

Entities are stored as JSON documents keyed by id.  The nested shapes are owned
by the frontend contract (``types/domain.ts``), so document storage keeps the
API honest without an ORM.  Writes are transactional.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_payments (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS suppliers (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS supplier_returns (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS purchase_orders (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ml_sales_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    sale_date TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    invoice_no TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ml_hist_product ON ml_sales_history(product_id, sale_date);
"""

_lock = threading.RLock()


class StoreDB:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with _lock:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ---- generic helpers -------------------------------------------------
    def all(self, table: str, order_by: str = "created_at", direction: str = "DESC") -> list[dict]:
        assert table in _TABLES
        assert direction in ("ASC", "DESC")
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT data FROM {table} ORDER BY {order_by} {direction}"
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def get(self, table: str, row_id: str) -> dict | None:
        assert table in _TABLES
        with self.connection() as conn:
            row = conn.execute(f"SELECT data FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def put(self, table: str, row_id: str, data: dict, created_at: str) -> dict:
        assert table in _TABLES
        with self.connection() as conn:
            conn.execute(
                f"INSERT INTO {table}(id, created_at, data) VALUES (?,?,?) "
                f"ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (row_id, created_at, json.dumps(data, separators=(",", ":"))),
            )
        return data

    def delete(self, table: str, row_id: str) -> bool:
        assert table in _TABLES
        with self.connection() as conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            return cur.rowcount > 0

    def count(self, table: str) -> int:
        assert table in _TABLES
        with self.connection() as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def has_history(self) -> bool:
        with self.connection() as conn:
            return conn.execute("SELECT 1 FROM ml_sales_history LIMIT 1").fetchone() is not None

    # ---- meta ------------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ---- ML history ------------------------------------------------------
    def add_history_rows(self, rows: list[tuple[str, str, float, float, str]]) -> None:
        with self.connection() as conn:
            conn.executemany(
                "INSERT INTO ml_sales_history(product_id, sale_date, quantity, unit_price, invoice_no) "
                "VALUES (?,?,?,?,?)",
                rows,
            )

    def history_for(self, product_ids: list[str] | None = None) -> dict[str, list[dict]]:
        sql = "SELECT product_id, sale_date, quantity, unit_price, invoice_no FROM ml_sales_history"
        params: tuple[Any, ...] = ()
        if product_ids:
            placeholders = ",".join("?" for _ in product_ids)
            sql += f" WHERE product_id IN ({placeholders})"
            params = tuple(product_ids)
        sql += " ORDER BY product_id, sale_date"
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["product_id"], []).append(
                {
                    "date": r["sale_date"],
                    "quantity": r["quantity"],
                    "unit_price": r["unit_price"],
                    "invoice_no": r["invoice_no"],
                }
            )
        return out

    def reset_domain(self) -> None:
        with self.connection() as conn:
            for table in _TABLES:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM meta")
            conn.execute("DELETE FROM ml_sales_history")


_TABLES = {
    "products",
    "sales",
    "customers",
    "customer_payments",
    "suppliers",
    "supplier_returns",
    "purchase_orders",
}
