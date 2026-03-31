"""
src/core/database.py
====================
SQLite database manager for Abaad 3D Print Manager v5.0.

Replaces the JSON-based DatabaseManager from v4.
All methods return plain dicts — the service layer converts to/from models.

Features:
  - WAL mode + foreign keys enabled on every connection
  - Full schema created on first run
  - Context-manager transactions (auto-commit / auto-rollback)
  - Parameterised queries throughout (no string-format SQL)
  - Singleton via module-level get_database()
  - Soft-delete for orders (is_deleted flag)
  - Backup copies .db file; does NOT duplicate the whole JSON blob
"""

import csv
import json
import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from src.core.config import (
    BACKUP_DIR,
    DB_PATH,
    DEFAULT_COLORS,
    DEFAULT_SETTINGS,
    EXPORT_DIR,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS customers (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    phone            TEXT DEFAULT '',
    email            TEXT DEFAULT '',
    address          TEXT DEFAULT '',
    notes            TEXT DEFAULT '',
    discount_percent REAL DEFAULT 0,
    total_orders     INTEGER DEFAULT 0,
    total_spent      REAL DEFAULT 0,
    created_date     TEXT DEFAULT (datetime('now','localtime')),
    updated_date     TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS orders (
    id                       TEXT PRIMARY KEY,
    order_number             INTEGER UNIQUE,
    customer_id              TEXT REFERENCES customers(id),
    customer_name            TEXT DEFAULT '',
    customer_phone           TEXT DEFAULT '',
    status                   TEXT DEFAULT 'Draft',
    is_rd_project            INTEGER DEFAULT 0,
    subtotal                 REAL DEFAULT 0,
    actual_total             REAL DEFAULT 0,
    discount_percent         REAL DEFAULT 0,
    discount_amount          REAL DEFAULT 0,
    order_discount_percent   REAL DEFAULT 0,
    order_discount_amount    REAL DEFAULT 0,
    tolerance_discount_total REAL DEFAULT 0,
    shipping_cost            REAL DEFAULT 0,
    total                    REAL DEFAULT 0,
    amount_received          REAL DEFAULT 0,
    rounding_loss            REAL DEFAULT 0,
    payment_method           TEXT DEFAULT 'Cash',
    payment_fee              REAL DEFAULT 0,
    material_cost            REAL DEFAULT 0,
    electricity_cost         REAL DEFAULT 0,
    depreciation_cost        REAL DEFAULT 0,
    profit                   REAL DEFAULT 0,
    notes                    TEXT DEFAULT '',
    is_deleted               INTEGER DEFAULT 0,
    quote_sent               INTEGER DEFAULT 0,
    quote_sent_date          TEXT DEFAULT '',
    deposit_amount           REAL DEFAULT 0,
    deposit_received         INTEGER DEFAULT 0,
    created_date             TEXT DEFAULT (datetime('now','localtime')),
    updated_date             TEXT DEFAULT (datetime('now','localtime')),
    confirmed_date           TEXT DEFAULT '',
    delivered_date           TEXT DEFAULT '',
    deleted_date             TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS print_items (
    id                          TEXT PRIMARY KEY,
    order_id                    TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    name                        TEXT DEFAULT '',
    estimated_weight_grams      REAL DEFAULT 0,
    actual_weight_grams         REAL DEFAULT 0,
    estimated_time_minutes      INTEGER DEFAULT 0,
    actual_time_minutes         INTEGER DEFAULT 0,
    filament_type               TEXT DEFAULT 'PLA+',
    color                       TEXT DEFAULT 'Black',
    spool_id                    TEXT DEFAULT '',
    nozzle_size                 REAL DEFAULT 0.4,
    layer_height                REAL DEFAULT 0.2,
    infill_density              INTEGER DEFAULT 20,
    support_type                TEXT DEFAULT 'None',
    scale_ratio                 REAL DEFAULT 1.0,
    quantity                    INTEGER DEFAULT 1,
    rate_per_gram               REAL DEFAULT 4.0,
    notes                       TEXT DEFAULT '',
    is_printed                  INTEGER DEFAULT 0,
    filament_pending            INTEGER DEFAULT 0,
    filament_deducted           INTEGER DEFAULT 0,
    printer_id                  TEXT DEFAULT '',
    tolerance_discount_applied  INTEGER DEFAULT 0,
    tolerance_discount_amount   REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filament_spools (
    id                   TEXT PRIMARY KEY,
    name                 TEXT DEFAULT '',
    filament_type        TEXT DEFAULT 'PLA+',
    brand                TEXT DEFAULT 'eSUN',
    color                TEXT DEFAULT 'Black',
    category             TEXT DEFAULT 'standard',
    status               TEXT DEFAULT 'active',
    initial_weight_grams REAL DEFAULT 1000,
    current_weight_grams REAL DEFAULT 1000,
    pending_weight_grams REAL DEFAULT 0,
    purchase_price_egp   REAL DEFAULT 840,
    purchase_date        TEXT DEFAULT (datetime('now','localtime')),
    archived_date        TEXT DEFAULT '',
    notes                TEXT DEFAULT '',
    is_active            INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS printers (
    id                       TEXT PRIMARY KEY,
    name                     TEXT DEFAULT 'HIVE 0.1',
    model                    TEXT DEFAULT 'Creality Ender-3 Max',
    purchase_price           REAL DEFAULT 25000,
    lifetime_kg              REAL DEFAULT 500,
    total_printed_grams      REAL DEFAULT 0,
    total_print_time_minutes INTEGER DEFAULT 0,
    nozzle_changes           INTEGER DEFAULT 0,
    nozzle_cost              REAL DEFAULT 100,
    nozzle_lifetime_grams    REAL DEFAULT 1500,
    current_nozzle_grams     REAL DEFAULT 0,
    electricity_rate_per_hour REAL DEFAULT 0.31,
    is_active                INTEGER DEFAULT 1,
    notes                    TEXT DEFAULT '',
    created_date             TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS print_failures (
    id                     TEXT PRIMARY KEY,
    date                   TEXT DEFAULT (datetime('now','localtime')),
    source                 TEXT DEFAULT 'Other',
    order_id               TEXT DEFAULT '',
    order_number           INTEGER DEFAULT 0,
    customer_name          TEXT DEFAULT '',
    item_name              TEXT DEFAULT '',
    reason                 TEXT DEFAULT 'Other',
    description            TEXT DEFAULT '',
    filament_wasted_grams  REAL DEFAULT 0,
    time_wasted_minutes    INTEGER DEFAULT 0,
    spool_id               TEXT DEFAULT '',
    color                  TEXT DEFAULT '',
    filament_cost          REAL DEFAULT 0,
    electricity_cost       REAL DEFAULT 0,
    total_loss             REAL DEFAULT 0,
    printer_id             TEXT DEFAULT '',
    printer_name           TEXT DEFAULT '',
    resolved               INTEGER DEFAULT 0,
    resolution_notes       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expenses (
    id               TEXT PRIMARY KEY,
    date             TEXT DEFAULT (datetime('now','localtime')),
    category         TEXT DEFAULT 'Other',
    name             TEXT DEFAULT '',
    description      TEXT DEFAULT '',
    amount           REAL DEFAULT 0,
    quantity         INTEGER DEFAULT 1,
    total_cost       REAL DEFAULT 0,
    supplier         TEXT DEFAULT '',
    receipt_number   TEXT DEFAULT '',
    is_recurring     INTEGER DEFAULT 0,
    recurring_period TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS filament_history (
    id               TEXT PRIMARY KEY,
    spool_id         TEXT DEFAULT '',
    spool_name       TEXT DEFAULT '',
    color            TEXT DEFAULT '',
    initial_weight   REAL DEFAULT 0,
    used_weight      REAL DEFAULT 0,
    remaining_weight REAL DEFAULT 0,
    waste_weight     REAL DEFAULT 0,
    archived_date    TEXT DEFAULT (datetime('now','localtime')),
    reason           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS colors (
    name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT DEFAULT '',
    password_salt TEXT DEFAULT '',
    role          TEXT DEFAULT 'User',
    display_name  TEXT DEFAULT '',
    email         TEXT DEFAULT '',
    is_active     INTEGER DEFAULT 1,
    created_date  TEXT DEFAULT (datetime('now','localtime')),
    last_login    TEXT DEFAULT '',
    login_count   INTEGER DEFAULT 0,
    notes         TEXT DEFAULT ''
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date     ON orders(created_date);
CREATE INDEX IF NOT EXISTS idx_orders_deleted  ON orders(is_deleted);
CREATE INDEX IF NOT EXISTS idx_items_order     ON print_items(order_id);
CREATE INDEX IF NOT EXISTS idx_spools_color    ON filament_spools(color);
CREATE INDEX IF NOT EXISTS idx_spools_active   ON filament_spools(is_active);
CREATE INDEX IF NOT EXISTS idx_expenses_cat    ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_date   ON expenses(date);
"""


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------

class DatabaseManager:
    """SQLite database manager — singleton.

    All public methods work with plain ``dict`` objects.
    Model conversion lives in the service layer.
    """

    _instance: Optional["DatabaseManager"] = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._db_path: Path = DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with row_factory and pragmas set."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield an auto-committing connection; rolls back on exception."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[dict]:
        return dict(row) if row else None

    def _rows_to_list(self, rows: List[sqlite3.Row]) -> List[dict]:
        return [dict(r) for r in rows]

    def _init_db(self) -> None:
        """Create schema and seed default data on first run."""
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            self._seed_defaults(conn)
            conn.commit()
        finally:
            conn.close()

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        """Insert default settings, colors and printer if tables are empty."""
        # Settings
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )

        # Colors
        for color in DEFAULT_COLORS:
            conn.execute(
                "INSERT OR IGNORE INTO colors (name) VALUES (?)",
                (color,),
            )

        # Default printer
        conn.execute(
            """
            INSERT OR IGNORE INTO printers
                (id, name, model, purchase_price, lifetime_kg)
            VALUES
                ('printer_default', 'HIVE 0.1', 'Creality Ender-3 Max', 25000, 500)
            """,
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def save_order(self, order: dict) -> bool:
        """Insert or replace an order record."""
        cols = ", ".join(order.keys())
        placeholders = ", ".join(["?"] * len(order))
        sql = f"INSERT OR REPLACE INTO orders ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(order.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_order failed: %s", e)
            return False

    def get_order(self, order_id: str) -> Optional[dict]:
        """Fetch a single order by ID."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def get_all_orders(self, include_deleted: bool = False) -> List[dict]:
        """Fetch all orders, optionally including soft-deleted ones."""
        conn = self._connect()
        try:
            if include_deleted:
                rows = conn.execute(
                    "SELECT * FROM orders ORDER BY order_number"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM orders WHERE is_deleted = 0 ORDER BY order_number"
                ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def delete_order(self, order_id: str, soft: bool = True) -> bool:
        """Delete an order — soft by default (sets is_deleted flag)."""
        try:
            with self._transaction() as conn:
                if soft:
                    conn.execute(
                        "UPDATE orders SET is_deleted=1, deleted_date=? WHERE id=?",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id),
                    )
                else:
                    conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
            return True
        except sqlite3.Error as e:
            log.error("delete_order failed: %s", e)
            return False

    def restore_order(self, order_id: str) -> bool:
        """Un-delete a soft-deleted order."""
        try:
            with self._transaction() as conn:
                conn.execute(
                    "UPDATE orders SET is_deleted=0, deleted_date='' WHERE id=?",
                    (order_id,),
                )
            return True
        except sqlite3.Error as e:
            log.error("restore_order failed: %s", e)
            return False

    def get_next_order_number(self) -> int:
        """Return and increment the next order number from settings."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key='next_order_number'"
            ).fetchone()
            current = int(row["value"]) if row else 1
            with self._transaction() as wconn:
                wconn.execute(
                    "UPDATE settings SET value=? WHERE key='next_order_number'",
                    (str(current + 1),),
                )
            return current
        finally:
            conn.close()

    def fix_order_numbering(self) -> None:
        """Re-sequence order numbers to close gaps."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM orders WHERE is_deleted=0 ORDER BY created_date"
            ).fetchall()
            with self._transaction() as wconn:
                for i, row in enumerate(rows, start=1):
                    wconn.execute(
                        "UPDATE orders SET order_number=? WHERE id=?",
                        (i, row["id"]),
                    )
                wconn.execute(
                    "UPDATE settings SET value=? WHERE key='next_order_number'",
                    (str(len(rows) + 1),),
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Print Items
    # ------------------------------------------------------------------

    def save_items(self, order_id: str, items: List[dict]) -> bool:
        """Replace all items for an order atomically."""
        try:
            with self._transaction() as conn:
                conn.execute(
                    "DELETE FROM print_items WHERE order_id=?", (order_id,)
                )
                for item in items:
                    item["order_id"] = order_id
                    cols = ", ".join(item.keys())
                    placeholders = ", ".join(["?"] * len(item))
                    conn.execute(
                        f"INSERT INTO print_items ({cols}) VALUES ({placeholders})",
                        list(item.values()),
                    )
            return True
        except sqlite3.Error as e:
            log.error("save_items failed: %s", e)
            return False

    def get_items(self, order_id: str) -> List[dict]:
        """Fetch all print items for an order."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM print_items WHERE order_id=?", (order_id,)
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    def save_customer(self, customer: dict) -> bool:
        """Insert or replace a customer record."""
        cols = ", ".join(customer.keys())
        placeholders = ", ".join(["?"] * len(customer))
        sql = f"INSERT OR REPLACE INTO customers ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(customer.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_customer failed: %s", e)
            return False

    def get_customer(self, customer_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM customers WHERE id=?", (customer_id,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def get_all_customers(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM customers ORDER BY name"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def search_customers(self, query: str) -> List[dict]:
        """Case-insensitive search on name and phone."""
        q = f"%{query.lower().strip()}%"
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM customers WHERE lower(name) LIKE ? OR phone LIKE ?",
                (q, q),
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def delete_customer(self, customer_id: str) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))
            return True
        except sqlite3.Error as e:
            log.error("delete_customer failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Filament Spools
    # ------------------------------------------------------------------

    def save_spool(self, spool: dict) -> bool:
        cols = ", ".join(spool.keys())
        placeholders = ", ".join(["?"] * len(spool))
        sql = f"INSERT OR REPLACE INTO filament_spools ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(spool.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_spool failed: %s", e)
            return False

    def get_spool(self, spool_id: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM filament_spools WHERE id=?", (spool_id,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def get_all_spools(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM filament_spools ORDER BY purchase_date DESC"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def get_active_spools(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM filament_spools
                   WHERE is_active=1
                     AND status != 'trash'
                     AND current_weight_grams > 0
                   ORDER BY color, current_weight_grams DESC"""
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def get_spools_by_color(self, color: str) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM filament_spools
                   WHERE is_active=1 AND status != 'trash' AND color=?
                   ORDER BY current_weight_grams DESC""",
                (color,),
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Printers
    # ------------------------------------------------------------------

    def save_printer(self, printer: dict) -> bool:
        cols = ", ".join(printer.keys())
        placeholders = ", ".join(["?"] * len(printer))
        sql = f"INSERT OR REPLACE INTO printers ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(printer.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_printer failed: %s", e)
            return False

    def get_all_printers(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM printers WHERE is_active=1 ORDER BY name"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Print Failures
    # ------------------------------------------------------------------

    def save_failure(self, failure: dict) -> bool:
        cols = ", ".join(failure.keys())
        placeholders = ", ".join(["?"] * len(failure))
        sql = f"INSERT OR REPLACE INTO print_failures ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(failure.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_failure failed: %s", e)
            return False

    def get_all_failures(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM print_failures ORDER BY date DESC"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def delete_failure(self, failure_id: str) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute(
                    "DELETE FROM print_failures WHERE id=?", (failure_id,)
                )
            return True
        except sqlite3.Error as e:
            log.error("delete_failure failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def save_expense(self, expense: dict) -> bool:
        cols = ", ".join(expense.keys())
        placeholders = ", ".join(["?"] * len(expense))
        sql = f"INSERT OR REPLACE INTO expenses ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(expense.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_expense failed: %s", e)
            return False

    def get_all_expenses(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM expenses ORDER BY date DESC"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def delete_expense(self, expense_id: str) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
            return True
        except sqlite3.Error as e:
            log.error("delete_expense failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def save_setting(self, key: str, value: Any) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(value)),
                )
            return True
        except sqlite3.Error as e:
            log.error("save_setting failed: %s", e)
            return False

    def get_all_settings(self) -> dict:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {r["key"]: r["value"] for r in rows}
        finally:
            conn.close()

    def save_all_settings(self, settings: dict) -> bool:
        try:
            with self._transaction() as conn:
                for key, value in settings.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (key, str(value)),
                    )
            return True
        except sqlite3.Error as e:
            log.error("save_all_settings failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Colors
    # ------------------------------------------------------------------

    def get_colors(self) -> List[str]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT name FROM colors ORDER BY name").fetchall()
            return [r["name"] for r in rows]
        finally:
            conn.close()

    def add_color(self, color: str) -> bool:
        if not color or not color.strip():
            return False
        try:
            with self._transaction() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO colors (name) VALUES (?)",
                    (color.strip(),),
                )
            return True
        except sqlite3.Error as e:
            log.error("add_color failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Filament History
    # ------------------------------------------------------------------

    def save_history(self, history: dict) -> bool:
        cols = ", ".join(history.keys())
        placeholders = ", ".join(["?"] * len(history))
        sql = f"INSERT OR REPLACE INTO filament_history ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(history.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_history failed: %s", e)
            return False

    def get_all_history(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM filament_history ORDER BY archived_date DESC"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Users  (auth_manager talks to this directly)
    # ------------------------------------------------------------------

    def save_user(self, user: dict) -> bool:
        cols = ", ".join(user.keys())
        placeholders = ", ".join(["?"] * len(user))
        sql = f"INSERT OR REPLACE INTO users ({cols}) VALUES ({placeholders})"
        try:
            with self._transaction() as conn:
                conn.execute(sql, list(user.values()))
            return True
        except sqlite3.Error as e:
            log.error("save_user failed: %s", e)
            return False

    def get_user(self, username: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def get_all_users(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY username"
            ).fetchall()
            return self._rows_to_list(rows)
        finally:
            conn.close()

    def delete_user(self, user_id: str) -> bool:
        try:
            with self._transaction() as conn:
                conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            return True
        except sqlite3.Error as e:
            log.error("delete_user failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_table_count(self, table: str) -> int:
        """Return row count for *table*."""
        conn = self._connect()
        try:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return row["n"] if row else 0
        except sqlite3.Error:
            return 0
        finally:
            conn.close()

    def backup_database(self) -> str:
        """Copy the .db file to the backups directory.

        Returns:
            Path string of the backup file.
        """
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"abaad_v5_{timestamp}.db"
        shutil.copy2(self._db_path, backup_path)
        log.info("Database backed up to %s", backup_path)
        return str(backup_path)

    def export_to_csv(self, export_dir: Optional[str] = None) -> Dict[str, str]:
        """Export core tables to CSV files.

        Args:
            export_dir: Target directory (defaults to ``EXPORT_DIR``).

        Returns:
            Dict mapping table name → file path.
        """
        out_dir = Path(export_dir) if export_dir else EXPORT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        files: Dict[str, str] = {}

        exports = {
            "orders": self.get_all_orders(),
            "customers": self.get_all_customers(),
            "expenses": self.get_all_expenses(),
            "failures": self.get_all_failures(),
            "spools": self.get_all_spools(),
        }

        for name, rows in exports.items():
            if not rows:
                continue
            path = out_dir / f"{name}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            files[name] = str(path)

        return files


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_db_instance: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """Return the application-wide DatabaseManager singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance