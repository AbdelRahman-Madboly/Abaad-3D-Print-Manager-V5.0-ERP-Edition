"""
scripts/migrate_v4_to_v5.py
============================
Migrate Abaad v4 JSON flat-file databases to v5 SQLite.

Reads:
  data/abaad_v4.db.json   — main database (orders, customers, spools, …)
  data/users.json          — user accounts

Writes:
  data/abaad_v5.db         — SQLite (via src/core/database.py)

Run once:
    python scripts/migrate_v4_to_v5.py

Safe to re-run:  uses INSERT OR IGNORE so existing records are never
overwritten; run with --force to replace everything.

Exit codes:
    0  success
    1  source file(s) not found
    2  validation mismatch (row counts differ)
    3  unexpected error
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running as a standalone script from project root
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.core.config import OLD_JSON_DB, OLD_USERS_JSON, ensure_directories
from src.core.database import get_database

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
log = logging.getLogger("migrate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bool_to_int(value: Any) -> int:
    """Convert JSON bool/int/string to SQLite integer (0 or 1)."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value else 0
    if isinstance(value, str):
        return 1 if value.lower() in ("true", "1", "yes") else 0
    return 0


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Table migrators
# ---------------------------------------------------------------------------

def migrate_customers(data: dict, db, force: bool) -> int:
    """Migrate customers dict → SQLite customers table."""
    customers = data.get("customers", {})
    count = 0
    for raw in customers.values():
        record = {
            "id":               _str(raw.get("id")),
            "name":             _str(raw.get("name")),
            "phone":            _str(raw.get("phone")),
            "email":            _str(raw.get("email")),
            "address":          _str(raw.get("address")),
            "notes":            _str(raw.get("notes")),
            "discount_percent": _float(raw.get("discount_percent")),
            "total_orders":     _int(raw.get("total_orders")),
            "total_spent":      _float(raw.get("total_spent")),
            "created_date":     _str(raw.get("created_date"), _now()),
            "updated_date":     _str(raw.get("updated_date"), _now()),
        }
        if not record["id"]:
            log.warning("Skipping customer with no id: %s", raw)
            continue
        if force:
            db.save_customer(record)
        else:
            _insert_ignore(db, "customers", record)
        count += 1
    return count


