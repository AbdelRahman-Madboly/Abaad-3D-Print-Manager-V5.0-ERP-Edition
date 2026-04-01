"""
tests/test_models.py
====================
Pure unit tests for Abaad v5 dataclass models and business logic.
No database required — all tests operate on in-memory objects.
"""

import pytest
import sys
from pathlib import Path

# Allow running pytest from the project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import (
    Order,
    PrintItem,
    PrintSettings,
    Customer,
    FilamentSpool,
    Printer,
    PrintFailure,
    Expense,
    SpoolCategory,
    SpoolStatus,
    PaymentMethod,
    calculate_payment_fee,
)
from src.core.config import DEFAULT_RATE_PER_GRAM, DEFAULT_COST_PER_GRAM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_item(
    name: str = "Test Part",
    weight: float = 50.0,
    actual_weight: float = 0.0,
    rate: float = DEFAULT_RATE_PER_GRAM,
    qty: int = 1,
    time_minutes: int = 60,
) -> PrintItem:
    item = PrintItem()
    item.name = name
    item.estimated_weight_grams = weight
    item.actual_weight_grams = actual_weight
    item.rate_per_gram = rate
    item.quantity = qty
    item.estimated_time_minutes = time_minutes
    return item


def make_order(items: list | None = None) -> Order:
    order = Order()
    order.order_number = 1
    order.customer_name = "Test Customer"
    if items:
        order.items = items
    return order


def recalc(order: Order) -> Order:
    """Run calculate_totals via OrderService without a real DB."""
    from src.services.order_service import OrderService

    class _FakeDB:
        pass

    svc = OrderService(_FakeDB())
    return svc.calculate_totals(order)


# ---------------------------------------------------------------------------
# to_dict / from_dict roundtrips
# ---------------------------------------------------------------------------

class TestModelRoundtrips:

    def test_order_roundtrip(self):
        o = Order()
        o.order_number = 42
        o.customer_name = "Alice"
        o.status = "Confirmed"
        restored = Order.from_dict(o.to_dict())
        assert restored.order_number == 42
        assert restored.customer_name == "Alice"
        assert restored.status == "Confirmed"

    def test_print_item_roundtrip(self):
        item = make_item("Bracket", weight=30.0, qty=3)
        restored = PrintItem.from_dict(item.to_dict())
        assert restored.name == "Bracket"
        assert restored.estimated_weight_grams == 30.0
        assert restored.quantity == 3

    def test_print_settings_roundtrip(self):
        s = PrintSettings(nozzle_size=0.6, layer_height=0.15, infill_density=30)
        restored = PrintSettings.from_dict(s.to_dict())
        assert restored.nozzle_size == 0.6
        assert restored.layer_height == 0.15
        assert restored.infill_density == 30

    def test_customer_roundtrip(self):
        c = Customer()
        c.name = "Bob"
        c.phone = "01234567890"
        restored = Customer.from_dict(c.to_dict())
        assert restored.name == "Bob"
        assert restored.phone == "01234567890"

    def test_filament_spool_roundtrip(self):
        s = FilamentSpool()
        s.color = "Silver"
        s.current_weight_grams = 750.0
        s.pending_weight_grams = 100.0
        restored = FilamentSpool.from_dict(s.to_dict())
        assert restored.color == "Silver"
        assert restored.current_weight_grams == 750.0
        assert restored.pending_weight_grams == 100.0

    def test_printer_roundtrip(self):
        p = Printer()
        p.name = "HIVE 0.1"
        p.total_printed_grams = 5000.0
        restored = Printer.from_dict(p.to_dict())
        assert restored.name == "HIVE 0.1"
        assert restored.total_printed_grams == 5000.0

    def test_print_failure_roundtrip(self):
        f = PrintFailure()
        f.reason = "Nozzle Clog"
        f.filament_wasted_grams = 12.5
        restored = PrintFailure.from_dict(f.to_dict())
        assert restored.reason == "Nozzle Clog"
        assert restored.filament_wasted_grams == 12.5

    def test_expense_roundtrip(self):
        e = Expense()
        e.name = "Nozzle pack"
        e.amount = 200.0
        e.quantity = 2
        e.calculate_total()
        restored = Expense.from_dict(e.to_dict())
        assert restored.name == "Nozzle pack"
        assert restored.total_cost == 400.0


# ---------------------------------------------------------------------------
# Order.calculate_totals pricing scenarios
# ---------------------------------------------------------------------------

