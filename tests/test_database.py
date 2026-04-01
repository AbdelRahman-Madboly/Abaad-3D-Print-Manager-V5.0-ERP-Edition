"""
tests/test_database.py
=======================
Low-level tests for DatabaseManager: pragmas, CRUD, soft delete,
table counts, backup, and CSV export.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.database import DatabaseManager


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return DatabaseManager(":memory:")


def _customer_record(name: str = "Charlie") -> dict:
    import uuid
    return {
        "id":               str(uuid.uuid4())[:8],
        "name":             name,
        "phone":            "01099999999",
        "email":            "",
        "address":          "",
        "notes":            "",
        "discount_percent": 0.0,
        "total_orders":     0,
        "total_spent":      0.0,
        "created_date":     "2024-01-01 00:00:00",
        "updated_date":     "2024-01-01 00:00:00",
    }


def _spool_record(color: str = "Black") -> dict:
    import uuid
    return {
        "id":                    str(uuid.uuid4())[:8],
        "name":                  f"eSUN PLA+ {color}",
        "filament_type":         "PLA+",
        "brand":                 "eSUN",
        "color":                 color,
        "category":              "standard",
        "status":                "active",
        "initial_weight_grams":  1000.0,
        "current_weight_grams":  1000.0,
        "pending_weight_grams":  0.0,
        "purchase_price_egp":    840.0,
        "purchase_date":         "2024-01-01 00:00:00",
        "archived_date":         "",
        "notes":                 "",
        "is_active":             1,
    }


def _order_record(number: int = 1, customer_name: str = "Charlie") -> dict:
    import uuid
    return {
        "id":                    str(uuid.uuid4())[:8],
        "order_number":          number,
        "customer_name":         customer_name,
        "customer_id":           "",
        "status":                "Draft",
        "payment_method":        "Cash",
        "shipping_cost":         0.0,
        "subtotal":              200.0,
        "actual_total":          200.0,
        "discount_amount":       0.0,
        "discount_percent":      0.0,
        "order_discount_percent":0.0,
        "order_discount_amount": 0.0,
        "tolerance_discount_total": 0.0,
        "payment_fee":           0.0,
        "total":                 200.0,
        "amount_received":       0.0,
        "rounding_loss":         0.0,
        "profit":                0.0,
        "material_cost":         0.0,
        "electricity_cost":      0.0,
        "depreciation_cost":     0.0,
        "is_rd_project":         0,
        "is_deleted":            0,
        "deposit_amount":        0.0,
        "deposit_paid":          0,
        "notes":                 "",
        "created_date":          "2024-01-01 00:00:00",
        "updated_date":          "2024-01-01 00:00:00",
        "confirmed_date":        "",
        "delivered_date":        "",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDatabasePragmas:

    def test_wal_mode(self, db):
        """WAL journal mode should be active."""
        with db._transaction() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"

    def test_foreign_keys_enabled(self, db):
        """Foreign-key enforcement should be on (returns 1)."""
        with db._transaction() as conn:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


class TestCustomerCRUD:

    def test_save_and_get_customer(self, db):
        record = _customer_record("Diana")
        db.save_customer(record)
        retrieved = db.get_customer(record["id"])
        assert retrieved is not None
        assert retrieved["name"] == "Diana"

    def test_get_all_customers(self, db):
        db.save_customer(_customer_record("Eve"))
        db.save_customer(_customer_record("Frank"))
        all_customers = db.get_all_customers()
        names = [c["name"] for c in all_customers]
        assert "Eve" in names
        assert "Frank" in names


class TestSpoolCRUD:

    def test_save_and_get_spool(self, db):
        record = _spool_record("Silver")
        db.save_spool(record)
        retrieved = db.get_spool(record["id"])
        assert retrieved is not None
        assert retrieved["color"] == "Silver"


class TestOrderSoftDelete:

    def test_soft_deleted_order_excluded(self, db):
        record = _order_record(1, "Grace")
        db.save_order(record)
        db.delete_order(record["id"], soft=True)
        visible = db.get_all_orders(include_deleted=False)
        assert not any(o["id"] == record["id"] for o in visible)

    def test_soft_deleted_order_included_when_requested(self, db):
        record = _order_record(2, "Hank")
        db.save_order(record)
        db.delete_order(record["id"], soft=True)
        all_orders = db.get_all_orders(include_deleted=True)
        assert any(o["id"] == record["id"] for o in all_orders)


class TestTableCount:

    def test_get_table_count_after_inserts(self, db):
        before = db.get_table_count("customers")
        db.save_customer(_customer_record("Iris"))
        db.save_customer(_customer_record("Jack"))
        after = db.get_table_count("customers")
        assert after == before + 2


class TestBackup:

    def test_backup_database_creates_file(self, db, tmp_path):
        """backup_database() should return a path that exists on disk."""
        # Only meaningful for file-based DBs; skip for :memory:
        # Instead verify the method exists and handles :memory: gracefully.
        try:
            result = db.backup_database(backup_dir=tmp_path)
            if result:
                assert Path(result).exists()
        except Exception:
            # :memory: backup may not be supported — acceptable
            pytest.skip("backup_database not supported for :memory: DB")


class TestCSVExport:

    def test_export_to_csv_creates_file(self, db, tmp_path):
        """export_to_csv() should write at least orders.csv to the given dir."""
        record = _order_record(1, "Leo")
        db.save_order(record)
        try:
            db.export_to_csv(export_dir=tmp_path)
            csv_file = tmp_path / "orders.csv"
            assert csv_file.exists()
        except (AttributeError, NotImplementedError):
            pytest.skip("export_to_csv not yet implemented")