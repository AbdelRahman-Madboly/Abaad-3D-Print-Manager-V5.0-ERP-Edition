"""
tests/test_migration.py
========================
Tests for the v4 JSON → v5 SQLite migration script.

Uses tmp_path to write a minimal v4 JSON fixture to disk, then
runs the migration against a fresh in-memory (or temp-file) SQLite DB.
"""

import json
import sys
import pytest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Minimal v4 fixture factory
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _make_v4_data() -> dict:
    """Build a minimal but structurally correct v4 JSON data dict."""
    return {
        "orders": {
            "ord1": {
                "id":             "ord1",
                "order_number":   1,
                "customer_name":  "Alice",
                "customer_id":    "cus1",
                "status":         "Delivered",
                "payment_method": "Cash",
                "shipping_cost":  0.0,
                "subtotal":       200.0,
                "actual_total":   200.0,
                "discount_amount": 0.0,
                "discount_percent": 0.0,
                "order_discount_percent": 0.0,
                "order_discount_amount":  0.0,
                "tolerance_discount_total": 0.0,
                "payment_fee":    0.0,
                "total":          200.0,
                "amount_received": 200.0,
                "rounding_loss":  0.0,
                "profit":         116.0,
                "material_cost":  42.0,
                "electricity_cost": 0.31,
                "depreciation_cost": 1.0,
                "is_rd_project":  False,
                "is_deleted":     False,
                "deposit_amount": 0.0,
                "deposit_paid":   False,
                "notes":          "",
                "created_date":   _now(),
                "updated_date":   _now(),
                "confirmed_date": "",
                "delivered_date": _now(),
                "items":          [],
            },
            "ord2": {
                "id":             "ord2",
                "order_number":   2,
                "customer_name":  "Bob",
                "customer_id":    "cus2",
                "status":         "Draft",
                "payment_method": "Cash",
                "shipping_cost":  0.0,
                "subtotal":       80.0,
                "actual_total":   80.0,
                "discount_amount": 0.0,
                "discount_percent": 0.0,
                "order_discount_percent": 0.0,
                "order_discount_amount":  0.0,
                "tolerance_discount_total": 0.0,
                "payment_fee":    0.0,
                "total":          80.0,
                "amount_received": 0.0,
                "rounding_loss":  0.0,
                "profit":         0.0,
                "material_cost":  0.0,
                "electricity_cost": 0.0,
                "depreciation_cost": 0.0,
                "is_rd_project":  False,
                "is_deleted":     False,
                "deposit_amount": 0.0,
                "deposit_paid":   False,
                "notes":          "",
                "created_date":   _now(),
                "updated_date":   _now(),
                "confirmed_date": "",
                "delivered_date": "",
                "items":          [],
            },
        },
        "deleted_orders": {},
        "customers": {
            "cus1": {
                "id":               "cus1",
                "name":             "Alice",
                "phone":            "01000000001",
                "email":            "",
                "address":          "",
                "notes":            "",
                "discount_percent": 0.0,
                "total_orders":     1,
                "total_spent":      200.0,
                "created_date":     _now(),
                "updated_date":     _now(),
            },
            "cus2": {
                "id":               "cus2",
                "name":             "Bob",
                "phone":            "01000000002",
                "email":            "",
                "address":          "",
                "notes":            "",
                "discount_percent": 0.0,
                "total_orders":     1,
                "total_spent":      80.0,
                "created_date":     _now(),
                "updated_date":     _now(),
            },
        },
        "spools": {
            "sp1": {
                "id":                   "sp1",
                "name":                 "eSUN PLA+ Black",
                "filament_type":        "PLA+",
                "brand":                "eSUN",
                "color":                "Black",
                "category":             "standard",
                "status":               "active",
                "initial_weight_grams": 1000.0,
                "current_weight_grams": 750.0,
                "pending_weight_grams": 0.0,
                "purchase_price_egp":   840.0,
                "purchase_date":        _now(),
                "archived_date":        "",
                "notes":                "",
                "is_active":            True,
            },
            "sp2": {
                "id":                   "sp2",
                "name":                 "eSUN PLA+ White",
                "filament_type":        "PLA+",
                "brand":                "eSUN",
                "color":                "White",
                "category":             "remaining",
                "status":               "active",
                "initial_weight_grams": 300.0,
                "current_weight_grams": 300.0,
                "pending_weight_grams": 0.0,
                "purchase_price_egp":   0.0,
                "purchase_date":        _now(),
                "archived_date":        "",
                "notes":                "",
                "is_active":            True,
            },
        },
        "printers": {
            "pr1": {
                "id":                        "pr1",
                "name":                      "HIVE 0.1",
                "model":                     "Creality Ender-3 Max",
                "purchase_price":            25000.0,
                "lifetime_kg":               500.0,
                "total_printed_grams":       250000.0,
                "total_print_time_minutes":  90000,
                "nozzle_changes":            5,
                "nozzle_cost":               100.0,
                "nozzle_lifetime_grams":     1500.0,
                "current_nozzle_grams":      300.0,
                "electricity_rate_per_hour": 0.31,
                "is_active":                 True,
                "notes":                     "",
                "created_date":              _now(),
            },
        },
        "failures": {
            "fl1": {
                "id":                    "fl1",
                "date":                  _now(),
                "source":                "Customer Order",
                "order_id":              "ord1",
                "order_number":          1,
                "customer_name":         "Alice",
                "item_name":             "Bracket",
                "reason":                "Nozzle Clog",
                "description":           "",
                "filament_wasted_grams": 15.0,
                "time_wasted_minutes":   45,
                "spool_id":              "sp1",
                "color":                 "Black",
                "filament_cost":         12.6,
                "electricity_cost":      0.23,
                "total_loss":            12.83,
                "printer_id":            "pr1",
                "printer_name":          "HIVE 0.1",
                "resolved":              True,
                "resolution_notes":      "Replaced nozzle",
            },
        },
        "expenses": {
            "ex1": {
                "id":               "ex1",
                "date":             _now(),
                "category":         "Tools",
                "name":             "Nozzle pack",
                "description":      "0.4 mm brass nozzles",
                "amount":           200.0,
                "quantity":         1,
                "total_cost":       200.0,
                "supplier":         "",
                "receipt_number":   "",
                "is_recurring":     False,
                "recurring_period": "",
            },
        },
        "filament_history": {},
        "colors": ["Black", "White", "Red"],
        "settings": {
            "company_name":          "Abaad",
            "default_rate_per_gram": "4.0",
            "next_order_number":     "3",
        },
    }