class TestCalculateTotals:

    def test_single_item_cash(self):
        """50 g × 1 qty × 4.0 EGP/g, Cash → total = 200.00"""
        order = make_order([make_item(weight=50.0, qty=1)])
        order.payment_method = "Cash"
        recalc(order)
        assert order.subtotal == pytest.approx(200.00)
        assert order.total == pytest.approx(200.00)
        assert order.payment_fee == pytest.approx(0.00)

    def test_two_items_rate_discount(self):
        """
        item1: 50 g × 1 × 4.0 → 200
        item2: 30 g × 1 × 3.0 → 90
        subtotal (base) = 200 + 120 = 320
        actual           = 200 + 90  = 290
        rate_discount    = 30
        """
        item1 = make_item(weight=50.0, rate=4.0)
        item2 = make_item(weight=30.0, rate=3.0)
        order = make_order([item1, item2])
        order.payment_method = "Cash"
        recalc(order)
        assert order.subtotal      == pytest.approx(320.00)
        assert order.actual_total  == pytest.approx(290.00)
        assert order.discount_amount == pytest.approx(30.00)

    def test_tolerance_discount_within_threshold(self):
        """
        estimated=50 g, actual=53 g, diff=3 g (in 1-5 range)
        tolerance_discount = 1 g × 4.0 × 1 qty = 4.00
        print_cost = 53 × 4.0 − 4.0 = 208.0
        """
        item = make_item(weight=50.0, actual_weight=53.0, rate=4.0, qty=1)
        order = make_order([item])
        order.payment_method = "Cash"
        recalc(order)
        assert item.tolerance_discount_amount == pytest.approx(4.0)
        assert item.print_cost == pytest.approx(53 * 4.0 - 4.0)

    def test_tolerance_discount_outside_threshold(self):
        """diff=6 g (> 5 threshold) → no discount"""
        item = make_item(weight=50.0, actual_weight=56.0, rate=4.0)
        order = make_order([item])
        recalc(order)
        assert item.tolerance_discount_amount == pytest.approx(0.0)
        assert item.tolerance_discount_applied is False

    def test_rd_mode_zero_profit(self):
        """R&D order: profit must be 0, total = material+elec+depreciation."""
        order = make_order([make_item(weight=100.0)])
        order.is_rd_project = True
        order.payment_method = "Cash"
        recalc(order)
        assert order.profit == pytest.approx(0.0)
        expected_total = order.material_cost + order.electricity_cost + order.depreciation_cost
        assert order.total == pytest.approx(expected_total, abs=0.01)

    def test_vodacash_fee_hits_minimum(self):
        """100 EGP × 0.5% = 0.50 → clamped to min 1.00 EGP"""
        fee = calculate_payment_fee(100.0, PaymentMethod.VODAFONE_CASH.value)
        assert fee == pytest.approx(1.00)

    def test_vodacash_fee_hits_maximum(self):
        """4000 EGP × 0.5% = 20.00 → clamped to max 15.00 EGP"""
        fee = calculate_payment_fee(4000.0, PaymentMethod.VODAFONE_CASH.value)
        assert fee == pytest.approx(15.00)

    def test_instapay_fee_hits_minimum(self):
        """100 EGP × 0.1% = 0.10 → clamped to min 0.50 EGP"""
        fee = calculate_payment_fee(100.0, PaymentMethod.INSTAPAY.value)
        assert fee == pytest.approx(0.50)

    def test_instapay_fee_no_cap(self):
        """1000 EGP × 0.1% = 1.00 → no clamping"""
        fee = calculate_payment_fee(1000.0, PaymentMethod.INSTAPAY.value)
        assert fee == pytest.approx(1.00)

    def test_order_discount_10_percent(self):
        """10% order discount on 200 EGP actual_total → discount = 20.00"""
        order = make_order([make_item(weight=50.0, rate=4.0)])
        order.order_discount_percent = 10.0
        order.payment_method = "Cash"
        recalc(order)
        assert order.order_discount_amount == pytest.approx(20.00)
        assert order.total == pytest.approx(180.00)


# ---------------------------------------------------------------------------
# FilamentSpool pending system
# ---------------------------------------------------------------------------

class TestFilamentSpoolPending:

    def _fresh_spool(self) -> FilamentSpool:
        s = FilamentSpool()
        s.current_weight_grams = 1000.0
        s.pending_weight_grams = 0.0
        return s

    def test_initial_available(self):
        s = self._fresh_spool()
        assert s.available_weight_grams == pytest.approx(1000.0)

    def test_reserve(self):
        s = self._fresh_spool()
        assert s.reserve_filament(50.0) is True
        assert s.pending_weight_grams == pytest.approx(50.0)
        assert s.available_weight_grams == pytest.approx(950.0)
        assert s.current_weight_grams  == pytest.approx(1000.0)

    def test_release(self):
        s = self._fresh_spool()
        s.reserve_filament(50.0)
        s.release_pending(50.0)
        assert s.pending_weight_grams  == pytest.approx(0.0)
        assert s.available_weight_grams == pytest.approx(1000.0)

    def test_commit(self):
        s = self._fresh_spool()
        s.reserve_filament(50.0)
        assert s.commit_filament(50.0) is True
        assert s.current_weight_grams  == pytest.approx(950.0)
        assert s.pending_weight_grams  == pytest.approx(0.0)
        assert s.available_weight_grams == pytest.approx(950.0)

    def test_reserve_insufficient(self):
        s = self._fresh_spool()
        s.current_weight_grams = 30.0
        assert s.reserve_filament(50.0) is False
        assert s.pending_weight_grams == pytest.approx(0.0)

    def test_commit_insufficient(self):
        s = self._fresh_spool()
        s.current_weight_grams = 10.0
        assert s.commit_filament(50.0) is False

    def test_status_becomes_low_after_commit(self):
        s = self._fresh_spool()
        s.current_weight_grams = 25.0
        s.commit_filament(10.0)
        assert s.status == SpoolStatus.LOW.value