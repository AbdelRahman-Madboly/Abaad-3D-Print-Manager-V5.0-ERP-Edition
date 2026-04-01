"""
src/services/finance_service.py
=================================
Expenses, print failures, and business statistics for Abaad v5.0.

This service owns three concerns:
  1. Expenses  — CRUD for business expenses
  2. Failures  — logging and resolving failed print jobs
  3. Statistics — the big aggregation used by StatsTab and AnalyticsTab
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.core.config import (
    DEFAULT_COST_PER_GRAM,
    ELECTRICITY_RATE,
    EXPENSE_CATEGORIES,
    FAILURE_REASONS,
)
from src.core.models import Expense, PrintFailure, Statistics
from src.utils.helpers import generate_id, now_str, today_str

log = logging.getLogger(__name__)


class FinanceService:
    """Expenses, failures, and statistics aggregation.

    Args:
        db: A ``DatabaseManager`` instance.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ==================================================================
    # Expenses
    # ==================================================================

    def get_all_expenses(self) -> List[Expense]:
        """Return all expenses, newest first."""
        return [Expense.from_dict(r) for r in self._db.get_all_expenses()]

    def add_expense(
        self,
        category: str,
        name: str,
        amount: float,
        quantity: int = 1,
        supplier: str = "",
        description: str = "",
        is_recurring: bool = False,
        recurring_period: str = "",
        date: str = "",
    ) -> Expense:
        """Create and persist a new expense record.

        Args:
            category:         One of ``EXPENSE_CATEGORIES``.
            name:             Item name (e.g. ``'Electricity bill'``).
            amount:           Unit price in EGP.
            quantity:         How many units purchased (default 1).
            supplier:         Supplier / vendor name.
            description:      Optional free-text notes.
            is_recurring:     Mark as a recurring expense.
            recurring_period: ``'monthly'`` or ``'yearly'``.
            date:             Override date string; defaults to today.

        Returns:
            The newly-created ``Expense``.
        """
        expense = Expense(
            id               = generate_id(),
            date             = date or today_str(),
            category         = category,
            name             = name.strip(),
            description      = description,
            amount           = amount,
            quantity         = quantity,
            supplier         = supplier.strip(),
            is_recurring     = is_recurring,
            recurring_period = recurring_period,
        )
        expense.calculate_total()
        self._db.save_expense(expense.to_dict())
        log.info("Added expense '%s'  %.2f EGP  (x%d)", expense.name, expense.amount, quantity)
        return expense

    def update_expense(self, expense_id: str, **kwargs) -> bool:
        """Edit an existing expense record.

        This fixes the v4 bug where the UI said "delete and re-add to edit".

        Args:
            expense_id: Target expense ID.
            **kwargs:   Field names and new values.

        Returns:
            ``True`` on success, ``False`` if not found.
        """
        rows = self._db.get_all_expenses()
        row  = next((r for r in rows if r["id"] == expense_id), None)
        if not row:
            log.warning("update_expense: %s not found", expense_id)
            return False

        expense = Expense.from_dict(row)
        for key, value in kwargs.items():
            if hasattr(expense, key):
                setattr(expense, key, value)
        expense.calculate_total()
        return self._db.save_expense(expense.to_dict())

    def delete_expense(self, expense_id: str) -> bool:
        """Permanently delete an expense.

        Args:
            expense_id: Target expense ID.

        Returns:
            ``True`` on success.
        """
        return self._db.delete_expense(expense_id)

    def get_expense_stats(self) -> Dict:
        """Aggregate expense totals by category and by month.

        Returns:
            Dict with:
              - ``total_expenses``:  grand total EGP
              - ``expense_count``:   number of records
              - ``by_category``:     {category: total_egp}
              - ``monthly``:         {YYYY-MM: total_egp}
        """
        expenses = self.get_all_expenses()

        by_category: Dict[str, float] = defaultdict(float)
        monthly:     Dict[str, float] = defaultdict(float)

        for e in expenses:
            by_category[e.category] += e.total_cost
            month_key = e.date[:7]   # "YYYY-MM"
            monthly[month_key]       += e.total_cost

        return {
            "total_expenses": sum(e.total_cost for e in expenses),
            "expense_count":  len(expenses),
            "by_category":    dict(by_category),
            "monthly":        dict(sorted(monthly.items())),
        }

    # ==================================================================
    # Print Failures
    # ==================================================================

    def get_all_failures(self) -> List[PrintFailure]:
        """Return all failure records, newest first."""
        return [PrintFailure.from_dict(r) for r in self._db.get_all_failures()]

    def log_failure(
        self,
        source: str,
        item_name: str,
        reason: str,
        filament_wasted_grams: float = 0.0,
        time_wasted_minutes: int = 0,
        spool_id: str = "",
        color: str = "",
        printer_id: str = "",
        printer_name: str = "",
        order_id: str = "",
        order_number: int = 0,
        customer_name: str = "",
        description: str = "",
        date: str = "",
    ) -> PrintFailure:
        """Log a failed print job and auto-calculate costs.

        Filament wasted is deducted from the spool (if ``spool_id`` given).

        Args:
            source:                ``'Customer Order'``, ``'R&D Project'``, etc.
            item_name:             Name of the part that failed.
            reason:                One of ``FAILURE_REASONS``.
            filament_wasted_grams: Grams of filament consumed.
            time_wasted_minutes:   Print time lost.
            spool_id:              Spool the filament came from (optional).
            color:                 Filament colour for the record.
            printer_id:            Printer that failed (optional).
            printer_name:          Printer display name for the record.
            order_id:              Linked order ID (optional).
            order_number:          Linked order number for display.
            customer_name:         Customer name for the record.
            description:           Free-text notes about the failure.
            date:                  Override date; defaults to now.

        Returns:
            The newly-created ``PrintFailure``.
        """
        failure = PrintFailure(
            id                    = generate_id(),
            date                  = date or now_str(),
            source                = source,
            order_id              = order_id,
            order_number          = order_number,
            customer_name         = customer_name,
            item_name             = item_name.strip(),
            reason                = reason,
            description           = description,
            filament_wasted_grams = filament_wasted_grams,
            time_wasted_minutes   = time_wasted_minutes,
            spool_id              = spool_id,
            color                 = color,
            printer_id            = printer_id,
            printer_name          = printer_name,
        )
        failure.calculate_costs(
            cost_per_gram    = DEFAULT_COST_PER_GRAM,
            electricity_rate = ELECTRICITY_RATE,
        )
        self._db.save_failure(failure.to_dict())

        # Deduct wasted filament from spool
        if spool_id and filament_wasted_grams > 0:
            self._deduct_from_spool(spool_id, filament_wasted_grams)

        log.info(
            "Failure logged: '%s'  reason=%s  loss=%.2f EGP",
            item_name, reason, failure.total_loss,
        )
        return failure

    def resolve_failure(self, failure_id: str, notes: str = "") -> bool:
        """Mark a failure as resolved.

        Args:
            failure_id: Target failure ID.
            notes:      Resolution notes.

        Returns:
            ``True`` on success.
        """
        rows = self._db.get_all_failures()
        row  = next((r for r in rows if r["id"] == failure_id), None)
        if not row:
            log.warning("resolve_failure: %s not found", failure_id)
            return False
        failure                  = PrintFailure.from_dict(row)
        failure.resolved         = True
        failure.resolution_notes = notes
        return self._db.save_failure(failure.to_dict())

    def delete_failure(self, failure_id: str) -> bool:
        """Permanently delete a failure record.

        Args:
            failure_id: Target failure ID.

        Returns:
            ``True`` on success.
        """
        return self._db.delete_failure(failure_id)

    def get_failure_stats(self) -> Dict:
        """Aggregate failure totals by reason and resolution status.

        Returns:
            Dict with total_failures, total_cost, total_filament_wasted,
            total_time_wasted, unresolved_count, by_reason.
        """
        failures = self.get_all_failures()

        by_reason: Dict[str, int] = defaultdict(int)
        for f in failures:
            by_reason[f.reason] += 1

        return {
            "total_failures":        len(failures),
            "total_cost":            sum(f.total_loss for f in failures),
            "total_filament_wasted": sum(f.filament_wasted_grams for f in failures),
            "total_time_wasted":     sum(f.time_wasted_minutes for f in failures),
            "unresolved_count":      sum(1 for f in failures if not f.resolved),
            "by_reason":             dict(by_reason),
        }

    # ==================================================================
    # Full Statistics  (used by StatsTab)
    # ==================================================================

    def get_full_statistics(self) -> dict:
        """Aggregate all business statistics into a ``Statistics`` object.

        Reads orders, spools, printers, failures, and expenses from the DB.
        This is the equivalent of the old ``DatabaseManager.get_statistics()``.

        Returns:
            A fully-populated ``Statistics`` dataclass.
        """
        from src.core.models import Order, Printer, FilamentSpool

        stats = Statistics()

        # ---- Orders ----
        order_rows = self._db.get_all_orders(include_deleted=False)
        orders     = [Order.from_dict(r) for r in order_rows]

        active_orders = [o for o in orders if o.status != "Cancelled"]

        stats.total_orders     = len(orders)
        stats.completed_orders = sum(1 for o in orders if o.status == "Delivered")
        stats.rd_orders        = sum(1 for o in orders if o.is_rd_project)

        stats.total_revenue          = sum(o.total           for o in active_orders)
        stats.total_shipping         = sum(o.shipping_cost   for o in active_orders)
        stats.total_payment_fees     = sum(o.payment_fee     for o in active_orders)
        stats.total_rounding_loss    = sum(o.rounding_loss   for o in active_orders)
        stats.total_material_cost    = sum(o.material_cost   for o in active_orders)
        stats.total_electricity_cost = sum(o.electricity_cost for o in active_orders)
        stats.total_depreciation_cost= sum(o.depreciation_cost for o in active_orders)
        stats.total_tolerance_discounts = sum(o.tolerance_discount_total for o in active_orders)
        stats.gross_profit           = sum(o.profit          for o in active_orders)

        printed_statuses = ("Delivered", "Ready", "In Progress")
        stats.total_weight_printed = sum(
            o.total_weight for o in orders if o.status in printed_statuses
        )
        # total_time requires items — approximate from order fields
        # (items not pre-loaded here for performance)
        stats.total_time_printed = 0  # filled by detailed pass if needed

        # ---- Failures ----
        fail_stats = self.get_failure_stats()
        stats.total_failures          = fail_stats["total_failures"]
        stats.total_failure_cost      = fail_stats["total_cost"]
        stats.failure_filament_wasted = fail_stats["total_filament_wasted"]
        stats.failure_time_wasted     = fail_stats["total_time_wasted"]

        # ---- Expenses ----
        exp_stats = self.get_expense_stats()
        stats.total_expenses       = exp_stats["total_expenses"]
        by_cat                     = exp_stats["by_category"]
        stats.expenses_tools       = by_cat.get("Tools", 0.0)
        stats.expenses_consumables = by_cat.get("Consumables", 0.0)
        stats.expenses_maintenance = by_cat.get("Maintenance", 0.0)
        stats.expenses_other       = (
            stats.total_expenses
            - stats.expenses_tools
            - stats.expenses_consumables
            - stats.expenses_maintenance
        )

        # TRUE PROFIT = Gross − Failures − Expenses
        stats.total_profit = stats.gross_profit - stats.total_failure_cost - stats.total_expenses

        # ---- Inventory ----
        spool_rows = self._db.get_all_spools()
        spools     = [FilamentSpool.from_dict(r) for r in spool_rows]

        stats.total_filament_used   = sum(s.used_weight_grams for s in spools)
        stats.active_spools         = sum(1 for s in spools if s.is_active and s.current_weight_grams > 50)
        stats.remaining_filament    = sum(s.current_weight_grams for s in spools if s.is_active)
        stats.pending_filament      = sum(s.pending_weight_grams for s in spools)
        stats.total_filament_waste  = sum(s.current_weight_grams for s in spools if s.status == "trash")
        stats.total_filament_waste += stats.failure_filament_wasted

        # ---- Printers ----
        printer_rows = self._db.get_all_printers()
        printers     = [Printer.from_dict(r) for r in printer_rows]

        stats.total_printers   = len(printers)
        stats.total_nozzle_cost = sum(p.total_nozzle_cost for p in printers)

        # ---- Customers ----
        stats.total_customers = self._db.get_table_count("customers")

        return {
            "total_revenue":      stats.total_revenue,
            "total_shipping":     stats.total_shipping,
            "total_fees":         stats.total_payment_fees,
            "total_rounding":     stats.total_rounding_loss,
            "total_material":     stats.total_material_cost,
            "total_electricity":  stats.total_electricity_cost,
            "total_depreciation": stats.total_depreciation_cost,
            "total_nozzle":       stats.total_nozzle_cost,
            "gross_profit":       stats.gross_profit,
            "total_weight":       stats.total_weight_printed,
            "total_print_time":   stats.total_time_printed,
        }

    def get_monthly_breakdown(self, months: int = 12) -> List[Dict]:
        """Return per-month revenue, cost, and profit for the last N months.

        Args:
            months: Number of months to include (default 12).

        Returns:
            List of dicts sorted oldest-first, each with:
            month, revenue, material_cost, electricity_cost,
            depreciation_cost, failure_cost, expense_cost, profit.
        """
        from src.core.models import Order

        order_rows = self._db.get_all_orders(include_deleted=False)
        orders     = [Order.from_dict(r) for r in order_rows if r.get("status") != "Cancelled"]

        # Group by YYYY-MM
        buckets: Dict[str, Dict] = defaultdict(lambda: {
            "revenue": 0.0, "material_cost": 0.0, "electricity_cost": 0.0,
            "depreciation_cost": 0.0, "profit": 0.0,
        })

        for o in orders:
            key = o.created_date[:7]
            buckets[key]["revenue"]          += o.total
            buckets[key]["material_cost"]    += o.material_cost
            buckets[key]["electricity_cost"] += o.electricity_cost
            buckets[key]["depreciation_cost"]+= o.depreciation_cost
            buckets[key]["profit"]           += o.profit

        # Expenses by month
        exp_stats = self.get_expense_stats()
        for month_key, total in exp_stats["monthly"].items():
            if month_key in buckets:
                buckets[month_key]["expense_cost"] = total
            else:
                buckets[month_key]["expense_cost"] = total

        # Failures by month
        failures = self.get_all_failures()
        for f in failures:
            key = f.date[:7]
            if key in buckets:
                buckets[key].setdefault("failure_cost", 0.0)
                buckets[key]["failure_cost"] += f.total_loss

        # Build sorted list, limited to last N months
        result = []
        for month_key in sorted(buckets.keys())[-months:]:
            row = {"month": month_key, **buckets[month_key]}
            row.setdefault("expense_cost", 0.0)
            row.setdefault("failure_cost", 0.0)
            result.append(row)

        return result

    def get_profit_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Profit report optionally filtered by date range.

        Args:
            start_date: ISO date string ``'YYYY-MM-DD'`` (inclusive).
            end_date:   ISO date string ``'YYYY-MM-DD'`` (inclusive).

        Returns:
            Dict with revenue, costs breakdown, gross_profit,
            failure_cost, expense_cost, net_profit, profit_margin.
        """
        from src.core.models import Order

        order_rows = self._db.get_all_orders(include_deleted=False)
        orders = [
            Order.from_dict(r) for r in order_rows
            if r.get("status") != "Cancelled"
        ]

        if start_date:
            orders = [o for o in orders if o.created_date[:10] >= start_date]
        if end_date:
            orders = [o for o in orders if o.created_date[:10] <= end_date]

        revenue          = sum(o.total for o in orders)
        material_cost    = sum(o.material_cost for o in orders)
        electricity_cost = sum(o.electricity_cost for o in orders)
        depreciation     = sum(o.depreciation_cost for o in orders)
        gross_profit     = sum(o.profit for o in orders)

        # Filter expenses and failures to date range
        expenses = self.get_all_expenses()
        failures = self.get_all_failures()
        if start_date:
            expenses = [e for e in expenses if e.date[:10] >= start_date]
            failures = [f for f in failures if f.date[:10] >= start_date]
        if end_date:
            expenses = [e for e in expenses if e.date[:10] <= end_date]
            failures = [f for f in failures if f.date[:10] <= end_date]

        expense_cost = sum(e.total_cost for e in expenses)
        failure_cost = sum(f.total_loss for f in failures)
        net_profit   = gross_profit - failure_cost - expense_cost

        return {
            "revenue":          round(revenue, 2),
            "material_cost":    round(material_cost, 2),
            "electricity_cost": round(electricity_cost, 2),
            "depreciation":     round(depreciation, 2),
            "gross_profit":     round(gross_profit, 2),
            "failure_cost":     round(failure_cost, 2),
            "expense_cost":     round(expense_cost, 2),
            "net_profit":       round(net_profit, 2),
            "profit_margin":    round((net_profit / revenue * 100) if revenue > 0 else 0, 1),
            "order_count":      len(orders),
            "start_date":       start_date or "",
            "end_date":         end_date or "",
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _deduct_from_spool(self, spool_id: str, grams: float) -> None:
        """Directly deduct filament from a spool (used for failure logging)."""
        row = self._db.get_spool(spool_id)
        if not row:
            return
        from src.core.models import FilamentSpool
        spool = FilamentSpool.from_dict(row)
        spool.commit_filament(grams)
        self._db.save_spool(spool.to_dict())