def migrate_orders_and_items(data: dict, db, force: bool) -> tuple[int, int]:
    """Migrate orders (and their nested items) to SQLite."""
    all_orders = {}
    # Live orders
    for oid, raw in data.get("orders", {}).items():
        all_orders[oid] = (raw, False)
    # Deleted orders
    for oid, raw in data.get("deleted_orders", {}).items():
        all_orders[oid] = (raw, True)

    order_count = 0
    item_count  = 0

    for raw, was_deleted in all_orders.values():
        # --- Order record ---
        order = {
            "id":                       _str(raw.get("id")),
            "order_number":             _int(raw.get("order_number")),
            "customer_id":              _str(raw.get("customer_id")),
            "customer_name":            _str(raw.get("customer_name")),
            "customer_phone":           _str(raw.get("customer_phone")),
            "status":                   _str(raw.get("status"), "Draft"),
            "is_rd_project":            _bool_to_int(raw.get("is_rd_project", False)),
            "subtotal":                 _float(raw.get("subtotal")),
            "actual_total":             _float(raw.get("actual_total")),
            "discount_percent":         _float(raw.get("discount_percent")),
            "discount_amount":          _float(raw.get("discount_amount")),
            "order_discount_percent":   _float(raw.get("order_discount_percent")),
            "order_discount_amount":    _float(raw.get("order_discount_amount")),
            "tolerance_discount_total": _float(raw.get("tolerance_discount_total")),
            "shipping_cost":            _float(raw.get("shipping_cost")),
            "total":                    _float(raw.get("total")),
            "amount_received":          _float(raw.get("amount_received")),
            "rounding_loss":            _float(raw.get("rounding_loss")),
            "payment_method":           _str(raw.get("payment_method"), "Cash"),
            "payment_fee":              _float(raw.get("payment_fee")),
            "material_cost":            _float(raw.get("material_cost")),
            "electricity_cost":         _float(raw.get("electricity_cost")),
            "depreciation_cost":        _float(raw.get("depreciation_cost")),
            "profit":                   _float(raw.get("profit")),
            "notes":                    _str(raw.get("notes")),
            "is_deleted":               1 if was_deleted else _bool_to_int(raw.get("is_deleted", False)),
            "quote_sent":               _bool_to_int(raw.get("quote_sent", False)),
            "quote_sent_date":          _str(raw.get("quote_sent_date")),
            "deposit_amount":           _float(raw.get("deposit_amount")),
            "deposit_received":         _bool_to_int(raw.get("deposit_received", False)),
            "created_date":             _str(raw.get("created_date"), _now()),
            "updated_date":             _str(raw.get("updated_date"), _now()),
            "confirmed_date":           _str(raw.get("confirmed_date")),
            "delivered_date":           _str(raw.get("delivered_date")),
            "deleted_date":             _str(raw.get("deleted_date")),
        }

        if not order["id"]:
            log.warning("Skipping order with no id")
            continue

        if force:
            db.save_order(order)
        else:
            _insert_ignore(db, "orders", order)
        order_count += 1

        # --- Items (nested list in v4) ---
        # v4 stores items inside the order dict under key "items"
        items_raw: List[dict] = raw.get("items", [])
        items: List[dict] = []
        for iraw in items_raw:
            # Flatten the nested "settings" sub-dict into top-level columns
            settings = iraw.get("settings", {})
            item = {
                "id":                         _str(iraw.get("id")),
                "order_id":                   order["id"],
                "name":                       _str(iraw.get("name")),
                "estimated_weight_grams":     _float(iraw.get("estimated_weight_grams")),
                "actual_weight_grams":        _float(iraw.get("actual_weight_grams")),
                "estimated_time_minutes":     _int(iraw.get("estimated_time_minutes")),
                "actual_time_minutes":        _int(iraw.get("actual_time_minutes")),
                "filament_type":              _str(iraw.get("filament_type"), "PLA+"),
                "color":                      _str(iraw.get("color"), "Black"),
                "spool_id":                   _str(iraw.get("spool_id")),
                # Flattened from settings sub-dict
                "nozzle_size":                _float(settings.get("nozzle_size", iraw.get("nozzle_size", 0.4))),
                "layer_height":               _float(settings.get("layer_height", iraw.get("layer_height", 0.2))),
                "infill_density":             _int(settings.get("infill_density", iraw.get("infill_density", 20))),
                "support_type":               _str(settings.get("support_type", iraw.get("support_type", "None"))),
                "scale_ratio":                _float(settings.get("scale_ratio", iraw.get("scale_ratio", 1.0))),
                "quantity":                   _int(iraw.get("quantity"), 1),
                "rate_per_gram":              _float(iraw.get("rate_per_gram"), 4.0),
                "notes":                      _str(iraw.get("notes")),
                "is_printed":                 _bool_to_int(iraw.get("is_printed", False)),
                "filament_pending":           _bool_to_int(iraw.get("filament_pending", False)),
                "filament_deducted":          _bool_to_int(iraw.get("filament_deducted", False)),
                "printer_id":                 _str(iraw.get("printer_id")),
                "tolerance_discount_applied": _bool_to_int(iraw.get("tolerance_discount_applied", False)),
                "tolerance_discount_amount":  _float(iraw.get("tolerance_discount_amount")),
            }
            if not item["id"]:
                log.warning("Skipping item with no id in order %s", order["id"])
                continue
            items.append(item)

        if items:
            if force:
                db.save_items(order["id"], items)
            else:
                for item in items:
                    _insert_ignore(db, "print_items", item)
            item_count += len(items)

    return order_count, item_count