def _make_v4_users() -> dict:
    return {"users": []}


# ---------------------------------------------------------------------------
# Helper: run migration against a fresh temp DB
# ---------------------------------------------------------------------------

def _run_migration(v4_json_path: Path, db_path: Path, force: bool = False) -> int:
    """
    Invoke the migration ``run()`` function with patched config paths.
    Returns the exit code (0 = success, 2 = count mismatch, …).
    """
    import importlib
    import src.core.config as cfg

    # Temporarily patch the paths the migration reads
    original_json_db    = cfg.OLD_JSON_DB
    original_users_json = cfg.OLD_USERS_JSON
    original_db_path    = cfg.DB_PATH

    cfg.OLD_JSON_DB    = v4_json_path
    cfg.OLD_USERS_JSON = v4_json_path.parent / "users.json"
    cfg.DB_PATH        = db_path

    # Re-import database so get_database() sees the new path
    import src.core.database as dbmod
    dbmod._db_instance = None   # reset singleton if present

    try:
        from scripts.migrate_v4_to_v5 import run as migration_run
        return migration_run(force=force)
    finally:
        cfg.OLD_JSON_DB    = original_json_db
        cfg.OLD_USERS_JSON = original_users_json
        cfg.DB_PATH        = original_db_path
        dbmod._db_instance = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMigration:

    @pytest.fixture
    def v4_fixture(self, tmp_path) -> Path:
        """Write the minimal v4 JSON to a temp file and return its path."""
        json_path = tmp_path / "abaad_v4.db.json"
        json_path.write_text(json.dumps(_make_v4_data()), encoding="utf-8")
        # Write empty users file
        (tmp_path / "users.json").write_text(
            json.dumps(_make_v4_users()), encoding="utf-8"
        )
        return json_path

    @pytest.fixture
    def migrated_db(self, v4_fixture, tmp_path):
        """Run migration once and return the DatabaseManager."""
        db_path = tmp_path / "abaad_v5.db"
        _run_migration(v4_fixture, db_path, force=False)
        from src.core.database import DatabaseManager
        return DatabaseManager(str(db_path))

    # ------------------------------------------------------------------

    def test_all_counts_match(self, migrated_db):
        db = migrated_db
        assert db.get_table_count("orders")         == 2
        assert db.get_table_count("customers")      == 2
        assert db.get_table_count("filament_spools") == 2
        assert db.get_table_count("printers")       == 1
        assert db.get_table_count("print_failures") == 1
        assert db.get_table_count("expenses")       == 1

    def test_key_fields_preserved_orders(self, migrated_db):
        db = migrated_db
        orders = db.get_all_orders(include_deleted=True)
        order_numbers = {o["order_number"] for o in orders}
        assert 1 in order_numbers
        assert 2 in order_numbers

    def test_key_fields_preserved_customers(self, migrated_db):
        db = migrated_db
        customers = db.get_all_customers()
        names = {c["name"] for c in customers}
        assert "Alice" in names
        assert "Bob" in names

    def test_key_fields_preserved_spools(self, migrated_db):
        db = migrated_db
        spools = db.get_all_spools()
        colors = {s["color"] for s in spools}
        assert "Black" in colors
        assert "White" in colors

    def test_key_fields_preserved_printer(self, migrated_db):
        db = migrated_db
        printers = db.get_all_printers()
        names = {p["name"] for p in printers}
        assert "HIVE 0.1" in names

    def test_no_duplicates_on_second_run(self, v4_fixture, tmp_path):
        """Running migration twice without --force must not duplicate records."""
        db_path = tmp_path / "abaad_v5.db"
        _run_migration(v4_fixture, db_path, force=False)
        _run_migration(v4_fixture, db_path, force=False)
        from src.core.database import DatabaseManager
        db = DatabaseManager(str(db_path))
        assert db.get_table_count("orders")    == 2
        assert db.get_table_count("customers") == 2

    def test_force_flag_succeeds(self, v4_fixture, tmp_path):
        """Migration with --force should complete successfully (exit code 0)."""
        db_path = tmp_path / "abaad_v5_force.db"
        exit_code = _run_migration(v4_fixture, db_path, force=True)
        assert exit_code == 0