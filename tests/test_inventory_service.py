"""
tests/test_inventory_service.py
================================
Integration tests for InventoryService against an in-memory SQLite database.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.database import DatabaseManager
from src.services.inventory_service import InventoryService
from src.core.config import SPOOL_PRICE_FIXED, TRASH_THRESHOLD_GRAMS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return DatabaseManager(":memory:")


@pytest.fixture
def svc(db):
    return InventoryService(db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInventoryService:

    def test_add_standard_spool(self, svc):
        """Standard spool: 1000 g, cost = SPOOL_PRICE_FIXED / 1000."""
        spool = svc.add_spool(
            color="Black",
            category="standard",
            initial_weight_grams=1000.0,
            purchase_price_egp=SPOOL_PRICE_FIXED,
        )
        assert spool.current_weight_grams  == pytest.approx(1000.0)
        assert spool.initial_weight_grams  == pytest.approx(1000.0)
        assert spool.cost_per_gram         == pytest.approx(SPOOL_PRICE_FIXED / 1000.0)

    def test_add_remaining_spool_zero_cost(self, svc):
        """Remaining spool: cost_per_gram = 0 (already paid)."""
        spool = svc.add_spool(
            color="White",
            category="remaining",
            initial_weight_grams=300.0,
            purchase_price_egp=0.0,
        )
        assert spool.cost_per_gram == pytest.approx(0.0)

    def test_reserve_filament(self, svc):
        spool = svc.add_spool(color="Black", initial_weight_grams=1000.0)
        ok = svc.reserve_filament(spool.id, 50.0)
        assert ok is True
        refreshed = svc.get_spool(spool.id)
        assert refreshed.pending_weight_grams   == pytest.approx(50.0)
        assert refreshed.available_weight_grams == pytest.approx(950.0)
        assert refreshed.current_weight_grams   == pytest.approx(1000.0)

    def test_release_filament(self, svc):
        spool = svc.add_spool(color="Black", initial_weight_grams=1000.0)
        svc.reserve_filament(spool.id, 50.0)
        ok = svc.release_filament(spool.id, 50.0)
        assert ok is True
        refreshed = svc.get_spool(spool.id)
        assert refreshed.pending_weight_grams   == pytest.approx(0.0)
        assert refreshed.available_weight_grams == pytest.approx(1000.0)

    def test_commit_filament(self, svc):
        spool = svc.add_spool(color="Black", initial_weight_grams=1000.0)
        svc.reserve_filament(spool.id, 50.0)
        ok = svc.commit_filament(spool.id, 50.0)
        assert ok is True
        refreshed = svc.get_spool(spool.id)
        assert refreshed.current_weight_grams   == pytest.approx(950.0)
        assert refreshed.pending_weight_grams   == pytest.approx(0.0)
        assert refreshed.available_weight_grams == pytest.approx(950.0)

    def test_move_to_trash_creates_history(self, svc, db):
        spool = svc.add_spool(color="Red", initial_weight_grams=200.0)
        ok = svc.move_to_trash(spool.id, reason="finished")
        assert ok is True
        refreshed = svc.get_spool(spool.id)
        assert refreshed.status     == "trash"
        assert refreshed.is_active  is False
        # History record should exist
        count = db.get_table_count("filament_history")
        assert count >= 1

    def test_get_inventory_summary(self, svc):
        svc.add_spool(color="Black",      initial_weight_grams=1000.0)
        svc.add_spool(color="Light Blue", initial_weight_grams=500.0)
        summary = svc.get_inventory_summary()
        assert summary["active_spools"] >= 2
        assert summary["total_weight"]  >= pytest.approx(1500.0)

    def test_add_color(self, svc):
        ok = svc.add_color("Gold")
        assert ok is True
        colors = svc.get_colors()
        assert "Gold" in colors

    def test_reserve_more_than_available_fails(self, svc):
        spool = svc.add_spool(color="Black", initial_weight_grams=30.0)
        ok = svc.reserve_filament(spool.id, 50.0)
        assert ok is False
        refreshed = svc.get_spool(spool.id)
        assert refreshed.pending_weight_grams == pytest.approx(0.0)