def migrate_spools(data: dict, db, force: bool) -> int:
    spools = data.get("spools", {})
    count  = 0
    for raw in spools.values():
        record = {
            "id":                   _str(raw.get("id")),
            "name":                 _str(raw.get("name")),
            "filament_type":        _str(raw.get("filament_type"), "PLA+"),
            "brand":                _str(raw.get("brand"), "eSUN"),
            "color":                _str(raw.get("color"), "Black"),
            "category":             _str(raw.get("category"), "standard"),
            "status":               _str(raw.get("status"), "active"),
            "initial_weight_grams": _float(raw.get("initial_weight_grams"), 1000.0),
            "current_weight_grams": _float(raw.get("current_weight_grams"), 1000.0),
            "pending_weight_grams": _float(raw.get("pending_weight_grams")),
            "purchase_price_egp":   _float(raw.get("purchase_price_egp"), 840.0),
            "purchase_date":        _str(raw.get("purchase_date"), _now()),
            "archived_date":        _str(raw.get("archived_date")),
            "notes":                _str(raw.get("notes")),
            "is_active":            _bool_to_int(raw.get("is_active", True)),
        }
        if not record["id"]:
            log.warning("Skipping spool with no id")
            continue
        if force:
            db.save_spool(record)
        else:
            _insert_ignore(db, "filament_spools", record)
        count += 1
    return count


def migrate_printers(data: dict, db, force: bool) -> int:
    printers = data.get("printers", {})
    count    = 0
    for raw in printers.values():
        record = {
            "id":                        _str(raw.get("id")),
            "name":                      _str(raw.get("name"), "HIVE 0.1"),
            "model":                     _str(raw.get("model"), "Creality Ender-3 Max"),
            "purchase_price":            _float(raw.get("purchase_price"), 25000.0),
            "lifetime_kg":               _float(raw.get("lifetime_kg"), 500.0),
            "total_printed_grams":       _float(raw.get("total_printed_grams")),
            "total_print_time_minutes":  _int(raw.get("total_print_time_minutes")),
            "nozzle_changes":            _int(raw.get("nozzle_changes")),
            "nozzle_cost":               _float(raw.get("nozzle_cost"), 100.0),
            "nozzle_lifetime_grams":     _float(raw.get("nozzle_lifetime_grams"), 1500.0),
            "current_nozzle_grams":      _float(raw.get("current_nozzle_grams")),
            "electricity_rate_per_hour": _float(raw.get("electricity_rate_per_hour"), 0.31),
            "is_active":                 _bool_to_int(raw.get("is_active", True)),
            "notes":                     _str(raw.get("notes")),
            "created_date":              _str(raw.get("created_date"), _now()),
        }
        if not record["id"]:
            log.warning("Skipping printer with no id")
            continue
        if force:
            db.save_printer(record)
        else:
            _insert_ignore(db, "printers", record)
        count += 1
    return count


def migrate_failures(data: dict, db, force: bool) -> int:
    failures = data.get("failures", {})
    count    = 0
    for raw in failures.values():
        record = {
            "id":                    _str(raw.get("id")),
            "date":                  _str(raw.get("date"), _now()),
            "source":                _str(raw.get("source"), "Other"),
            "order_id":              _str(raw.get("order_id")),
            "order_number":          _int(raw.get("order_number")),
            "customer_name":         _str(raw.get("customer_name")),
            "item_name":             _str(raw.get("item_name")),
            "reason":                _str(raw.get("reason"), "Other"),
            "description":           _str(raw.get("description")),
            "filament_wasted_grams": _float(raw.get("filament_wasted_grams")),
            "time_wasted_minutes":   _int(raw.get("time_wasted_minutes")),
            "spool_id":              _str(raw.get("spool_id")),
            "color":                 _str(raw.get("color")),
            "filament_cost":         _float(raw.get("filament_cost")),
            "electricity_cost":      _float(raw.get("electricity_cost")),
            "total_loss":            _float(raw.get("total_loss")),
            "printer_id":            _str(raw.get("printer_id")),
            "printer_name":          _str(raw.get("printer_name")),
            "resolved":              _bool_to_int(raw.get("resolved", False)),
            "resolution_notes":      _str(raw.get("resolution_notes")),
        }
        if not record["id"]:
            log.warning("Skipping failure with no id")
            continue
        if force:
            db.save_failure(record)
        else:
            _insert_ignore(db, "print_failures", record)
        count += 1
    return count


