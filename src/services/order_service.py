"""
src/services/order_service.py
==============================
All order-related business logic for Abaad 3D Print Manager v5.0.

This service sits between the UI and the database.
UI tabs call methods here; this module calls db.* methods.
No tkinter imports. No messagebox calls.

Pricing calculation chain (see calculate_totals):
  1.  Per-item tolerance discounts
  2.  Subtotal at base rate (4 EGP/g)
  3.  Actual total at item rates
  4.  Rate discount = subtotal - actual_total  (auto)
  5.  Order discount (manual %)
  6.  R&D override → total = material + electricity + depreciation
  7.  Payment fee (Cash/VodaCash/InstaPay)
  8.  Final total = discounted_subtotal + shipping + fee
  9.  Rounding loss (if amount_received < total)
  10. Profit = discounted_subtotal − production_costs
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from src.core.config import (
    DEFAULT_COST_PER_GRAM,
    DEFAULT_RATE_PER_GRAM,
    ELECTRICITY_RATE,
    TOLERANCE_THRESHOLD_GRAMS,
)
from src.core.models import Order, PrintItem
from src.utils.helpers import calculate_payment_fee, generate_id, now_str

log = logging.getLogger(__name__)


class OrderService:
    """CRUD + pricing business logic for orders.

    Args:
        db: A ``DatabaseManager`` instance (from ``src.core.database``).
    """

    def __init__(self, db) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> Optional[Order]:
        """Load a single order with its items.

        Args:
            order_id: The order UUID.

        Returns:
            Fully-assembled ``Order`` object, or ``None`` if not found.
        """
        row = self._db.get_order(order_id)
        if not row:
            return None
        order = Order.from_dict(row)
        order.items = self._load_items(order_id)
        return order

    def get_all_orders(self, include_deleted: bool = False) -> List[Order]:
        """Return all orders, optionally including soft-deleted ones.

        Items are NOT pre-loaded here (use ``get_order`` for that) to keep
        list views fast.

        Args:
            include_deleted: When ``True``, include orders with ``is_deleted=1``.

        Returns:
            List of ``Order`` objects (no items attached).
        """
        rows = self._db.get_all_orders(include_deleted=include_deleted)
        return [Order.from_dict(r) for r in rows]

    def get_deleted_orders(self) -> List[Order]:
        """Return only soft-deleted orders (for the Trash tab)."""
        all_orders = self._db.get_all_orders(include_deleted=True)
        return [Order.from_dict(r) for r in all_orders if r.get("is_deleted")]

    def search_orders(
        self,
        query: str = "",
        status_filter: str = "All",
    ) -> List[Order]:
        """Search orders by customer name/number with optional status filter.

        Args:
            query:         Case-insensitive text to match against
                           customer_name or order_number.
            status_filter: ``'All'`` or one of the ``ORDER_STATUSES`` values.

        Returns:
            Filtered list of ``Order`` objects (no items attached).
        """
        orders = self.get_all_orders()
        q = query.strip().lower()

        if q:
            orders = [
                o for o in orders
                if q in o.customer_name.lower()
                or q in str(o.order_number)
                or q in o.customer_phone
            ]

        if status_filter and status_filter != "All":
            orders = [o for o in orders if o.status == status_filter]

        return sorted(orders, key=lambda o: o.order_number, reverse=True)

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_order(
        self,
        customer_name: str,
        customer_phone: str = "",
        customer_id: str = "",
    ) -> Order:
        """Create and persist a new Draft order.

        Args:
            customer_name:  Display name for the order header.
            customer_phone: Customer phone number.
            customer_id:    Optional FK to the customers table.

        Returns:
            The newly-created ``Order`` object.
        """
        order = Order(
            id             = generate_id(),
            order_number   = self._db.get_next_order_number(),
            customer_id    = customer_id,
            customer_name  = customer_name.strip(),
            customer_phone = customer_phone.strip(),
            status         = "Draft",
            created_date   = now_str(),
            updated_date   = now_str(),
        )
        self._db.save_order(order.to_dict())
        log.info("Created order #%d  id=%s", order.order_number, order.id)
        return order

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def add_item(self, order: Order, item_data: dict) -> PrintItem:
        """Add a new print item to an order and recalculate totals.

        Args:
            order:     The parent ``Order`` (mutated in-place).
            item_data: Dict with item fields — any missing keys get defaults.

        Returns:
            The created ``PrintItem``.
        """
        item = PrintItem.from_dict({**item_data, "id": item_data.get("id") or generate_id()})
        order.items.append(item)
        self.calculate_totals(order)
        self._persist_order(order)
        return item

    def update_item(self, order: Order, item_id: str, item_data: dict) -> bool:
        """Replace an existing item's data and recalculate totals.

        Args:
            order:     The parent ``Order`` (mutated in-place).
            item_id:   ID of the item to replace.
            item_data: New field values.

        Returns:
            ``True`` if the item was found and updated.
        """
        for i, item in enumerate(order.items):
            if item.id == item_id:
                updated = PrintItem.from_dict({**item_data, "id": item_id})
                order.items[i] = updated
                self.calculate_totals(order)
                self._persist_order(order)
                return True
        log.warning("update_item: item %s not found in order %s", item_id, order.id)
        return False

    def remove_item(self, order: Order, item_id: str) -> bool:
        """Remove an item from an order and recalculate totals.

        Args:
            order:   The parent ``Order`` (mutated in-place).
            item_id: ID of the item to remove.

        Returns:
            ``True`` if the item was found and removed.
        """
        before = len(order.items)
        order.items = [i for i in order.items if i.id != item_id]
        if len(order.items) == before:
            return False
        self.calculate_totals(order)
        self._persist_order(order)
        return True

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save_order(self, order: Order) -> bool:
        """Validate and persist an order (with its items).

        Args:
            order: The ``Order`` to save.

        Returns:
            ``True`` on success, ``False`` on validation failure or DB error.
        """
        valid, msg = self._validate(order)
        if not valid:
            log.warning("save_order validation failed: %s", msg)
            return False
        self.calculate_totals(order)
        return self._persist_order(order)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def update_status(self, order_id: str, new_status: str) -> bool:
        """Change an order's status and record transition timestamps.

        Allowed transitions are not enforced here — the UI should guard them.
        Timestamps ``confirmed_date`` and ``delivered_date`` are set automatically.

        Args:
            order_id:   Target order ID.
            new_status: One of the ``ORDER_STATUSES`` string values.

        Returns:
            ``True`` on success.
        """
        order = self.get_order(order_id)
        if not order:
            return False

        order.status       = new_status
        order.updated_date = now_str()

        if new_status == "Confirmed" and not order.confirmed_date:
            order.confirmed_date = now_str()
        if new_status == "Delivered" and not order.delivered_date:
            order.delivered_date = now_str()

        return self._persist_order(order)

    # ------------------------------------------------------------------
    # Delete / restore
    # ------------------------------------------------------------------

    def delete_order(self, order_id: str, hard: bool = False) -> bool:
        """Soft-delete (default) or permanently delete an order.

        Args:
            order_id: Target order ID.
            hard:     If ``True``, permanently deletes the record.

        Returns:
            ``True`` on success.
        """
        return self._db.delete_order(order_id, soft=not hard)

    def restore_order(self, order_id: str) -> bool:
        """Restore a soft-deleted order.

        Args:
            order_id: Target order ID.

        Returns:
            ``True`` on success.
        """
        return self._db.restore_order(order_id)

    # ------------------------------------------------------------------
    # Pricing engine  (the core of the service)
    # ------------------------------------------------------------------

    def calculate_totals(self, order: Order) -> Order:
        """Recalculate all financial fields on *order* from its items.

        Implements the full pricing chain defined in the spec.
        Mutates the order in-place and also returns it.

        Steps:
            1.  Tolerance discounts per item
            2.  Subtotal at base rate (4 EGP/g)
            3.  Actual total at per-item rates
            4.  Rate discount (auto-calculated)
            5.  Manual order discount
            6.  Production cost tracking (material, electricity, depreciation)
            7.  R&D override (zero profit, cost = total)
            8.  Payment fee
            9.  Final total
            10. Rounding loss
            11. Profit

        Args:
            order: The ``Order`` to recalculate (mutated in-place).

        Returns:
            The same ``order`` object for chaining.
        """
        # 1. Per-item tolerance discounts
        order.tolerance_discount_total = 0.0
        for item in order.items:
            if item.actual_weight_grams > 0:
                item.calculate_tolerance_discount()
            order.tolerance_discount_total += item.tolerance_discount_amount

        # 2. Subtotal at base rate (4 EGP/g)
        order.subtotal = sum(
            item.weight * item.quantity * DEFAULT_RATE_PER_GRAM
            for item in order.items
        )

        # 3. Actual total at per-item rates (already includes tolerance deduction)
        order.actual_total = sum(item.print_cost for item in order.items)

        # 4. Rate discount (auto)
        if order.subtotal > 0:
            order.discount_amount  = order.subtotal - order.actual_total
            order.discount_percent = (order.discount_amount / order.subtotal) * 100
        else:
            order.discount_amount  = 0.0
            order.discount_percent = 0.0

        # 5. Manual order discount
        after_rate_discount = order.actual_total
        if order.order_discount_percent > 0:
            order.order_discount_amount = after_rate_discount * (order.order_discount_percent / 100)
        else:
            order.order_discount_amount = 0.0

        final_subtotal = after_rate_discount - order.order_discount_amount

        # 6. Production costs (internal tracking)
        total_weight          = sum(i.total_weight for i in order.items)
        total_time_minutes    = sum(i.time_minutes * i.quantity for i in order.items)
        order.material_cost     = total_weight * DEFAULT_COST_PER_GRAM
        order.electricity_cost  = (total_time_minutes / 60) * ELECTRICITY_RATE
        order.depreciation_cost = total_weight * _depreciation_per_gram()

        # 7. R&D override — total = costs, zero profit
        if order.is_rd_project:
            final_subtotal              = order.material_cost + order.electricity_cost + order.depreciation_cost
            order.order_discount_percent = 0.0
            order.order_discount_amount  = 0.0

        # 8. Payment fee
        subtotal_with_shipping = final_subtotal + order.shipping_cost
        order.payment_fee = calculate_payment_fee(subtotal_with_shipping, order.payment_method)

        # 9. Final total
        order.total = final_subtotal + order.shipping_cost + order.payment_fee

        # 10. Rounding loss
        if order.amount_received > 0:
            diff = order.total - order.amount_received
            order.rounding_loss = max(0.0, diff)

        # 11. Profit
        production_costs = order.material_cost + order.electricity_cost + order.depreciation_cost
        order.profit = 0.0 if order.is_rd_project else final_subtotal - production_costs

        order.updated_date = now_str()
        return order

    def get_price_breakdown(self, order: Order) -> dict:
        """Return a human-readable breakdown dict for display / PDF.

        Args:
            order: A fully calculated ``Order``.

        Returns:
            Dict with labelled line items for every price component.
        """
        return {
            "subtotal_base":       order.subtotal,
            "rate_discount":       order.discount_amount,
            "rate_discount_pct":   order.discount_percent,
            "after_rate":          order.actual_total,
            "order_discount":      order.order_discount_amount,
            "order_discount_pct":  order.order_discount_percent,
            "tolerance_discount":  order.tolerance_discount_total,
            "after_discounts":     order.actual_total - order.order_discount_amount,
            "shipping":            order.shipping_cost,
            "payment_fee":         order.payment_fee,
            "payment_method":      order.payment_method,
            "total":               order.total,
            "amount_received":     order.amount_received,
            "rounding_loss":       order.rounding_loss,
            "is_rd_project":       order.is_rd_project,
            "material_cost":       order.material_cost,
            "electricity_cost":    order.electricity_cost,
            "depreciation_cost":   order.depreciation_cost,
            "profit":              order.profit,
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_next_order_number(self) -> int:
        """Return and increment the global order counter.

        Returns:
            The next available order number (1-based, sequential).
        """
        return self._db.get_next_order_number()

    def fix_order_numbering(self) -> None:
        """Close gaps in order numbers (call after bulk deletes)."""
        self._db.fix_order_numbering()

    def get_order_summary(self, order: Order) -> dict:
        """Return a concise summary dict for list-view display.

        Args:
            order: The order to summarise.

        Returns:
            Dict with display-ready strings and values.
        """
        return {
            "order_number":  order.order_number,
            "customer_name": order.customer_name,
            "item_count":    order.item_count,
            "total_weight":  round(sum(i.total_weight for i in order.items), 1),
            "total":         order.total,
            "status":        order.status,
            "created_date":  order.created_date[:10],
            "is_rd_project": order.is_rd_project,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_items(self, order_id: str) -> List[PrintItem]:
        """Fetch and deserialise items for an order."""
        rows = self._db.get_items(order_id)
        return [PrintItem.from_dict(r) for r in rows]

    def _persist_order(self, order: Order) -> bool:
        """Save order header + items atomically."""
        ok_order = self._db.save_order(order.to_dict())
        ok_items = self._db.save_items(order.id, [i.to_dict() for i in order.items])
        return ok_order and ok_items

    def _validate(self, order: Order) -> Tuple[bool, str]:
        """Run basic validation before saving.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not order.id:
            return False, "Order has no ID"
        if not order.customer_name.strip():
            return False, "Customer name is required"
        if order.order_number <= 0:
            return False, "Invalid order number"
        return True, ""


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _depreciation_per_gram() -> float:
    """Depreciation cost per gram based on default printer specs.

    Uses constants from config rather than hardcoding.
    Override per-printer is handled by PrinterService.
    """
    from src.core.config import DEFAULT_PRINTER_LIFETIME_KG, DEFAULT_PRINTER_PRICE
    return DEFAULT_PRINTER_PRICE / (DEFAULT_PRINTER_LIFETIME_KG * 1000)