def migrate_expenses(data: dict, db, force: bool) -> int:
    expenses = data.get("expenses", {})
    count    = 0
    for raw in expenses.values():
        record = {
            "id":               _str(raw.get("id")),
            "date":             _str(raw.get("date"), _now()),
            "category":         _str(raw.get("category"), "Other"),
            "name":             _str(raw.get("name")),
            "description":      _str(raw.get("description")),
            "amount":           _float(raw.get("amount")),
            "quantity":         _int(raw.get("quantity"), 1),
            "total_cost":       _float(raw.get("total_cost")),
            "supplier":         _str(raw.get("supplier")),
            "receipt_number":   _str(raw.get("receipt_number")),
            "is_recurring":     _bool_to_int(raw.get("is_recurring", False)),
            "recurring_period": _str(raw.get("recurring_period")),
        }
        if not record["id"]:
            log.warning("Skipping expense with no id")
            continue
        if force:
            db.save_expense(record)
        else:
            _insert_ignore(db, "expenses", record)
        count += 1
    return count


def migrate_filament_history(data: dict, db, force: bool) -> int:
    history = data.get("filament_history", {})
    count   = 0
    for raw in history.values():
        record = {
            "id":               _str(raw.get("id")),
            "spool_id":         _str(raw.get("spool_id")),
            "spool_name":       _str(raw.get("spool_name")),
            "color":            _str(raw.get("color")),
            "initial_weight":   _float(raw.get("initial_weight")),
            "used_weight":      _float(raw.get("used_weight")),
            "remaining_weight": _float(raw.get("remaining_weight")),
            "waste_weight":     _float(raw.get("waste_weight")),
            "archived_date":    _str(raw.get("archived_date"), _now()),
            "reason":           _str(raw.get("reason")),
        }
        if not record["id"]:
            log.warning("Skipping history entry with no id")
            continue
        if force:
            db.save_history(record)
        else:
            _insert_ignore(db, "filament_history", record)
        count += 1
    return count


def migrate_colors(data: dict, db) -> int:
    colors = data.get("colors", [])
    count  = 0
    for color in colors:
        if color and isinstance(color, str):
            db.add_color(color)
            count += 1
    return count


def migrate_settings(data: dict, db) -> int:
    settings = data.get("settings", {})
    count    = 0
    for key, value in settings.items():
        db.save_setting(key, str(value))
        count += 1
    return count


def migrate_users(users_data: dict, db, force: bool) -> int:
    users = users_data.get("users", [])
    count = 0
    for raw in users:
        record = {
            "id":            _str(raw.get("id")),
            "username":      _str(raw.get("username")),
            "password_hash": _str(raw.get("password_hash")),
            "password_salt": _str(raw.get("password_salt")),
            "role":          _str(raw.get("role"), "User"),
            "display_name":  _str(raw.get("display_name")),
            "email":         _str(raw.get("email")),
            "is_active":     _bool_to_int(raw.get("is_active", True)),
            "created_date":  _str(raw.get("created_date"), _now()),
            "last_login":    _str(raw.get("last_login")),
            "login_count":   _int(raw.get("login_count")),
            "notes":         _str(raw.get("notes")),
        }
        if not record["id"] or not record["username"]:
            log.warning("Skipping user with missing id/username: %s", raw)
            continue
        if force:
            db.save_user(record)
        else:
            _insert_ignore(db, "users", record)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Direct SQL insert-or-ignore (bypasses the service-layer upsert)
# ---------------------------------------------------------------------------

def _insert_ignore(db, table: str, record: dict) -> None:
    """INSERT OR IGNORE — skips record if primary key already exists."""
    cols         = ", ".join(record.keys())
    placeholders = ", ".join(["?"] * len(record))
    sql          = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    with db._transaction() as conn:
        conn.execute(sql, list(record.values()))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(db, v4_data: dict, v4_users: dict) -> bool:
    """Compare row counts between source JSON and migrated SQLite."""
    ok = True

    checks = [
        ("customers",       len(v4_data.get("customers", {})),       db.get_table_count("customers")),
        ("orders",          len(v4_data.get("orders", {}))
                          + len(v4_data.get("deleted_orders", {})),   db.get_table_count("orders")),
        ("filament_spools", len(v4_data.get("spools", {})),           db.get_table_count("filament_spools")),
        ("printers",        len(v4_data.get("printers", {})),         db.get_table_count("printers")),
        ("print_failures",  len(v4_data.get("failures", {})),         db.get_table_count("print_failures")),
        ("expenses",        len(v4_data.get("expenses", {})),         db.get_table_count("expenses")),
        ("users",           len(v4_users.get("users", [])),           db.get_table_count("users")),
    ]

    log.info("")
    log.info("── Validation ──────────────────────────────────────")
    log.info("  %-20s  %6s  %6s  %s", "Table", "JSON", "SQLite", "Status")
    log.info("  " + "-" * 50)
    for table, expected, actual in checks:
        status = "✓" if actual >= expected else "✗ MISMATCH"
        if actual < expected:
            ok = False
        log.info("  %-20s  %6d  %6d  %s", table, expected, actual, status)
    log.info("────────────────────────────────────────────────────")

    return ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(force: bool = False) -> int:
    """Execute the migration. Returns an exit code."""
    ensure_directories()

    # --- Load source files ---
    if not OLD_JSON_DB.exists():
        log.error("v4 database not found: %s", OLD_JSON_DB)
        log.error("Place abaad_v4.db.json in the data/ directory and retry.")
        return 1

    with open(OLD_JSON_DB, encoding="utf-8") as f:
        v4_data: dict = json.load(f)

    v4_users: dict = {"users": []}
    if OLD_USERS_JSON.exists():
        with open(OLD_USERS_JSON, encoding="utf-8") as f:
            v4_users = json.load(f)
    else:
        log.warning("users.json not found — no users will be migrated")

    db = get_database()

    log.info("Starting migration  v4 JSON → v5 SQLite")
    log.info("Source:  %s", OLD_JSON_DB)
    log.info("Target:  %s", db._db_path)
    log.info("Mode:    %s", "FORCE (overwrite)" if force else "safe (skip existing)")
    log.info("")

    # --- Migrate each section ---
    n_customers = migrate_customers(v4_data, db, force)
    log.info("Customers        : %d", n_customers)

    n_orders, n_items = migrate_orders_and_items(v4_data, db, force)
    log.info("Orders           : %d  (items: %d)", n_orders, n_items)

    n_spools = migrate_spools(v4_data, db, force)
    log.info("Filament spools  : %d", n_spools)

    n_printers = migrate_printers(v4_data, db, force)
    log.info("Printers         : %d", n_printers)

    n_failures = migrate_failures(v4_data, db, force)
    log.info("Print failures   : %d", n_failures)

    n_expenses = migrate_expenses(v4_data, db, force)
    log.info("Expenses         : %d", n_expenses)

    n_history = migrate_filament_history(v4_data, db, force)
    log.info("Filament history : %d", n_history)

    n_colors = migrate_colors(v4_data, db)
    log.info("Colors           : %d", n_colors)

    n_settings = migrate_settings(v4_data, db)
    log.info("Settings         : %d", n_settings)

    n_users = migrate_users(v4_users, db, force)
    log.info("Users            : %d", n_users)

    # --- Validate ---
    ok = _validate(db, v4_data, v4_users)

    if ok:
        log.info("")
        log.info("✓ Migration complete — all counts match.")
        return 0
    else:
        log.error("")
        log.error("✗ Validation failed — row count mismatch. Check warnings above.")
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate Abaad v4 JSON → v5 SQLite"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing records (default: skip on conflict)",
    )
    args = parser.parse_args()

    try:
        sys.exit(run(force=args.force))
    except Exception as exc:
        log.exception("Unexpected error during migration: %s", exc)
        sys.exit(3)